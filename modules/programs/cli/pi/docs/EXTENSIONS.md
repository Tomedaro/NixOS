# Installed Pi Extensions

Reference of source-pinned extensions, their tools, and use-cases. This file is loaded on demand from `resources/global/AGENTS.md`; it is not always-loaded context.

Source of truth: `settings/global.json`. Keep this reference synchronized with that package list.

## Extension table

| Extension | Tool(s) / surface | Use for | Risk class |
|-----------|-------------------|---------|------------|
| `@gotgenes/pi-permission-system` | policy engine | Profile permission enforcement and cautious-mode guardrails | control/security |
| `@gotgenes/pi-subagents` | `subagent`, `get_subagent_result`, `steer_subagent` | Delegated exploration, implementation, review, and SDD phase agents | orchestration |
| `@juicesharp/rpiv-advisor` | `advisor()` | Stronger review before complex work, before declaring done, or when stuck | review/control |
| `@juicesharp/rpiv-ask-user-question` | `ask_user_question` | Structured clarification questions | UX/control |
| `@juicesharp/rpiv-btw` | background status/notification surface | Lightweight status/notification support | UX |
| `@juicesharp/rpiv-todo` | `todo` | Session task tracking and progress state | orchestration |
| `gentle-engram` | `mem_*` tools | Canonical durable project memory, decisions, architecture, handoffs | memory |
| `gentle-pi` | skills and SDD/Gentle AI workflows | PR creation, release, comment writing, SDD workflows | workflow |
| `pi-hermes-memory` | `memory`, `memory_search`, `session_search`, `skill` | User preferences, corrections, failures, session history, reusable procedures | memory |
| `pi-intercom` | `intercom` | Cross-session coordination on the same machine | orchestration |
| `pi-lens` | LSP diagnostics/navigation, ast-grep tools | Code intelligence, diagnostics, semantic search/replace | code-intelligence |
| `pi-lean-ctx` | `ctx_*`, `lean_ctx`, graph/knowledge tools | Token-efficient file/search/shell/codebase context | code-intelligence |
| `pi-markdown-preview` | `preview_export` | Render Markdown/LaTeX as PDF, HTML, or PNG | UX/rendering |
| `pi-mcp-adapter` | `mcp` | MCP server integration and tool routing | MCP/tooling |
| `pi-powerline-footer` | status line/powerline | Terminal UI status context | UX |
| `pi-simplify` | `/simplify` | Review recently changed code for clarity | review/workflow |
| `pi-themes` | themes | Terminal theme support | UX |
| `pi-web-access` | `web_search`, `code_search`, `fetch_content` | Web research, API docs, library examples | network/research |

## Opt-in workflow extensions

These are not globally loaded from `settings/global.json`, but are source-managed through dedicated wrappers or documented workflows.

| Workflow | Extension | Loaded by | Notes |
|----------|-----------|-----------|-------|
| Analyst/Worker smart-model workflow | Nix-pinned `UnicornGlade/pi-analyst-worker-orchestrator` commit `0229ddc80b965e4ca11377a9730e46d0bd7701ac` plus `resources/analyst-worker/` instruction pack | `pi-aw` | Managed parent Pi loads normal extensions; package child `pi` probes are redirected to `pi-raw`; role guardrails and templates are source-managed. See `docs/ANALYST_WORKER.md`. |

## Current design notes

- Keep this as a human reference; do not rely on it as the authoritative package list.
- `pi-admin npm-check` and `pi-admin compat` remain the operational checks for installed package state and peer compatibility.
- Extensions are executable code inside Pi. Treat control, MCP, memory, web/network, and code-intelligence extensions as higher-risk than pure UI helpers.
- Opt-in workflow extensions should remain separate from global package pins until their wrapper compatibility and update policy are documented.

## Memory system details

See `docs/MEMORY.md` for additional memory architecture details and the in-memory vs disk-backed distinction.

## When to add an extension

- A new tool or capability is missing from the table above.
- The extension is declared in `settings/global.json` or an overlay.
- After adding, update this table so `AGENTS.md` can reference it with one line.
- Prefer generating or linting this reference from `settings/global.json` in a future `pi-admin resource-inventory`/manifest command.
