# Installed Pi Extensions

Reference of installed extensions, their tools, and use-cases. Loaded on demand from
`resources/global/AGENTS.md` — not always-loaded context.

## Extension table

| Extension | Tool(s) | Use for |
|-----------|---------|---------|
| `rpiv-advisor` | `advisor()` | Stronger review before complex work, before declaring done, when stuck |
| `pi-subagents` | `subagent` | Delegate to specialized agents (scout, worker, reviewer, sdd-*) |
| `gentle-engram` | `mem_save`, `mem_search`, `mem_context`, `mem_doctor`, `mem_session_summary`, `mem_get_observation` | Canonical durable project memory, decisions, architecture, handoffs |
| `pi-hermes-memory` | `memory`, `memory_search`, `session_search`, `skill` | User preferences, corrections, failures, session history, reusable procedures |
| `pi-web-access` | `web_search`, `code_search`, `fetch_content` | Web research, API docs, library examples |
| `pi-mcp-adapter` | `mcp()` | Query NixOS options via the nixos MCP server |
| `pi-markdown-preview` | `preview_export` | Render markdown/LaTeX as PDF, HTML, or PNG |
| `pi-simplify` | `/simplify` | Review recently changed code for clarity |
| `gentle-pi` | skills (branch-pr, gentle-ai, etc.) | PR creation, release, comment writing, SDD workflows |

## Memory system details

See `docs/MEMORY.md` for additional memory architecture details and the in-memory
vs disk-backed distinction.

## When to add an extension

- A new tool or capability is missing from the table above.
- The extension is declared in `settings/global.json` or an overlay.
- After adding, update this table so `AGENTS.md` can reference it with one line.
