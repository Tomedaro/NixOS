# Refactor backlog - draft

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
- Current problem: ordinary action authority and TaskNotes promotion authority are coupled through `authorityLevel >= 2`.
- Proposed change:
  - Add explicit capability flags or split authority levels by action class.
  - Default TaskNotes promotion off.
  - Keep ordinary answer/nudge/session/check-in behavior working.
- Acceptance tests:
  - Default config cannot execute `promote_task_proposal`.
  - Ordinary `answer_question`, `ack_nudge`, `snooze_nudge`, `start_recovery_target` still pass.
  - Enabling legacy promotion requires explicit config and is reported in status.

### R-0002 Deprecate legacy/direct TaskNotes mutation surfaces

- Severity: high
- Depends on: R-0001 partly
- Files likely touched:
  - `action-bridge/action_bridge.py`
  - `action-bridge/default.nix`
  - `anki-bridge/anki_bridge.py`
  - `anki-bridge/default.nix`
  - docs: `SAFETY_MODEL.md`, `PROTOCOLS.md`, `ROADMAP.md`
- Current problem:
  - `action-bridge promote_task_proposal` mutates real TaskNotes.
  - `anki-bridge taskNoteMode = direct` mutates real TaskNotes.
- Proposed change:
  - Mark both as legacy/deprecated.
  - Emit warnings when enabled/used.
  - Move templates/examples away from direct promotion.
- Acceptance tests:
  - Direct TaskNotes paths are enumerated in `SAFETY_MODEL.md`.
  - Direct mode status includes warning.
  - Default mode produces proposal/draft only.

### R-0003 Make `dialog-bridge` emit canonical action files for answers/dismissals

- Severity: medium
- Depends on: R-0001 not strictly, but should follow authority split design
- Files likely touched:
  - `dialog-bridge/dialog_bridge.py`
  - `dialog-bridge/default.nix`
  - `tests/dialog_bridge_smoke.py`
  - `tests/action_bridge_smoke.py`
- Current problem: direct answer events bypass action journal/idempotency.
- Proposed change:
  - `dialog-bridge` writes `AI/inbox/actions/<timestamp>_answer-question.json` and `dismiss-question.json`.
  - `action-bridge` remains lifecycle owner.
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

### R-0201 Add first-class read-only TaskNotes context

- Severity: medium
- Depends on: docs current-state clarity
- Current problem: TaskNotes is central, but read-only context should be explicit before applying writes.
- Proposed change:
  - Add bounded read-only TaskNotes context provider.
  - Include active/open commitments, due/scheduled metadata, provenance fields, and limits.
- Acceptance tests:
  - Context provider cannot write TaskNotes.
  - Context facts are bounded and safe for LLM consumption.

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
