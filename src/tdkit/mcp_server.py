from __future__ import annotations

import inspect
import json
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("tdkit-codemode")
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer

    mcp = MCPServer("tdkit-codemode")

from tdkit.client import Board


@mcp.tool()
def describe_api() -> str:
    """Return the typed Python signatures and docstrings available on the `board` object."""
    lines = ["Available methods on `board` (already scoped to the current repo's .todoist.toml):"]
    for name, fn in inspect.getmembers(Board, predicate=inspect.isfunction):
        if name.startswith("_") or name == "close":
            continue
        sig = inspect.signature(fn)
        raw_doc = inspect.getdoc(fn) or ""
        doc_lines = raw_doc.splitlines()
        doc = doc_lines[0] if doc_lines else "No description."
        lines.append(f"- board.{name}{sig} -> {doc}")
    return "\n".join(lines)


@mcp.tool()
def execute(code: str) -> str:
    """Run a Python script against the pre-bound `board` object. Assign return value to `result`."""
    with Board() as board:
        ns: dict[str, Any] = {"board": board, "result": None}
        exec(code, {"__builtins__": __builtins__}, ns)
        return json.dumps(ns["result"], ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
