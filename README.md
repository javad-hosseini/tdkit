# tdkit

Project-scoped Todoist API v1 SDK, CLI, and 2-tool Code Mode MCP server built for AI coding agents and engineering teams.

---

## Why `tdkit` Exists

Generic Todoist MCP servers and integrations are designed for personal productivity, not multi-developer software repositories. Using them with AI coding agents introduces several problems:

1. **Tool schema bloat:** Loading 30–50+ MCP tool schemas into an agent's context window wastes thousands of tokens on every turn.
2. **No project boundaries:** A generic Todoist tool has access to *all* your personal and work projects. One wrong query or prompt can read or mutate tasks in unrelated projects.
3. **Secrets in repositories:** Storing API tokens in a repo's `.env` risks leaking credentials and forces all contributors (or agents) to share a single identity.
4. **Multi-step round-trip latency:** Updating 10 tasks via individual tool calls requires 10 separate LLM turns.
5. **Accidental destruction:** Agents shouldn't be able to permanently delete project tasks.

---

## Goal & What It Does

`tdkit` solves these problems by providing a **lightweight, project-scoped Todoist interface** using Cloudflare's **Code Mode** pattern:

- **Project-scoped by default:** Every command and SDK call is strictly bound to the Todoist project declared in the repository's `.todoist.toml`.
- **Zero repo secrets & per-developer identity:** Each developer authenticates once on their machine (`~/.config/tdkit/.env`, mode `0600`). Repositories contain **no** API keys, and every task/comment created by an agent is attributed to the developer running it.
- **2-tool Code Mode MCP (`tdkit-mcp`):** Exposes only `describe_api()` and `execute(code)` instead of dozens of tool schemas, while still giving agents full programmatic control.
- **Single-turn batching (`tdkit run`):** Agents can query, filter, move, and update multiple tasks in a single Python snippet.
- **Safe by design:** Disallows task deletion; supports reading, creating, updating, moving across Kanban sections, commenting, completing, and reopening.

---

## How It Works

### 1. Repository Scoping (`.todoist.toml`)
When you run `tdkit` (or `tdkit-mcp`) anywhere inside a repository, `tdkit` walks upward from the current working directory until it finds `.todoist.toml`. All API operations are automatically scoped to `[project].id`.

### 2. Token Resolution Order
`tdkit` resolves `TODOIST_API_TOKEN` in the following order:
1. `TODOIST_API_TOKEN` environment variable (useful for CI/CD or temporary overrides)
2. `~/.config/tdkit/.env` (created by `tdkit auth <token>` with `0600` permissions)
3. `.env` in the current directory or parent directories (fallback)

### 3. Three Interfaces on One Core (`Board`)
All interfaces wrap `tdkit.client.Board`, a thin `httpx` client over the Todoist API v1 (`https://api.todoist.com/api/v1`):
- **CLI (`tdkit`):** Human- and agent-friendly terminal commands returning clean JSON.
- **Code Mode (`tdkit run "..."`):** Executes a Python snippet with `board` pre-bound to the current repo's `Board` instance and prints `result` as JSON.
- **MCP Server (`tdkit-mcp`):** A FastMCP stdio server exposing `describe_api()` and `execute(code)`.

---

## 1. Installation & Developer Setup

