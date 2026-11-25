from __future__ import annotations

import os
from pathlib import Path
import pytest

from tdkit.config import (
    USER_ENV_PATH,
    ProjectConfig,
    find_config_file,
    get_api_token,
    load_config,
    save_user_token,
)
from tdkit.client import Board
from tdkit.cli import main as cli_main
from tdkit.mcp_server import describe_api, execute


def test_find_config_file(tmp_path: Path) -> None:
    # No config in empty directory
    with pytest.raises(FileNotFoundError):
        find_config_file(tmp_path)

    # Place config in parent, verify child finds it
    parent = tmp_path / "repo"
    child = parent / "src" / "pkg"
    child.mkdir(parents=True)
    cfg_file = parent / ".todoist.toml"
    cfg_file.write_text('[project]\nid = "test-proj-123"\n', encoding="utf-8")

    assert find_config_file(child) == cfg_file


def test_load_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / ".todoist.toml"
    cfg_file.write_text(
        """
[project]
id = "proj_test"
default_section = "backlog"

[sections]
backlog = "sec_1"
in_progress = "sec_2"

[members]
alice = "user_1"
bob = "user_2"
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    assert config.project_id == "proj_test"
    assert config.default_section == "backlog"
    assert config.sections == {"backlog": "sec_1", "in_progress": "sec_2"}
    assert config.members == {"alice": "user_1", "bob": "user_2"}


def test_env_token_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TODOIST_API_TOKEN", raising=False)
    # Mock USER_ENV_PATH to nonexistent
    monkeypatch.setattr("tdkit.config.USER_ENV_PATH", tmp_path / "nonexistent" / ".env")

    # Without .env, should fail
    with pytest.raises(RuntimeError, match="TODOIST_API_TOKEN"):
        get_api_token(tmp_path)

    # With .env fallback
    env_file = tmp_path / ".env"
    env_file.write_text('TODOIST_API_TOKEN="token_from_env_file"\n', encoding="utf-8")
    assert get_api_token(tmp_path) == "token_from_env_file"


def test_user_config_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TODOIST_API_TOKEN", raising=False)
    fake_user_env = tmp_path / "user_config" / ".env"
    monkeypatch.setattr("tdkit.config.USER_CONFIG_DIR", fake_user_env.parent)
    monkeypatch.setattr("tdkit.config.USER_ENV_PATH", fake_user_env)

    save_user_token("user_secret_token_123")
    assert fake_user_env.is_file()
    assert get_api_token() == "user_secret_token_123"


def test_mcp_describe_api() -> None:
    desc = describe_api()
    assert "Available methods on `board`" in desc
    assert "board.add_task" in desc
    assert "board.list_tasks" in desc
    assert "board.move_task" in desc
    assert "board.complete_task" in desc


def test_cli_summary_and_run(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBoard:
        def __enter__(self) -> "FakeBoard":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def summary(self) -> dict[str, list[dict[str, str]]]:
            return {"backlog": [{"id": "1", "content": "Sample task"}]}

    monkeypatch.setattr("tdkit.cli.Board", FakeBoard)

    ret = cli_main(["summary"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Sample task" in captured.out

    ret_run = cli_main(["run", "result = 1 + 1"])
    assert ret_run == 0
    captured_run = capsys.readouterr()
    assert "2" in captured_run.out


def test_cli_whoami(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tdkit.cli.Board.get_user_info",
        staticmethod(lambda: {"id": "36012451", "name": "Test User", "email": "test@example.com"}),
    )
    ret = cli_main(["whoami"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Test User" in captured.out
