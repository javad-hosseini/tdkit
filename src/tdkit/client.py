from __future__ import annotations

from typing import Any
import httpx

from tdkit.config import ProjectConfig, get_api_token, load_config

BASE_URL = "https://api.todoist.com/api/v1"


class Board:
    """Project-scoped Todoist API v1 client designed for AI agent Code Mode."""

    def __init__(
        self,
        config: ProjectConfig | None = None,
        token: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.config = config or load_config()
        config_dir = self.config.config_path.parent if self.config.config_path else None
        self._token = token or get_api_token(config_dir)
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=timeout,
        )
        self._section_cache: dict[str, str] | None = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Board:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- Static helper methods for user/account inspection ---

    @staticmethod
    def get_user_info(token: str | None = None) -> dict[str, Any]:
        """Fetch current authenticated user profile (id, name, email)."""
        tok = token or get_api_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {tok}"}, timeout=15.0) as client:
            resp = client.get("/user")
            resp.raise_for_status()
            u = resp.json()
            return {"id": u.get("id"), "name": u.get("full_name"), "email": u.get("email")}

    @staticmethod
    def list_all_projects(token: str | None = None) -> list[dict[str, Any]]:
        """List all accessible Todoist projects across the account."""
        tok = token or get_api_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {tok}"}, timeout=15.0) as client:
            resp = client.get("/projects")
            resp.raise_for_status()
            data = resp.json()
            projects = data if isinstance(data, list) else data.get("results", [])
            return [{"id": p.get("id"), "name": p.get("name"), "is_shared": p.get("is_shared")} for p in projects]

    # --- Internal helpers ---

    def _paginate(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query = {k: v for k, v in (params or {}).items() if v is not None}
        while True:
            resp = self._client.get(path, params=query)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, list):
                items.extend(payload)
                break
            items.extend(payload.get("results", []))
            cursor = payload.get("next_cursor")
            if not cursor:
                break
            query["cursor"] = cursor
        return items

    def _sections_map(self) -> dict[str, str]:
        """Returns mapping of lowercase section name -> section_id."""
        if self._section_cache is None:
            raw = self._paginate("/sections", {"project_id": self.config.project_id})
            live = {s["name"].strip().lower(): str(s["id"]) for s in raw}
            # Merge live sections with explicit aliases from .todoist.toml
            merged = {**live, **self.config.sections}
            self._section_cache = merged
        return self._section_cache

    def _resolve_section_id(self, section: str | None) -> str | None:
        if not section:
            return None
        key = section.strip().lower()
        sections = self._sections_map()
        if key in sections:
            return sections[key]
        # Allow passing a raw section ID directly if already known
        if section in sections.values():
            return section
        available = ", ".join(sorted(sections.keys()))
        raise ValueError(f"Unknown section '{section}'. Available: {available}")

    def _resolve_assignee_id(self, assignee: str | None) -> str | None:
        if not assignee:
            return None
        return self.config.members.get(assignee.strip().lower(), assignee)

    def _section_name_by_id(self) -> dict[str, str]:
        return {sid: name for name, sid in self._sections_map().items()}

    def _compact_task(self, t: dict[str, Any], sec_names: dict[str, str]) -> dict[str, Any]:
        due = t.get("due")
        return {
            "id": str(t["id"]),
            "content": t.get("content", ""),
            "description": t.get("description", ""),
            "section": sec_names.get(str(t.get("section_id") or ""), None),
            "priority": t.get("priority", 1),  # Todoist API: 4=P1(urgent), 1=P4(normal)
            "labels": t.get("labels", []),
            "due": due.get("string") if isinstance(due, dict) else None,
            "assignee_id": t.get("assignee_id"),
            "parent_id": t.get("parent_id"),
        }

    # --- Public Agent API ---

    def list_sections(self) -> dict[str, str]:
        """Return {section_name: section_id} for the current repo's project."""
        return dict(self._sections_map())

    def list_tasks(
        self,
        section: str | None = None,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """List active tasks strictly inside this repo's Todoist project."""
        params: dict[str, Any] = {"project_id": self.config.project_id}
        if section:
            params["section_id"] = self._resolve_section_id(section)
        if label:
            params["label"] = label
        raw = self._paginate("/tasks", params)
        sec_names = self._section_name_by_id()
        return [self._compact_task(t, sec_names) for t in raw]

    def get_task(self, task_id: str, include_comments: bool = True) -> dict[str, Any]:
        """Fetch a single task and (optionally) its comments. Verifies project scope."""
        resp = self._client.get(f"/tasks/{task_id}")
        resp.raise_for_status()
        task = resp.json()
        if str(task.get("project_id")) != self.config.project_id:
            raise PermissionError(
                f"Task {task_id} does not belong to this repo's project ({self.config.project_id})."
            )
        result = self._compact_task(task, self._section_name_by_id())
        if include_comments:
            result["comments"] = self.get_comments(task_id)
        return result

    def add_task(
        self,
        content: str,
        description: str = "",
        section: str | None = None,
        priority: int = 1,
        labels: list[str] | None = None,
        due_string: str | None = None,
        assignee: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a task in this repo's project. Priority: 4=P1(urgent) .. 1=P4(normal)."""
        target_section = section or self.config.default_section
        body: dict[str, Any] = {
            "content": content,
            "description": description,
            "project_id": self.config.project_id,
            "priority": max(1, min(4, int(priority))),
        }
        if sec_id := self._resolve_section_id(target_section):
            body["section_id"] = sec_id
        if labels:
            body["labels"] = labels
        if due_string:
            body["due_string"] = due_string
        if assignee_id := self._resolve_assignee_id(assignee):
            body["assignee_id"] = assignee_id
        if parent_id:
            body["parent_id"] = parent_id

        resp = self._client.post("/tasks", json=body)
        resp.raise_for_status()
        return self._compact_task(resp.json(), self._section_name_by_id())

    def update_task(
        self,
        task_id: str,
        content: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        labels: list[str] | None = None,
        due_string: str | None = None,
        assignee: str | None = None,
    ) -> dict[str, Any]:
        """Update task metadata (verifies project ownership first)."""
        self.get_task(task_id, include_comments=False)
        body: dict[str, Any] = {}
        if content is not None:
            body["content"] = content
        if description is not None:
            body["description"] = description
        if priority is not None:
            body["priority"] = max(1, min(4, int(priority)))
        if labels is not None:
            body["labels"] = labels
        if due_string is not None:
            body["due_string"] = due_string
        if assignee is not None:
            body["assignee_id"] = self._resolve_assignee_id(assignee)

        resp = self._client.post(f"/tasks/{task_id}", json=body)
        resp.raise_for_status()
        return self._compact_task(resp.json(), self._section_name_by_id())

    def move_task(self, task_id: str, section: str) -> dict[str, Any]:
        """Move a task to another Kanban section inside the same project."""
        self.get_task(task_id, include_comments=False)
        section_id = self._resolve_section_id(section)
        resp = self._client.post(f"/tasks/{task_id}/move", json={"section_id": section_id})
        resp.raise_for_status()
        return {"id": task_id, "moved_to": section, "section_id": section_id}

    def complete_task(self, task_id: str, comment: str | None = None) -> dict[str, Any]:
        """Optionally post a closing comment, then mark the task done."""
        self.get_task(task_id, include_comments=False)
        if comment:
            self.comment(task_id, comment)
        resp = self._client.post(f"/tasks/{task_id}/close")
        resp.raise_for_status()
        return {"id": task_id, "status": "completed"}

    def reopen_task(self, task_id: str) -> dict[str, Any]:
        """Reopen a previously completed task."""
        resp = self._client.post(f"/tasks/{task_id}/reopen")
        resp.raise_for_status()
        return {"id": task_id, "status": "reopened"}

    def get_comments(self, task_id: str) -> list[dict[str, Any]]:
        """List comments on a task."""
        raw = self._paginate("/comments", {"task_id": task_id})
        return [
            {
                "id": str(c["id"]),
                "content": c.get("content", ""),
                "posted_at": c.get("posted_at"),
                "posted_uid": c.get("posted_uid"),
            }
            for c in raw
        ]

    def comment(self, task_id: str, content: str) -> dict[str, Any]:
        """Post a comment on a task in this project."""
        self.get_task(task_id, include_comments=False)
        resp = self._client.post("/comments", json={"task_id": task_id, "content": content})
        resp.raise_for_status()
        c = resp.json()
        return {"id": str(c["id"]), "task_id": task_id, "content": c.get("content", "")}

    def summary(self) -> dict[str, list[dict[str, Any]]]:
        """Group active project tasks by Kanban section for quick sprint overview."""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for task in self.list_tasks():
            key = task["section"] or "unsectioned"
            grouped.setdefault(key, []).append(
                {"id": task["id"], "content": task["content"], "priority": task["priority"], "labels": task["labels"]}
            )
        return grouped