Each developer installs `tdkit` once on their machine using [`uv`](https://docs.astral.sh/uv/):

```bash
# Clone and build the wheel
git clone git@github.com:javad-hosseini/tdkit.git
cd tdkit
uv build

# Install globally (includes CLI `tdkit` and MCP server `tdkit-mcp`)
uv tool install --with mcp ./dist/tdkit-0.1.0-py3-none-any.whl
```

Alternatively, install directly into a project's virtual environment:
```bash
uv pip install /path/to/tdkit/dist/tdkit-0.1.0-py3-none-any.whl
```

### Authenticate Once Per Machine
Save your personal Todoist API token to `~/.config/tdkit/.env`:
```bash
tdkit auth <your_personal_todoist_token>
```

Verify your authenticated identity:
```bash
tdkit whoami
```

---

## 2. Integrating `tdkit` Into Any Project

To enable `tdkit` in any repository, commit **two files** to the root of that repository (no secrets required):

### Step 1: Find your Todoist Project ID
```bash
tdkit projects
```

### Step 2: Create `.todoist.toml` in the project root
```toml
[project]
id = "6hhx7JVPrwqjV2g3"          # From `tdkit projects`
# default_section = "Backlog"    # Optional: set only if the section exists in Todoist

# Optional: friendly aliases -> Todoist section IDs (live sections are also auto-discovered by name)
[sections]
backlog = "6j4RQH2Vvp6p4PJ9"
in_progress = "6j4RQH39cV3xg2Mh"
review = "6j4RQHqC3WJjVPwh"
done = "6j4RQHp739XXp6J9"

# Optional: map teammate shortnames -> Todoist collaborator user IDs
[members]
javad = "36012451"
potato = "56754999"
```

> **Note:** Only set `default_section` if that section actually exists in your Todoist project (run `tdkit sections` to check). If the project has no sections yet, omit or comment out `default_section`.

### Step 3: Add Agent Instructions (`AGENTS.md` / `RULES.md`)
Copy [AGENTS.md](./AGENTS.md) into your repository root (or append it to your project's `RULES.md` / `CLAUDE.md` / `.cursorrules`) so AI coding agents follow the workflow:

```markdown
# Task Management Protocol (Todoist via `tdkit`)

This repository tracks work in Todoist via `tdkit`, automatically scoped to this repo by `.todoist.toml`. Do not call external Todoist MCP servers or raw HTTP requests.

## Commands
- Board overview: `tdkit summary`
- List tasks: `tdkit list [--section "In Progress"] [--label bug]`
- Read task + comments: `tdkit get <task_id>`
- Add task: `tdkit add "<title>" -d "<details>" -s "Backlog" -p <1..4> -l <label>`
- Move section: `tdkit move <task_id> "In Progress"`
- Comment: `tdkit comment <task_id> "<note>"`
- Complete task: `tdkit done <task_id> -c "<summary + commit/PR ref>"`
- Multi-step batch (Code Mode): `tdkit run "result = [board.move_task(t['id'], 'Review') for t in board.list_tasks(section='In Progress')]"`

## Rules
1. **Priority scale:** Todoist API priority is inverted from the UI: `4` = P1 (Urgent), `3` = P2 (High), `2` = P3 (Medium), `1` = P4 (Normal).
2. **Before coding:** Run `tdkit get <task_id>` to read the full description and comments, then move the task to `"In Progress"`.
3. **After coding:** Post a concise comment listing files changed and test results. Move to `"Review"` for teammate review, or run `tdkit done <task_id>` only when explicitly instructed.
4. **Never delete tasks.** If a task is obsolete, comment why and mark it done or ask the Tech Lead.
5. **Batching:** When operating on more than 2 tasks, use a single `tdkit run "..."` Python call instead of looping shell commands.
```

---

## 3. CLI & Code Mode Reference

### CLI Commands
| Command | Description |
| :--- | :--- |
| `tdkit auth <token>` | Save personal Todoist token to `~/.config/tdkit/.env` and verify it |
| `tdkit whoami` | Show current authenticated Todoist user |
| `tdkit projects` | List all accessible Todoist projects and their IDs |
| `tdkit sections` | List sections in the current repository's project |
| `tdkit summary` | Show active tasks grouped by Kanban section |
| `tdkit list [--section S] [--label L]` | List active tasks (optionally filtered) |
| `tdkit get <task_id>` | Get task details and comments |
| `tdkit add "<title>" [-d DESC] [-s SEC] [-p 1..4] [-l LABEL] [-a MEMBER]` | Create a new task |
| `tdkit move <task_id> "<section>"` | Move a task to another section |
| `tdkit comment <task_id> "<note>"` | Add a comment to a task |
| `tdkit done <task_id> [-c "<note>"]` | Mark a task complete (with optional closing comment) |
| `tdkit reopen <task_id>` | Reopen a completed task |
| `tdkit run "<python_code>"` | Execute Python with `board` pre-bound; assign output to `result` |

### `Board` SDK Methods (for `tdkit run` and `tdkit-mcp`)
- `board.list_sections()`
- `board.list_tasks(section=None, label=None)`
- `board.get_task(task_id, include_comments=True)`
- `board.add_task(content, description="", section=None, priority=1, labels=None, assignee=None, due_string=None)`
- `board.update_task(task_id, content=None, description=None, priority=None, labels=None, assignee=None, due_string=None)`
- `board.move_task(task_id, section)`
- `board.complete_task(task_id, comment=None)`
- `board.reopen_task(task_id)`
- `board.get_comments(task_id)`
- `board.comment(task_id, content)`
- `board.summary()`

---

## 4. MCP Server Setup (`tdkit-mcp`)

For MCP-compatible clients (Claude Desktop, Cursor, etc.), register `tdkit-mcp`:

```json
{
  "mcpServers": {
    "todoist": {
      "command": "tdkit-mcp"
    }
  }
}
```

Because your token lives in `~/.config/tdkit/.env` and the project scope lives in each repo's `.todoist.toml`, no environment variables are needed in the MCP client config.

---

## 5. Development & Testing

```bash
# Run unit tests
uv run pytest -v

# Rebuild wheel after changes
uv build
```
