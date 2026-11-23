from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

USER_CONFIG_DIR = Path.home() / ".config" / "tdkit"
USER_ENV_PATH = USER_CONFIG_DIR / ".env"


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    default_section: str | None = None
    sections: dict[str, str] = field(default_factory=dict)
    members: dict[str, str] = field(default_factory=dict)
    config_path: Path | None = None


def find_config_file(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".todoist.toml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "No .todoist.toml found in this directory or any parent. "
        "Create one at the repository root to scope agent access."
    )


def load_config(start: Path | None = None) -> ProjectConfig:
    path = find_config_file(start)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    project_id = str(project.get("id", "")).strip()
    if not project_id:
        raise ValueError(f"Missing [project].id in {path}")

    return ProjectConfig(
        project_id=project_id,
        default_section=project.get("default_section"),
        sections={k.lower(): str(v) for k, v in data.get("sections", {}).items()},
        members={k.lower(): str(v) for k, v in data.get("members", {}).items()},
        config_path=path,
    )


def _parse_token_from_file(file_path: Path) -> str:
    if not file_path.is_file():
        return ""
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k == "TODOIST_API_TOKEN" and v:
                    return v
    except OSError:
        pass
    return ""


def _load_env_fallback(start: Path | None = None) -> str:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        token = _parse_token_from_file(candidate)
        if token:
            return token
    return ""


def get_api_token(start: Path | None = None) -> str:
    # 1. Shell environment variable
    token = os.environ.get("TODOIST_API_TOKEN", "").strip()
    if token:
        return token

    # 2. Per-user package configuration (~/.config/tdkit/.env)
    token = _parse_token_from_file(USER_ENV_PATH)
    if token:
        return token

    # 3. Project directory fallback
    token = _load_env_fallback(start)
    if token:
        return token

    raise RuntimeError(
        "TODOIST_API_TOKEN is not configured.\n"
        "Run `tdkit auth <your_token>` to save it to your user configuration (~/.config/tdkit/.env),\n"
        "or export TODOIST_API_TOKEN in your shell profile."
    )


def save_user_token(token: str) -> Path:
    """Save user token securely to ~/.config/tdkit/.env (mode 0600)."""
    token = token.strip()
    if not token:
        raise ValueError("Token cannot be empty")
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_ENV_PATH.write_text(f'TODOIST_API_TOKEN="{token}"\n', encoding="utf-8")
    os.chmod(USER_ENV_PATH, 0o600)
    return USER_ENV_PATH
