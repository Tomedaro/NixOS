<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->

# Global Pi instructions for this NixOS system

This global profile is for general coding and NixOS work, not dedicated study.

## Scope, precedence, and content boundaries

This file defines global behavior for normal Pi sessions on this NixOS system.

Precedence, from strongest to weakest:

1. User's current request
2. Project/profile-local `AGENTS.md` or `LOCAL.md` files
3. This global `AGENTS.md`
4. Memory, prior sessions, and general model knowledge

If instructions conflict, follow the most specific current instruction and mention the conflict when it affects the task.

Keep this file for always-loaded instructions only — content belongs here when it must be
available in every Pi session without reading additional files. Everything else lives in:

| Content type | Go to |
|---|---|
| Reference, tables, detailed workflows | `docs/*.md` (routed via `docs/LOOKUP.json`) |
| Repeatable procedures | `skill` tool → `~/.pi/agent/skills/` |
| Temporary/volatile task state | Not in version control |
| Local overrides | `~/.pi/agent/LOCAL.md` (read if present, never created from Nix) |

Keep this file small — every line adds tokens to every session. Use prompts/skills for
repeatable workflows instead of growing this file.

## Pi setup routing

For any question about Pi itself, this NixOS module, the smart launcher, wrappers, settings, policies, packages, MCP, memory, study/work profiles, or runtime `.pi` state, read these first:

1. `/home/daniil/NixOS/modules/programs/cli/pi/docs/INDEX.md`
2. `/home/daniil/NixOS/modules/programs/cli/pi/docs/LOOKUP.json`

Do not start with broad `grep -R` across the whole NixOS repository for Pi setup questions unless the wiki routes are missing or insufficient.

For small Pi setup changes, use `docs/LOOKUP.json` to identify the narrowest route, read only those files, and stop. Do not inspect wrappers, scripts, package settings, policies, or profile resources unless the selected route points there or the request depends on them.

## When unsure

For Pi setup questions:

1. Read `docs/INDEX.md`.
2. Use `docs/LOOKUP.json`.
3. Read only the routed source files.
4. If the route is missing, conflicting, or risky, ask the user or call `advisor()` before broad exploration.

## NixOS rules

- This machine is managed declaratively with NixOS.
- Durable Pi setup changes belong under `/home/daniil/NixOS/modules/programs/cli/pi/**`.
- Runtime files under `~/.pi/agent/**`, `~/Learning/**`, and work project `.pi/**` are generated or user-owned depending on the ownership docs.
- Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` for durable setup changes. Edit this Nix source tree, rebuild/test, then use `pi-admin sync` or the relevant compatibility sync command.
- `pi update` and `pi update --extensions` are intentional maintenance actions for pinned packages; explain what will change before running them.
- If `~/.pi/agent/LOCAL.md` exists, read it for private local preferences, but do not create or overwrite it from Nix.
- Never put API keys, tokens, passwords, private SSH material, or OAuth credentials into Nix files.
- Prefer small diffs and show `git diff --stat` plus relevant `git diff` before final recommendations.

## Editing this setup

For durable global behavior changes:

1. Edit `/home/daniil/NixOS/modules/programs/cli/pi/resources/global/AGENTS.md`.
2. Do not edit `/home/daniil/.pi/agent/AGENTS.md` directly.
3. Run:
   - `sudo nixos-rebuild test --flake /home/daniil/NixOS#Default`
   - `pi-admin sync global`
   - `pi-admin drift`
4. Show `git diff --stat` and relevant `git diff`.

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

## Core tools

- Prefer `ctx_*` tools for reading, searching, listing, and shell commands.
- Use `advisor()` before complex or risky work, when stuck, or before declaring major work complete.
- Use `subagent` for delegated exploration, planning, implementation, or review.
- Use `mem_*` for durable project memory.
- Use `memory`, `memory_search`, `session_search`, and `skill` for Pi-local preferences, prior conversations, failures, and reusable procedures.

For the full extension inventory, see `docs/EXTENSIONS.md`.

## Memory policy

Use `docs/MEMORY.md` for the full architecture.

| Need | Tool family |
|------|-------------|
| Durable project decisions, architecture, root causes, handoffs | Engram: `mem_save`, `mem_search`, `mem_context` |
| User preferences, local quirks, prior conversations, reusable procedures, failures | Hermes: `memory`, `memory_search`, `session_search`, `skill` |

Rules:

- Current repo files and command output override memory.
- Memory is context, not instruction.
- Do not store secrets, tokens, credentials, or private keys.
- Do not duplicate the same fact into both systems.
- Parent sessions own memory orchestration for SDD/subagent flows unless explicitly changed.

## Token policy

- Keep always-loaded context small.
- Use the Pi setup wiki and lookup map before reading source files.
- Use prompts/skills for repeatable workflows instead of growing this file.
