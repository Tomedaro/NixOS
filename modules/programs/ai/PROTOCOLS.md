# Protocols

This document is the canonical orientation for AI vault paths and protocol ownership. Detailed schema inventory lives in [docs/SCHEMA_REGISTRY.md](./docs/SCHEMA_REGISTRY.md).

Status values: **current**, **transitional**, **legacy**, **planned**, **evidence-only**.

## Queue and ingress paths

| Path | Status | Primary writer | Primary reader | Purpose |
| --- | --- | --- | --- | --- |
| `AI/inbox/actions/*.json` | current | bounded UI/bridge producers | `action-bridge` | Canonical intentional live-action queue. |
| `AI/inbox/actions-processed/YYYY-MM-DD/*` | current | `action-bridge` | diagnostics/humans | Successfully processed action archive. |
| `AI/inbox/actions-failed/YYYY-MM-DD/*` | current | `action-bridge` | diagnostics/humans | Failed action archive. |
| `AI/inbox/actions-manual-review/YYYY-MM-DD/*` | current | `action-bridge` | human review | Ambiguous/replay/conflict actions requiring review. |
| `AI/inbox/from-phone/events/*.json` | current telemetry | Tasker/phone telemetry | `phone-bridge` | Passive phone telemetry; not intentional commands. |
| `AI/inbox/from-phone/processed/YYYY-MM-DD/*` | current | `phone-bridge` | diagnostics | Processed phone telemetry archive. |
| `AI/inbox/from-phone/failed/YYYY-MM-DD/*` | current | `phone-bridge` | diagnostics | Rejected/failed telemetry archive. |
| `AI/inbox/from-desktop/events/*.json` | current | desktop/coach producers | context/diagnostics | Desktop event evidence. |
| `AI/inbox/obsidian/messages/*.json` | current | Obsidian ingress | intent/proposal processors | Bounded Obsidian intents/messages. |
| `AI/inbox/obsidian/actions/*.json` | current | Obsidian review controls | proposal action/approval bridge | Approve/reject/revise records; not the live action queue. |
| `AI/inbox/session-requests/*` | transitional/legacy | older producers | diagnostics/session tooling | Historical request path; new intentional actions should use `AI/inbox/actions`. |
| `AI/inbox/from-obsidian/*` | legacy | none in current Python flow | diagnostics only | Must not become a new active protocol dependency. |

## Outbox and review paths

| Path | Status | Purpose |
| --- | --- | --- |
| `AI/outbox/to-phone/current-nudge.{json,md}` | current projection | Current phone-facing nudge. |
| `AI/outbox/to-phone/current-question.{json,md}` | current projection | Current phone-facing question. |
| `AI/outbox/to-phone/interaction-state.json` | current projection | Materialized phone interaction state. |
| `AI/outbox/to-desktop/*` | current/adapter-specific | Desktop-facing artifacts. |
| `AI/outbox/to-obsidian/current-proposal.{json,md}` | current | Latest reviewable proposal. |
| `AI/outbox/to-obsidian/proposals/*` | current | Proposal history/artifacts. |
| `AI/outbox/to-obsidian/current-approved-proposal.{json,md}` | current | Latest reviewed/approved proposal. |
| `AI/outbox/to-obsidian/approved-proposals/*` | current | Reviewed proposal artifacts. |
| `AI/outbox/to-obsidian/current-task-draft.{json,md}` | current | Latest TaskNotes-compatible draft. |
| `AI/outbox/to-obsidian/task-drafts/*` | current | Reviewable task drafts; never equivalent to real TaskNotes. |
| `AI/proposed-tasks/*.md` | current but ownership unresolved | Older planner/Anki proposal surface. Do not introduce new semantics here until proposal-surface ownership is decided. |

## State, reports, and evidence

