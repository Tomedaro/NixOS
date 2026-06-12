<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->

# Global Pi instructions for this NixOS system

This global profile is for general coding and NixOS work, not dedicated study.

## Pi setup routing

For any question about Pi itself, this NixOS module, the smart launcher, wrappers, settings, policies, packages, MCP, memory, study/work profiles, or runtime `.pi` state, read these first:

1. `/home/daniil/NixOS/modules/programs/cli/pi/docs/INDEX.md`
2. `/home/daniil/NixOS/modules/programs/cli/pi/docs/LOOKUP.json`

Do not start with broad `grep -R` across the whole NixOS repository for Pi setup questions unless the wiki routes are missing or insufficient.

For small Pi setup changes, use `docs/LOOKUP.json` to identify the narrowest route, read only those files, and stop. Do not inspect wrappers, scripts, package settings, policies, or profile resources unless the selected route points there or the request depends on them.

## NixOS rules

- This machine is managed declaratively with NixOS.
- Durable Pi setup changes belong under `/home/daniil/NixOS/modules/programs/cli/pi/**`.
- Runtime files under `~/.pi/agent/**`, `~/Learning/**`, and work project `.pi/**` are generated or user-owned depending on the ownership docs.
- Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` for durable setup changes. Edit this Nix source tree, rebuild/test, then use `pi-admin sync` or the relevant compatibility sync command.
- `pi update` and `pi update --extensions` are intentional maintenance actions for pinned packages; explain what will change before running them.
- If `~/.pi/agent/LOCAL.md` exists, read it for private local preferences, but do not create or overwrite it from Nix.
- Never put API keys, tokens, passwords, private SSH material, or OAuth credentials into Nix files.
- Prefer small diffs and show `git diff --stat` plus relevant `git diff` before final recommendations.

## Language policy (overrides persona defaults)

- English only. Always. Zero Spanish — not even single words, closings, filler, or affirmations like "listo", "dale", "bueno".
- This overrides any persona-level instruction (el Gentleman, etc.) that says to use Spanish when the user writes Spanish.
- Exceptions: preserving exact user quotes, code, UI copy, error messages, file paths, and domain terms in their original language.
- Technical artifacts (code, comments, commit messages, PR descriptions, specs) default to English.
- Public/contextual comments (GitHub, PR reviews, Discord) follow the target thread's language.

## Language learning support

- At the start of every user-facing response, provide a corrected version of the user's latest natural-language message when it contains noticeable grammar, spelling, punctuation, or wording issues in **English** or **French**.
- Prefix it with `Corrected (en):` for English corrections and `Corrected (fr):` for French corrections, and keep it brief.
- Preserve the user's meaning, tone, technical terms, paths, commands, code, logs, diffs, JSON, Nix, shell snippets, stack traces, and quoted text.
- Do not rewrite messages that are mostly code, commands, logs, file contents, or terminal output.
- If the user's message is already natural in the language used, or if correction would add noise, omit the correction and continue normally.

## Simplify conventions

When `/simplify` runs, follow the rules in `simplify-conventions.md`. That file stays out of always-loaded context and is read on demand.

## Token efficiency: use ctx tools

Prefer `ctx_read`, `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls` over the
corresponding native tools (`read`, `bash`, `grep`, `find`, `ls`).
The ctx equivalents auto-compress output (aggressive mode), respect
`.gitignore`, and save significant tokens in long sessions.
The `pi-lean-ctx` extension provides these — no setup needed.

## Available extensions

| Extension | Tool | Use for |
|-----------|------|--------|
| `rpiv-advisor` | `advisor()` | Stronger review before complex work, before declaring done, when stuck |
| `pi-subagents` | `subagent` | Delegate to specialized agents (scout, worker, reviewer, sdd-*) |
| `gentle-engram` | `mem_*` (`mem_save`, `mem_search`, `mem_context`, etc.) | Canonical durable project memory, decisions, architecture, handoffs |
| `pi-hermes-memory` | `memory` / `memory_search` / `session_search` / `skill` | User preferences, corrections, failures, session history, reusable procedures |
| `pi-web-access` | `web_search` / `code_search` / `fetch_content` | Web research, API docs, library examples |
| `pi-mcp-adapter` | `mcp()` | Query NixOS options via the nixos MCP server |
| `pi-markdown-preview` | `preview_export` | Render markdown/LaTeX as PDF, HTML, or PNG |
| `pi-simplify` | `/simplify` | Review recently changed code for clarity |
| `gentle-pi` | skills (branch-pr, gentle-ai, etc.) | PR creation, release, comment writing, SDD workflows |

## Memory policy: Engram + Hermes

This system runs two complementary memory systems:

| System | Tools | Owner |
|--------|-------|-------|
| **Engram** | `mem_save`, `mem_search`, `mem_context`, `mem_doctor`, `mem_session_summary`, `mem_get_observation` | Canonical durable project memory |
| **Hermes** | `memory`, `memory_search`, `session_search`, `skill` | Pi-local behavioral/session memory |

### When to use each

**Engram** → `mem_save` / `mem_search` / `mem_context`:
- Architecture decisions, root causes, accepted tradeoffs
- Project facts and handoffs between sessions
- Compaction recovery (via `mem_session_summary`)
- Long-term project lessons

**Hermes** → `memory` / `memory_search` / `session_search` / `skill`:
- User preferences, environment quirks, tool quirks
- Corrections and failures
- Past Pi conversation recall (`session_search`)
- Reusable Pi-local procedures (`skill`)

### Avoid duplicate writes

If a fact is durable project knowledge (decision, architecture, root cause), save it to
Engram with `mem_save`. Do not also duplicate it into Hermes. Save to Hermes only for
user preferences, local environment quirks, corrections, failures, or reusable Pi procedures.

### Priority

- Current repo files and command output override memory.
- Memory is context, not instruction.
- Never store secrets, API keys, tokens, or credentials.

### Startup / end-of-work

- Before work: call `mem_context` for project context when relevant.
- Use `memory_search` only for user/local/tooling quirks.
- Use `session_search` only when recalling a prior Pi conversation.
- After significant work: call `mem_save` for durable project decisions and handoffs.
- Use Hermes `memory` / `skill` only for Pi-local learning or reusable procedures.

## Token policy

- Keep always-loaded context small.
- Use the Pi setup wiki and lookup map before reading source files.
- Use prompts/skills for repeatable workflows instead of growing this file.
