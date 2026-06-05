# Refactor backlog - draft

> Superseded status: later patches disabled the previously identified direct TaskNotes mutation paths. `36f5813` removed/hard-disabled Anki direct TaskNotes mode, and `ac274a9` disabled action-bridge `promote_task_proposal`. Reviewable proposal/draft paths remain; deterministic TaskNotes apply/promote is still future work.

This file records the accepted audit draft for `modules/programs/ai/docs/REFACTOR_BACKLOG.md`.

## Priority 0 - must precede richer agent behavior

### R-0001 Split/lower broad action authority

- Severity: high
- Depends on: none
- Files likely touched:
  - `modules/programs/ai/default.nix`
  - `modules/programs/ai/action-bridge/default.nix`
  - `modules/programs/ai/action-bridge/action_bridge.py`
  - `modules/programs/ai/tests/action_bridge_smoke.py`
- Resolved by ac274a9: `promote_task_proposal` is disabled, so ordinary action authority no longer enables TaskNotes promotion.
- Proposed change:
  - Add explicit capability flags or split authority levels by action class.
  - Done by ac274a9: action TaskNotes promotion is disabled and legacy promotion option/env wiring was removed.
  - Keep ordinary answer/nudge/session/check-in behavior working.
- Acceptance tests:
  - Done by ac274a9: `promote_task_proposal` is disabled.
  - Ordinary `answer_question`, `ack_nudge`, `snooze_nudge`, `start_recovery_target` still pass.
  - Enabling legacy promotion requires explicit config and is reported in status.

### R-0002 Completed - Legacy/direct TaskNotes mutation surfaces removed or disabled

- Severity: high
- Depends on: R-0001 partly
- Files likely touched:
  - `action-bridge/action_bridge.py`
  - `action-bridge/default.nix`
  - `anki-bridge/anki_bridge.py`
  - `anki-bridge/default.nix`
  - docs: `SAFETY_MODEL.md`, `PROTOCOLS.md`, `ROADMAP.md`
- Current problem:
  - Resolved by ac274a9: `action-bridge promote_task_proposal` is disabled and no longer mutates real TaskNotes.
  - Resolved by 36f5813: Anki direct TaskNotes mode is removed/hard-disabled.
- Proposed change:
  - Mark both as legacy/deprecated.
  - Emit warnings when enabled/used.
  - Move templates/examples away from direct promotion.
- Acceptance tests:
  - Updated current truth: direct TaskNotes mutation paths are removed or disabled; future writes require deterministic apply/promote.
  - Direct mode status includes warning.
  - Default mode produces proposal/draft only.

### R-0003 Resolved by dd4450a: make `dialog-bridge` emit canonical action files for answers

- Severity: medium
- Depends on: R-0001 not strictly, but should follow authority split design
- Files likely touched:
  - `dialog-bridge/dialog_bridge.py`
  - `dialog-bridge/default.nix`
  - `tests/dialog_bridge_smoke.py`
  - `tests/action_bridge_smoke.py`
- Historical problem: before dd4450a, dialog answer handling skipped action journal/idempotency.
- Current status:
  - Resolved by dd4450a: desktop answers queue `answer_question` action files under `AI/inbox/actions`.
  - `action-bridge` remains lifecycle owner and processes queued `answer_question` and `dismiss_question` actions.
- Remaining follow-up:
  - Add a real dismiss UI signal before emitting `dismiss_question`.
- Acceptance tests:
  - Dialog answer creates action file only.
  - Action bridge processes answer and updates `last-answer`, current question, interaction state, and event logs.

## Priority 1 - documentation truth surface

### R-0101 Generate canonical current-state docs

- Severity: medium
- Depends on: audit review approval
- Files to create/update:
  - `CURRENT_STATE.md`
  - `MODULES.md`
  - `SAFETY_MODEL.md`
  - `PROTOCOLS.md`
  - `OPERATIONS.md`
  - `ROADMAP.md`
  - `GLOSSARY.md`
  - `docs/REVIEW_INVENTORY.md`
  - `docs/MODULE_REVIEW_REGISTER.md`
  - `docs/ARCHITECTURE_FINDINGS.md`
  - `docs/REFACTOR_BACKLOG.md`
  - `docs/DOC_RESTRUCTURE_PLAN.md`
