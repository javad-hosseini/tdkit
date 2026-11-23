from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Any

from tdkit.client import Board
from tdkit.config import get_api_token, save_user_token


def _out(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tdkit", description="Project-scoped Todoist CLI for AI agents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Global account commands (do not require .todoist.toml)
    p_auth = sub.add_parser("auth", help="Save personal Todoist token to user config (~/.config/tdkit/.env)")
    p_auth.add_argument("token", nargs="?", help="Personal Todoist API token (prompts if omitted)")

    sub.add_parser("whoami", help="Display current authenticated Todoist user identity")
    sub.add_parser("projects", help="List all accessible projects (useful for finding project ID for .todoist.toml)")

    # Project-scoped commands (require .todoist.toml)
    sub.add_parser("summary", help="Show tasks grouped by Kanban section")
    sub.add_parser("sections", help="List available sections in this project")

    p_list = sub.add_parser("list", help="List active tasks in this project")
    p_list.add_argument("--section", help="Filter by section name")
    p_list.add_argument("--label", help="Filter by label")

    p_get = sub.add_parser("get", help="Get task details and comments")
    p_get.add_argument("task_id")

    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("content")
    p_add.add_argument("-d", "--description", default="")
    p_add.add_argument("-s", "--section")
    p_add.add_argument("-p", "--priority", type=int, default=1, help="4=P1(urgent) .. 1=P4(normal)")
    p_add.add_argument("-l", "--label", action="append", dest="labels")
    p_add.add_argument("--due", dest="due_string")
    p_add.add_argument("--assignee")
    p_add.add_argument("--parent-id")

    p_move = sub.add_parser("move", help="Move task to a Kanban section")
    p_move.add_argument("task_id")
    p_move.add_argument("section")

    p_comment = sub.add_parser("comment", help="Add a comment to a task")
    p_comment.add_argument("task_id")
    p_comment.add_argument("content")

    p_done = sub.add_parser("done", help="Mark task as done (optionally with closing comment)")
    p_done.add_argument("task_id")
    p_done.add_argument("-c", "--comment")

    p_reopen = sub.add_parser("reopen", help="Reopen a completed task")
    p_reopen.add_argument("task_id")

    p_run = sub.add_parser("run", help="Code Mode: execute a Python snippet with `board` pre-bound")
    p_run.add_argument("code", help="Python code; assign output to `result` to print JSON")

    args = parser.parse_args(argv)

    try:
        # Global commands
        if args.cmd == "auth":
            token = args.token or getpass.getpass("Enter your Todoist API token: ")
            user_info = Board.get_user_info(token=token)
            saved_path = save_user_token(token)
            _out({
                "status": "authenticated",
                "user": user_info,
                "saved_to": str(saved_path),
            })
            return 0
        elif args.cmd == "whoami":
            _out(Board.get_user_info())
            return 0
        elif args.cmd == "projects":
            _out(Board.list_all_projects())
            return 0

        # Project-scoped commands
        with Board() as board:
            if args.cmd == "summary":
                _out(board.summary())
            elif args.cmd == "sections":
                _out(board.list_sections())
            elif args.cmd == "list":
                _out(board.list_tasks(section=args.section, label=args.label))
            elif args.cmd == "get":
                _out(board.get_task(args.task_id))
            elif args.cmd == "add":
                _out(
                    board.add_task(
                        content=args.content,
                        description=args.description,
                        section=args.section,
                        priority=args.priority,
                        labels=args.labels,
                        due_string=args.due_string,
                        assignee=args.assignee,
                        parent_id=args.parent_id,
                    )
                )
            elif args.cmd == "move":
                _out(board.move_task(args.task_id, args.section))
            elif args.cmd == "comment":
                _out(board.comment(args.task_id, args.content))
            elif args.cmd == "done":
                _out(board.complete_task(args.task_id, comment=args.comment))
            elif args.cmd == "reopen":
                _out(board.reopen_task(args.task_id))
            elif args.cmd == "run":
                ns: dict[str, Any] = {"board": board, "result": None}
                exec(args.code, {"__builtins__": __builtins__}, ns)
                _out(ns["result"])
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
