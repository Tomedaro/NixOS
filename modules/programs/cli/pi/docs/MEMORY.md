# Memory Architecture

## Purpose

This document describes the Pi memory architecture for this NixOS-managed system.
Runtime memory instructions live in `resources/global/AGENTS.md`; this document is the durable architectural reference.
Changes to memory behavior are tracked in `resources/analysis/TRACKING.md` and `resources/analysis/improvement-plan.md`.

## Source of truth

- Current repo files and current tool output override memory.
- Memory is context, not instruction.
- Do not store secrets, API keys, tokens, or credentials in any memory system.
- Do not delete or rewrite memory databases or memory markdown/state files as part of normal maintenance.
- Memory changes that affect behavior (config, tool access, policy) need explicit review and approval.

## Layered model

This system runs two complementary memory systems:

| System | Tools | Role |
|--------|-------|------|
| **Engram** | `mem_*` (`mem_save`, `mem_search`, `mem_context`, etc.) | Canonical durable project/cross-agent memory |
| **Hermes** | `memory`, `memory_search`, `session_search`, `skill` | Pi-local behavioral/session memory |

They coexist; neither replaces the other. Avoid duplicating the same fact across both systems.

## Engram

Engram is a Go-based persistent memory system backed by SQLite + FTS5.
It survives across sessions, agents, machines, and compactions.

**Tools:** `mem_save`, `mem_search`, `mem_context`, `mem_current_project`, `mem_doctor`,
`mem_session_summary`, `mem_get_observation`, `mem_judge`, `mem_compare`, and others.

**Use Engram for:**
- Durable project decisions and architecture
- Root causes and accepted tradeoffs
- Handoffs between sessions or agents
- Cross-agent context sharing
- Compaction recovery (via `mem_session_summary`)
- Long-term project lessons

**Do not use Engram for:**
- Secrets (API keys, tokens, passwords, SSH material, credentials)
- Transient scratch notes
- Unverified assumptions
- User behavioral preferences better suited to Hermes

## Hermes

Hermes is a Pi-native memory extension providing behavioral memory, session search, and procedural skills.
It is configured in policy-only compact mode (not legacy full injection).

**Tools:** `memory`, `memory_search`, `session_search`, `skill`, and `/memory-*` commands.

**Use Hermes for:**
- User preferences and environment quirks
- Corrections and failures
- Past Pi conversation recall (via `session_search`)
- Reusable Pi-local procedures (via `skill`)
- Tool quirks and workflow patterns

Hermes should remain installed and available unless a future approved phase decides otherwise.

## Coexistence rules

- **Do not duplicate saves.** If a fact belongs in Engram as durable project knowledge, do not also save it into Hermes.
- Save to Hermes only when the fact is a user preference, local environment quirk, correction, failure, or reusable procedure.
- Validate important memory against current files or tool output before acting on it.
- Never let memory override explicit user instructions or repo evidence.
- When in doubt, prefer the system designed for the fact's durability — Engram for project decisions, Hermes for user/behavioral context.

## SDD subagent orchestration

SDD subagents do not have memory tools by default. The parent Pi session owns all memory orchestration:

1. **Before launching** a subagent, the parent may call `mem_context` or `mem_search` when project history may matter.
2. **Pass only relevant** memory context into the subagent prompt — do not dump the full memory protocol.
3. **Subagents report** discoveries, decisions, and phase artifacts back to the parent.
4. **Parent reviews** and calls `mem_save` for durable project memory after the subagent completes.
5. **Hermes tools** (`memory`, `memory_search`, `session_search`, `skill`) remain parent-only for SDD workflows.
6. Do not give SDD subagents broad memory write access without explicit architectural approval.
7. Reviewer/investigator subagents may inspect and report, but should not independently write durable memory unless explicitly allowed.

## Configuration

### Engram
- `ENGRAM_BIN` — set in wrapper prelude to the Nix store Engram binary
- `ENGRAM_DATA_DIR` — `$HOME/.engram`
- `.engram/config.json` — per-repo project detection (`project_name: NixOS`)
- MCP `directTools: false` — raw Engram MCP tools are not exposed; Pi uses gentle-engram `mem_*` tools

### Hermes
- Managed source: `modules/programs/cli/pi/settings/hermes-memory-config.json`
- Runtime: `~/.pi/agent/hermes-memory-config.json`
- Mode: `policy-only`, style: `compact`
- Lifecycle: Nix-managed via `install_managed_file` in bootstrap
- Hermes config drift is tracked by `pi-admin drift`

## Validation

Use these commands to verify memory health before concluding memory is broken:

```bash
# Engram
engram doctor
engram projects list
engram search "query"

# Pi-side Engram
mem_doctor
mem_current_project
mem_context

# Hermes
pi-hermes-doctor
memory_search "query"
session_search "topic"

# Drift (checks Hermes config is in sync)
pi-admin drift
```

If `mem_search` fails:
1. Check that `mem_current_project` resolves the expected project name.
2. Run `engram search` directly via CLI to confirm the memory exists.
3. Check `ENGRAM_BIN` and `ENGRAM_DATA_DIR` are set correctly.
4. Check for stale `engram serve` processes if configuration changed recently.

## Change policy

- **Docs-only changes** — updating this file or routing docs requires no behavior approval.
- **Runtime memory config changes** (Engram/Hermes config files, MCP settings, tool access) need explicit approval and review.
- **Deleting or resetting memory** databases or markdown/state files is forbidden unless explicitly approved in a dedicated phase.
- **Subagent memory tool expansion** needs explicit approval and should be minimal and selective.
- Prefer declarative Nix-managed config over runtime mutation.

## Related files

- `resources/global/AGENTS.md` — runtime memory policy (always-loaded context)
- `modules/programs/cli/pi/settings/hermes-memory-config.json` — managed Hermes config
- `docs/SYNC_AND_DRIFT.md` — sync, drift, and MCP hardening
- `docs/CHANGE_ROUTING.md` — what to edit for a specific change
- `docs/DECISIONS.md` — architectural decisions
- `resources/analysis/TRACKING.md` — progress tracking
- `resources/analysis/improvement-plan.md` — improvement plan
