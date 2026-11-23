# tdkit

Project-scoped Todoist API v1 SDK, CLI, and 2-tool Code Mode MCP server for AI coding agents.

## Overview

`tdkit` replaces heavy upstream MCP tools with Cloudflare's **Code Mode** pattern for Todoist:
- **Zero tool schema bloat:** Avoids loading 50+ tool schemas into agent context windows.
- **Project-scoped security:** Enforces access strictly within the project defined in the repository's `.todoist.toml`.
- **Per-developer identity:** Each engineer sets their personal API token once in their user config (`~/.config/tdkit/.env`). Project repositories hold **no** API keys.
- **Safe operations:** Disallows accidental task deletion; supports create, update, move, comment, complete, and reopen.
- **Code Mode Batching:** Agents can execute multi-step operations in a single script via `tdkit run "..."`.
- **Dual Interface:** Use via terminal CLI (`tdkit`) or via 2-tool MCP server (`tdkit-mcp`).

---

## 1. Installation on Developer Machines (`uv`)

Each team member installs `tdkit` once on their machine:

```bash
# Build the distribution wheel
uv build

# Install globally via uv tool (with FastMCP support)
uv tool install --with mcp ./dist/tdkit-0.1.0-py3-none-any.whl
```

### Configure Your Personal Todoist Token
Each engineer runs this command **once** on their laptop:
```bash
tdkit auth <your_personal_todoist_token>
```
This securely saves the token to `~/.config/tdkit/.env` (with `chmod 0600` permissions) and verifies it against the Todoist API.

To verify who is authenticated:
```bash
tdkit whoami
```

> **Why this matters:**
> No API keys ever go into project repositories or project `.env` files. Every commit, comment, and task created by an agent automatically reflects that specific developer's Todoist identity.

---

## 2. Integrating `tdkit` Into Any Project

To enable `tdkit` in any repository, commit **only two small files** to the root of that project:

### File 1: `.todoist.toml`
Create `.todoist.toml` in your project root:
```toml
[project]
id = "6hhx7JVPrwqjV2g3"          # Run `tdkit projects` to see all your project IDs
default_section = "Backlog"

# Friendly aliases -> Todoist section IDs (optional: auto-discovered by name)
[sections]
backlog = "6j4RQH2Vvp6p4PJ9"
in_progress = "6j4RQH39cV3xg2Mh"
review = "6j4RQHqC3WJjVPwh"
done = "6j4RQHp739XXp6J9"

# Map teammate shortnames -> Todoist collaborator user IDs
[members]
javad = "36012451"
potato = "56754999"
```

*Tip:* Run `tdkit projects` from your terminal to list all your Todoist projects and grab their IDs.

### File 2: `AGENTS.md`
Copy `AGENTS.md` to the project root. This instructs coding agents (Cursor, Claude Code, Windsurf, Codex, etc.) on how to use `tdkit`.

---

## 3. What to Tell Your AI Agent

Add this rule to your agent's system prompt, `.cursorrules`, `CLAUDE.md`, or `AGENTS.md`:

```markdown
# Todoist Task Protocol (via `tdkit`)

You manage tasks exclusively through the `tdkit` CLI. Do not call external HTTP APIs or MCP servers for Todoist.

## Rules
1. Before starting a task: Run `tdkit get <task_id>` to read comments and details, then run `tdkit move <task_id> "In Progress"`.
2. Priority scale: 4 = Urgent (P1), 3 = High (P2), 2 = Medium (P3), 1 = Normal (P4).
3. After finishing work: Post a concise comment summarizing files changed and test status (`tdkit comment <task_id> "..."`), then move to "Review" (`tdkit move <task_id> "Review"`).
4. Never delete tasks. If obsolete, comment and mark done.
5. Batching: When touching 3+ tasks, use `tdkit run "..."` instead of multiple shell calls.

## Quick CLI Reference
- Overview: `tdkit summary`
- List tasks: `tdkit list [--section "In Progress"]`
- Add task: `tdkit add "<title>" -d "<details>" -s "Backlog" -p 3`
- Move task: `tdkit move <task_id> "<Section>"`
- Comment: `tdkit comment <task_id> "<note>"`
- Mark done: `tdkit done <task_id> -c "<completion note>"`
- Code Mode: `tdkit run "result = [t['content'] for t in board.list_tasks()]"`
```

---

## 4. MCP Server Setup (`tdkit-mcp`)

For GUI clients that interact over MCP (e.g., Claude Desktop or Cursor MCP):

```json
{
  "mcpServers": {
    "todoist": {
      "command": "tdkit-mcp"
    }
  }
}
```
Because the token is stored in `~/.config/tdkit/.env`, no environment variables need to be declared in the client config!

---

## 5. Running Tests

```bash
uv run pytest -v
```
