# Review inventory - draft

> Superseded status: later patches disabled the previously identified direct TaskNotes mutation paths. `36f5813` removed/hard-disabled Anki direct TaskNotes mode, and `ac274a9` disabled action-bridge `promote_task_proposal`. Reviewable proposal/draft paths remain; deterministic TaskNotes apply/promote is still future work.

This file records the accepted audit draft for `modules/programs/ai/docs/REVIEW_INVENTORY.md`.

## Review basis

Ground truth was established from:

- source code under `modules/programs/ai/**/*.py`;
- Nix modules under `modules/programs/ai/**/*.nix`;
- tests under `modules/programs/ai/tests/*_smoke.py`;
- dev scripts under `modules/programs/ai/dev/*.sh` and `modules/programs/ai/dev/*.py`;
- existing docs: `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `TODO.md`, `AI_DEBUG_REFACTORING_TODO.md`, component READMEs, shared Python README;
- supplied generated audit/live files under `ai-doc-audit-input/`;
- git status/log snapshots in `ai-doc-audit-input/`.

## Files reviewed

Top-level AI docs and config:

- `modules/programs/ai/default.nix`
- `modules/programs/ai/core/default.nix`
- `modules/programs/ai/vault-bridge/default.nix`
- `modules/programs/ai/README.md`
- `modules/programs/ai/ARCHITECTURE.md`
- `modules/programs/ai/DEVELOPMENT.md`
- `modules/programs/ai/TODO.md`
- `modules/programs/ai/AI_DEBUG_REFACTORING_TODO.md`
- `modules/programs/ai/AI_DOC_AUDIT_HANDOFF.md`

Runtime service modules:

- `action-bridge/action_bridge.py`, `action-bridge/default.nix`, README
- `anki-bridge/anki_bridge.py`, `anki-bridge/default.nix`, README
- `coach-daemon/coach.py`, `coach-daemon/default.nix`, README
- `dialog-bridge/dialog_bridge.py`, `dialog-bridge/default.nix`, README
- `intervention-outcomes/intervention_outcomes_reporter.py`, `intervention-outcomes/default.nix`, README
- `llm-planner/planner.py`, `llm-planner/default.nix`, README, `DESIGN_NOTES.md`, planner package
- `phone-bridge/phone_bridge.py`, `phone-bridge/default.nix`, README
- `recovery-manager/recovery_manager.py`, `recovery-manager/default.nix`, README
- `recovery-trigger/recovery_trigger.py`, `recovery-trigger/default.nix`, README
- `session-manager/session_manager.py`, `session-manager/default.nix`, README
- `vault-bridge/default.nix`, README

Shared Python package:

- `python/ai_system/io_utils.py`
- `python/ai_system/queue.py`
- `python/ai_system/events.py`
- `python/ai_system/status.py`
- `python/ai_system/agent_context.py`
- `python/ai_system/context_schema.py`
- `python/ai_system/context_providers.py`
- `python/ai_system/interactions*.py` / interaction modules
- `python/ai_system/interventions.py`
- `python/ai_system/intervention_outcomes.py`
- `python/ai_system/llm_proposal_contract.py`
- `python/ai_system/obsidian_*` modules
- `python/ai_system/proposal_gate.py`
- `python/ai_system/recovery_*` modules

Dev scripts:

- `dev/run-smoke.sh`
- `dev/check-ai-live.sh`
- `dev/audit-ai-project.sh`
- `dev/check-phone-bridge-live.sh`
- `dev/run-obsidian-agent-loop.sh`
- `dev/interaction_surface.py`
- `dev/rebuild-default.sh`

Optional/stub modules reviewed at Nix level:

- `activitywatch/default.nix`
- `browser-bridge/default.nix`
- `compat/default.nix`
- `hypr-agent/default.nix`
- `notifications/default.nix`
- `ollama/default.nix`
- `screenpipe/default.nix`
- `phone-webview/*`

## Files intentionally not deeply reviewed yet

- Non-AI desktop modules outside `modules/programs/ai`, except where they appear in the tar list.
- Binary/import assets under `phone-webview/import/`.
- Image/html assets beyond identifying that `phone-webview/install-to-vault.sh` is a vault-mutating installer.
- Generated `__pycache__` or temporary files.

## Modules found

| Module | Status | Notes |
|---|---:|---|
| core | current | Canonical local paths/timezone defaults. |
| vault-bridge | current | Creates AI vault directory/protocol skeleton. |
| action-bridge | current / high-risk | Live action authority; includes legacy TaskNotes promotion. |
| session-manager | current | Session state and control-file writer. |
| phone-bridge | current | Passive phone telemetry ingestion; rejects misrouted actions. |
| anki-bridge | current / legacy option | Status/proposal writer; has deprecated direct TaskNotes mode. |
| coach-daemon | current | ActivityWatch-based desktop coach and telemetry writer. |
| llm-planner | current but timer off | Local Ollama planner; writes reports, current question/nudge, proposed tasks. |
| dialog-bridge | current but timer off | Notification/answer loop; should hand answers to action queue. |
| recovery-trigger | implemented but disabled | Deterministic recovery nudge generator through proposal gate. |
| recovery-manager | current | Recovery lifecycle classifier. |
| intervention-outcomes | current | Outcome stats reporter; timer enabled by default. |
| Obsidian protocol modules | current | Ingress/planner/action/approval/task-draft chain; review-only. |
| agent context hub | current | Read-only context aggregation. |
| phone-webview | optional integration | Human/phone review surface asset/installer. |
| browser/hypr/notifications/screenpipe | future/stub/optional | Nix integration placeholders or simple packages. |

## Tests found

28 smoke tests were found and run in isolated/chunked form. All passed. See `VERIFICATION_LOG.md`.

## Live paths found

Primary current paths:

- `AI/inbox/actions/*.json`
- `AI/inbox/actions-processed/YYYY-MM-DD/*.json`
- `AI/inbox/actions-failed/YYYY-MM-DD/*.json`
- `AI/inbox/actions-manual-review/YYYY-MM-DD/*.json`
- `AI/inbox/from-phone/events/*.json`
- `AI/inbox/from-phone/processed/YYYY-MM-DD/*.json`
- `AI/inbox/from-phone/failed/YYYY-MM-DD/*.json`
- `AI/inbox/from-desktop/events/*.json`
- `AI/inbox/obsidian/messages/*.json`
- `AI/inbox/obsidian/actions/*.json`
- `AI/outbox/to-phone/current-nudge.{json,md}`
- `AI/outbox/to-phone/current-question.{json,md}`
- `AI/outbox/to-phone/interaction-state.json`
- `AI/outbox/to-obsidian/current-proposal.{json,md}`
- `AI/outbox/to-obsidian/current-approved-proposal.{json,md}`
- `AI/outbox/to-obsidian/current-task-draft.{json,md}`
- `AI/outbox/to-obsidian/proposals/*.json|*.md`
- `AI/outbox/to-obsidian/approved-proposals/*.json|*.md`
- `AI/outbox/to-obsidian/task-drafts/*.json|*.md`
- `AI/state/*`
- `AI/events/*/*.jsonl`
- `AI/proposed-tasks/*.md`
- Real `TaskNotes/` direct mutation through legacy paths is removed or disabled; reviewable drafts remain under `AI/outbox/to-obsidian/task-drafts/*`.

## Side-effecting paths found

Low/normal side-effect surfaces:

- write state/status files under `AI/state`;
- write reports/context under `AI/context`, `AI/reports`, `AI/state/agent`;
- write outbox artifacts to phone/Obsidian;
- write JSONL events;
- archive processed/failed queue files;
- send local desktop notifications;
- start selected user systemd services for replanning/help-now.

High-risk side-effect surfaces:

- `action-bridge promote_task_proposal` is disabled by ac274a9 and no longer writes real TaskNotes.
- `anki-bridge` direct TaskNotes mode is removed/hard-disabled by 36f5813; raw `TASKNOTE_MODE=direct` falls back to `propose`.
- `session-manager` rewrites human-facing control files under `AI/control` as part of session start/end.
- `dialog-bridge` currently writes answer lifecycle events directly instead of delegating to canonical action files.
- JSONL event append is not crash-consistent/audit-grade in the same way as `atomic_write_text/json`.

## Unsafe or legacy paths found

- `action-bridge promote_task_proposal`: disabled legacy/direct mutation surface.
- `anki-bridge taskNoteMode = "direct"`: removed/hard-disabled legacy/direct mutation surface.
- `dialog-bridge` answer handling: duplicated lifecycle ownership; should emit canonical action files.
- `AI/inbox/from-obsidian/...`: not active in Python code; appears only as legacy/diagnostic references.
- `TaskNotes/Tasks` appears in older TODO documentation and should be corrected against actual TaskNotes path/config before implementation.
