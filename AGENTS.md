# Task Management Protocol (Todoist via `tdkit`)

This repository tracks work in Todoist via the local `tdkit` package, automatically scoped to this repo by `.todoist.toml`. Do not call external Todoist MCP servers or raw HTTP requests.

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