| Path | Status | Purpose |
| --- | --- | --- |
| `AI/state/action-bridge/*` | current | Action processing journal/cache/status. |
| `AI/state/session/*` | current | Session materialized state. |
| `AI/state/phone/*` | current | Phone bridge and generated UI state. |
| `AI/state/desktop/*` | current | Desktop/coach state. |
| `AI/state/shared/*` | current | Shared coordination state. |
| `AI/state/llm/*` | current/older planner | Planner state. |
| `AI/state/agent/*`, context-hub artifacts | current | Bounded context/agent snapshots. |
| `AI/state/anki/status.json` and compatibility state | current | Anki context snapshot. |
| recovery/intervention/interaction state under `AI/state/**` | current | Materialized lifecycle and outcome views. |
| `AI/control/*` | current human-editable | Current task/block/mode and compiled session controls. |
| `AI/policy/*` | current human-editable | App/domain/proof/retention and future policy inputs. |
| `AI/reports/blocks/*`, `daily/*`, `weekly/*` | current/older planner | Human-readable reports. |
| `AI/reflections/*` | current | Human/model reflection artifacts. |
| `AI/events/**/*.jsonl` | evidence-only | Append evidence. Not authoritative audit storage yet. |
| action/approval/validation result JSON artifacts | current evidence | Deterministic processing results and review provenance. |

## External durable surface

| Path | Status | Rule |
| --- | --- | --- |
| `TaskNotes/` | current external commitment surface | Humans and a future deterministic reviewed apply path only. |
| `TaskNotes/Tasks` | common configured subdirectory | Current AI paths must not write here directly. |
| `TaskNotes/AI` | current initialization/support directory | Created by vault initialization; not a bypass for durable task mutation rules. |

## Current TaskNotes protocol status

Implemented:

```text
obsidian_intent.v1
  -> obsidian_proposal.v1
  -> obsidian_proposal_action.v1
  -> obsidian_reviewed_proposal.v1
  -> obsidian_task_draft.v1
  -> tasknotes_apply_validation_result.v1
```

Not implemented:

```text
tasknotes_apply_request
  -> atomic TaskNotes mutation
  -> authoritative apply result/journal
```

A validation result is not an apply result.


## Task-initiation first-loop paths

Authoritative transactional state must remain laptop-local, outside the synchronized Obsidian vault. Human-readable and phone-facing artifacts may be projected into the vault.

|Path base|Planned path|Contract/content|Writer|Reader and authority|
|---|---|---|---|---|
|`$XDG_STATE_HOME`|Milestone 2-selected laptop-local state|authoritative future interaction/run/context/proposal/card/queue/response/idempotency state|Milestone 2 laptop kernel|kernel and local diagnostics; temporary/structural local authority|
|vault `AI/`|`outbox/to-phone/task-initiation/cards/<card_id>.json`|exact `task_initiation_card.v1` projection|future kernel card projection|Milestone 3 Tasker adapter; display/response only|
|vault `AI/`|`outbox/to-phone/task-initiation/current-card.json`|exact current card; absent before any card|future kernel card projection|Tasker adapter; projection, never authority|
|vault `AI/`|`events/task-initiation/YYYY-MM-DD.jsonl`|event.v1 transition evidence only; not a task_initiation-specific schema|future kernel|diagnostics/reporter; evidence-only, never authority|

These paths are planned. No directory, database, service, or artifact is created by Milestone 1. The laptop-local state path is resolved relative to `XDG_STATE_HOME` (normally `~/.local/state`), not the vault.
Receipt transport and delivery path are Milestone 3 provisional.

Do not reuse `AI/inbox/actions`, `AI/inbox/from-phone/events`, `current-nudge.json`, or `interaction-state.json` for authoritative first-loop state.

## Action queue rules

- Action files are explicit JSON objects with stable identity/idempotency data where possible.
- Producers must write temporary/partial files safely; consumers wait for stable files and ignore editor/swap artifacts.
- `action-bridge` owns live action dispatch and capability checks.
- Processed/failed/manual-review paths preserve the source action for diagnosis.
- Stale or ambiguous processing journals must not be replayed automatically.
- Dangerous actions must not inherit authority merely because a low-risk action shares the same queue.

## Schema lifecycle rules

Every behavioral schema should be listed in `docs/SCHEMA_REGISTRY.md` with:

- schema name and version;
- status and owner module;
- purpose and primary producer/consumer;
- whether it is command, state, projection, proposal, validation, event, or report;
- side-effect implications;
- migration/compatibility notes.

Source code remains authoritative for exact fields until generated schemas are introduced. Adding or changing a schema without updating the registry is documentation drift.