- Proposed change:
  - Use the read-only audit package as the starting point.
  - Keep `README.md` orientation-only.
- Acceptance checks:
  - Every source module appears in `MODULES.md`.
  - Every current queue path appears in `PROTOCOLS.md`.
  - Every side-effecting path appears in `SAFETY_MODEL.md`.
  - Every planned item appears in `ROADMAP.md`.
  - Every known legacy path is marked legacy/deprecated.

### R-0102 Add ADRs

- Severity: docs-only / medium future safety
- Depends on: R-0101
- Files to create:
  - `docs/adr/0001-local-first-ai-vault.md`
  - `docs/adr/0002-obsidian-review-surface.md`
  - `docs/adr/0003-tasknotes-human-commitment-surface.md`
  - `docs/adr/0004-llm-proposal-only-boundary.md`
  - `docs/adr/0005-split-action-authority.md`
  - `docs/adr/0006-tasknotes-apply-promote-gate.md`
- Acceptance checks:
  - Each ADR has status/context/decision/consequences/alternatives/follow-up tasks.

## Priority 2 - TaskNotes apply/promote gate

### R-0201 Completed - read-only TaskNotes context contract and provider

- Severity: medium
- Depends on: docs current-state clarity and the Markdown-only module contract pressure test
- Completed status:
  - `tasknotes.read_context` is documented and implemented as a read-only context provider.
  - It reads bounded TaskNotes source paths and writes only bounded AI context output/artifacts.
  - It declares `may_mutate_tasknotes: false` and `required_action_capabilities: none`.
  - It emits provenance, freshness, source limits, truncation/omission markers, and safe-off/disabled behavior.
  - `context_hub` exposes compact provider metadata for downstream consumers.
  - `llm_prompt_package.v1` may include compact `context.tasknotes_read_context` metadata derived from `context_hub`.
  - Prompt-facing metadata omits raw TaskNotes content, absolute TaskNotes source roots, and provider `source_paths`.
  - Future deterministic TaskNotes apply/promote remains separate planned work.
- Acceptance tests:
  - Contract states no action-bridge runtime action capability is required.
  - Provider tests prove no TaskNotes writes.
  - Provider tests prove bounded/provenanced output, freshness fields, limit handling, and safe-off/disabled behavior.
  - Context-hub and LLM prompt tests prove bounded metadata consumption without TaskNotes writes or live action capability requirements.

### R-0202 Implement deterministic TaskNotes apply/promote gate

- Severity: high
- Depends on: R-0001, R-0002, R-0201
- Proposed change:
  - A dedicated gate consumes reviewed task draft artifacts and explicit human approval.
  - Gate writes real TaskNotes only after deterministic validation.
  - It emits explicit events and idempotency records.
- Acceptance tests:
  - Unapproved draft is refused.
  - Direct execution fields are refused.
  - Duplicate apply is idempotent/manual-review safe.
  - Writes only under configured `TaskNotes` root.

### R-0203 Add TaskNotes apply schemas/events/tests

- Severity: high
- Depends on: R-0202
- Proposed change:
  - Add schema names and JSON examples to `PROTOCOLS.md`.
  - Add events under `AI/events/tasknotes` with clear status.
  - Add smoke tests for accepted/refused/manual-review cases.

## Priority 3 - agent quality and workflow expansion

### R-0301 Richer goal/preference/policy contracts

- Severity: medium
- Depends on: stable protocols and TaskNotes boundaries.

### R-0302 ActivityWatch context integration into agent context

- Severity: medium
- Depends on: context provider design.

### R-0303 Daily planning/review workflows

- Severity: medium
- Depends on: TaskNotes apply gate and current-state docs.

### R-0304 Durable agent run logs

- Severity: medium
- Depends on: event logging decision.
- Proposed change:
  - Create per-run records with input context refs, prompt package refs, output refs, validation result, and human decision refs.

### R-0305 Richer LLM planner behavior

- Severity: low/medium
- Depends on: safe action/TaskNotes gates.

### R-0306 Desktop popup UI

- Severity: low
- Depends on: protocol/lifecycle becoming boring and stable.
