# Module review register - draft

> Superseded status: later patches disabled the previously identified direct TaskNotes mutation paths. `36f5813` removed/hard-disabled Anki direct TaskNotes mode, and `ac274a9` disabled action-bridge `promote_task_proposal`. Reviewable proposal/draft paths remain; deterministic TaskNotes apply/promote is still future work.

This file records the accepted audit draft for `modules/programs/ai/docs/MODULE_REVIEW_REGISTER.md`.

Severity legend: critical, high, medium, low, cleanup, docs-only.
Authority legend: observe, draft/propose, review, local-state mutate, live-action, TaskNotes mutate.

## Top-level Nix composition

### `modules/programs/ai/default.nix`

- Purpose: imports all AI submodules and sets project-level defaults.
- Current status: active composition layer.
- Evidence:
  - imports `core`, `session-manager`, `action-bridge`, `vault-bridge`, telemetry bridges, feedback bridges, `llm-planner`, and optional/future layers at lines 5-35.
  - sets `ankiBridge.taskNoteMode = "propose"` at lines 117-122.
  - sets `llmPlanner.enableTimer = false` at lines 166-170.
  - sets `dialogBridge.enableTimer = false` at lines 204-209.
  - sets `actionBridge.authorityLevel = 2` at lines 227-234.
  - sets `recoveryTrigger.enable = false` at lines 242-244.
- Side effects: none directly; config enables/starts services via imported modules.
- Authority: configuration authority.
- Issues:
  - Resolved by ac274a9: broad action authority no longer enables real TaskNotes promotion because `promote_task_proposal` is disabled.
  - LOW: comments are generally useful but should move lasting architecture rationale into docs/ADRs.
- Actions:
  - Split action authority into ordinary interaction/session authority and explicit TaskNotes apply/promote authority.
  - Keep defaults here, but document all effective runtime defaults in `CURRENT_STATE.md` and `OPERATIONS.md`.

### `core/default.nix`

- Purpose: canonical paths/timezone and protocol-relative path options.
- Current status: current and important.
- Evidence: defines `vaultRoot`, `aiDir`, `taskNotesDir`, timezone, and protocol path suboptions at lines 5-78.
- Inputs: Nix configuration.
- Outputs: typed config values used by other modules.
- Side effects: none.
- Authority: configuration reference.
- Issues:
  - LOW: protocol path defaults should be mirrored exactly in `PROTOCOLS.md`.
- Actions:
  - Treat `core/default.nix` as the source of truth for root/path naming.

### `vault-bridge/default.nix`

- Purpose: creates the AI vault directory skeleton and initial human-editable policy/control files.
- Current status: current.
- Evidence: creates control, policy, state, inbox, outbox, events, logs, prompts/templates/schemas/cache/archive paths at lines 13-75.
- Inputs: Nix config paths.
- Outputs: AI vault directories and seed files.
- Side effects: creates directories/files in `AI_DIR` and `TASKNOTES_DIR/AI`.
- Authority: local-state mutate during initialization.
- Issues:
  - MEDIUM: its seeded README still says LLM-created obligations should go to `proposed-tasks/`; this is true for legacy planner proposals but must coexist with Obsidian task drafts under `outbox/to-obsidian/task-drafts`.
  - LOW: vault init owns many path declarations; `PROTOCOLS.md` should reference it to avoid drift.
- Actions:
  - Add a generated/path inventory check so every path created here appears in `PROTOCOLS.md`.

## Live action and human-commitment modules

### `action-bridge/action_bridge.py`

- Purpose: consumes canonical action files from `AI/inbox/actions/*.json` and performs deterministic side effects.
- Current status: current; highest authority component.
- Inputs:
  - `AI/inbox/actions/*.json`
  - current session/nudge/question/recovery state
  - proposed task files under `AI/proposed-tasks/*.md`
- Outputs:
  - processed/failed/manual-review action queues
  - action journal and processed id cache
  - `AI/state/action-bridge/*`
  - session/control effects via `ai-session`
  - phone outbox interaction state
  - recovery state
  - events under `AI/events/actions`, `phone`, `desktop`, `tasknotes`, `proofs`, `recovery`
  - Resolved by ac274a9: `promote_task_proposal` is disabled and no longer writes real `TaskNotes/` files.
- Side effects:
  - file mutation;
  - subprocess/systemd calls;
  - Resolved by ac274a9: promotion no longer mutates TaskNotes.
  - queue moves.
- Resolved by ac274a9 and 36f5813: legacy/direct TaskNotes mutation paths are disabled or removed.
- Evidence:
  - defaults `ACTION_AUTHORITY_LEVEL` to 2 at line 30.
  - defines current action queues at lines 38-41.
  - defines current phone outbox files at lines 72-77.
  - Resolved by ac274a9: `handle_promote_task_proposal` now rejects promotion before any TaskNotes write.
  - action dispatch includes `start_session`, `end_session`, `check_in`, `answer_question`, `ack_nudge`, `snooze_nudge`, `dismiss_question`, `start_recovery_target`, `promote_task_proposal`, and `submit_proof` at lines 1447-1470.
  - replay protection uses action journals and sends stale `processing`, previous `failed`, or previous `manual_review` to manual review at lines 1513-1566.
  - action status records include processed/failed/manual_review/unstable/ignored and authority level at lines 1691-1698.
- Tests:
  - `action_bridge_smoke.py` covers nudge/question actions, invalid JSON, duplicate IDs, action journal, stale processing journal, and process lock.
- Issues:
  - Resolved by ac274a9: broad authority level 2 is no longer sufficient for TaskNotes mutation because promotion is disabled.
  - Resolved by ac274a9: `promote_task_proposal` is disabled and is no longer a real TaskNotes writer.
  - MEDIUM: templates include `promote-anki-recovery.json`; this normalizes a legacy behavior in the action template directory.
  - MEDIUM: JSONL events are useful evidence but not authoritative audit logs yet.
- Actions:
  - Superseded by ac274a9: the legacy TaskNotes promotion option/env wiring was removed because promotion is disabled.
  - Superseded by ac274a9: the legacy TaskNotes promotion option/env wiring was removed because promotion is disabled.
  - Remove or quarantine `promote_task_proposal` templates from ordinary template creation.
  - Add tests proving default config cannot mutate TaskNotes.

### `anki-bridge/anki_bridge.py`

- Updated by 36f5813: Anki bridge emits proposal output; direct TaskNotes mode is removed/hard-disabled.
- Current status: current; safer default but legacy direct mode remains.
- Inputs:
  - AnkiConnect HTTP API;
  - configured deck list;
  - `TASKNOTE_MODE` / `CREATE_TASKNOTE`.
- Outputs:
  - `AI/state/anki/status.*` and legacy `AI/anki/status.json` style compatibility;
  - `AI/proposed-tasks/anki-recovery.md` in propose mode;
  - Removed by 36f5813: direct Anki TaskNotes output is no longer written.
  - `AI/events/anki/YYYY-MM-DD.jsonl`.
- Resolved by 36f5813: Anki direct TaskNotes write is removed/hard-disabled.
- Resolved by ac274a9 and 36f5813: legacy/direct TaskNotes mutation paths are disabled or removed.
- Evidence:
  - Updated by 36f5813: Nix `taskNoteMode` supports only `off` and `propose`; raw `TASKNOTE_MODE=direct` falls back to `propose`.
  - Resolved by 36f5813: `write_recovery_task_or_proposal` no longer writes `DIRECT_RECOVERY_TASK`; raw `TASKNOTE_MODE=direct` falls back to `propose`.
  - Nix top-level default keeps `taskNoteMode = "propose"` at `default.nix` lines 117-122.
- Tests:
  - Resolved by 2bb0fa1 and 36f5813: offline Anki smoke coverage verifies default/propose behavior, `CREATE_TASKNOTE=0`, and raw direct fallback do not write real TaskNotes.
- Issues:
  - Resolved by 36f5813: direct TaskNotes mode is removed/hard-disabled.
  - Resolved by 36f5813: direct mode is removed/hard-disabled, so the read-only/status bridge label is no longer contradicted by direct TaskNotes writes.
- Actions:
  - No further Anki direct-mode deprecation work is needed; preserve reviewable proposal behavior until deterministic apply/promote exists.
  - Consider removing direct mode after deterministic apply gate exists.

### `session-manager/session_manager.py`

- Purpose: manages local productivity session state and compiled policy/control files.
- Current status: current.
- Inputs: CLI commands, current time/config.
- Outputs:
  - `AI/state/session/current.json`
  - `AI/state/session/current-policy.{json,md}`
  - `AI/control/current-task.md`, `current-mode.md`, `current-block.md`
  - `AI/events/desktop/YYYY-MM-DD.jsonl`
  - session archive files
- Side effects: mutates AI state/control files.
- Authority: local-state mutate.
- Tests: `session_manager_smoke.py`.
- Issues:
  - MEDIUM: control files are human-editable surfaces but also written by service. Docs must make ownership rules clear.
- Actions:
  - Document `session-manager` as authoritative for session-derived control files during active sessions.

## Phone, desktop, interaction modules

### `phone-bridge/phone_bridge.py`

- Purpose: ingests passive phone telemetry from Tasker/phone event files.
- Current status: current and reasonably hardened.
- Inputs: `AI/inbox/from-phone/events/*.json`.
- Outputs:
  - `AI/state/phone/latest.{json,md}`
  - `AI/events/phone/YYYY-MM-DD.jsonl`
  - `AI/logs/phone/YYYY-MM-DD.md`
  - processed/failed raw event queues
  - phone outbox templates when enabled
- Side effects: state/log/event writes and queue moves.
- Authority: observe/local-state mutate only.
- Evidence:
  - raw event queue path at lines 16-34.
  - rejects misrouted command/action schemas rather than executing them in `validate_raw_event_contract` and smoke tests.
- Tests: `phone_bridge_smoke.py`.
- Issues:
  - LOW: `createTemplates=true` is transitional; ownership should eventually move fully to vault/protocol docs.
- Actions:
  - Keep as telemetry-only; do not add action authority here.

### `coach-daemon/coach.py`

- Purpose: rule-based desktop context classifier and notification/log writer.
- Current status: current.
- Inputs: ActivityWatch API, current task/control policy.
- Outputs:
  - `AI/state/desktop/now.{json,md}`
  - `AI/events/desktop/YYYY-MM-DD.jsonl`
  - `AI/logs/desktop/YYYY-MM-DD.md`
  - local notifications
- Side effects: local notification and state/log writes.
- Authority: observe + local notification.
- Tests: `coach_daemon_smoke.py`.
- Issues:
  - LOW: coach is intentionally friendly, but docs should mark notification authority separately from mutation authority.
- Actions:
  - Document notification authority as non-durable/user-facing but not commitment-mutating.

### `dialog-bridge/dialog_bridge.py`

- Purpose: displays pending planner questions and records answers.
- Current status: implemented but timer disabled by default.
- Inputs: `AI/state/llm/pending-question.json`.
- Outputs:
  - `AI/outbox/to-phone/current-question.md`
  - `AI/archive/questions/YYYY-MM-DD/*.json`
  - `AI/events/desktop/YYYY-MM-DD.answers.jsonl`
  - `AI/inbox/from-desktop/events/*_question_answered.json`
  - `AI/state/llm/last-answer.json`
  - triggers planner service if configured.
- Side effects: notification, events, state writes, planner trigger.
- Authority: local interaction lifecycle mutate.
- Evidence:
  - writes answer event directly to `AI/inbox/from-desktop/events` and JSONL at lines 391-418.
  - triggers planner through `systemctl --user start` at lines 423-433.
- Tests: `dialog_bridge_smoke.py` only covers no-pending inactive markdown.
- Issues:
  - MEDIUM: duplicates question lifecycle ownership with `action-bridge`, which already has canonical `answer_question` and `dismiss_question` actions.
  - MEDIUM: answer path bypasses action journal/idempotency/manual-review semantics.
- Actions:
  - Migrate answer/dismiss actions to write `AI/inbox/actions/*.json` canonical action files.
  - Expand tests for answer/dismiss and planner-trigger behavior.

### `llm-planner`

- Purpose: builds context, calls local Ollama, writes planner outputs, proposed tasks, and current interaction surfaces.
- Current status: implemented; automatic timer disabled by default.
- Inputs:
  - local state/events/context;
  - `TaskNotes` read context;
  - Ollama HTTP API;
  - mode-specific config.
- Outputs:
  - reports under `AI/reports/*`;
  - `AI/context/today.{json,md}`;
  - `AI/state/llm/last-output.*`, `planner-status.*`, `pending-question.json`, `last-error.md`;
  - `AI/outbox/to-phone/current-nudge.*`, `current-question.*`, `interaction-state.json`;
  - `AI/proposed-tasks/YYYY-MM-DD.md`.
- Side effects: AI state/outbox/report writes; no live action execution.
- Authority: draft/propose.
- Evidence:
  - writes current question and pending question at `outputs.py` lines 445-487.
  - writes current nudge and interaction state at `outputs.py` lines 513-611.
  - writes proposed tasks under `AI/proposed-tasks` at line 143.
- Tests: `planner_outputs_smoke.py`; LLM contract tests cover safe proposal logic.
- Issues:
  - MEDIUM: `AI/proposed-tasks` is a legacy proposal surface next to newer Obsidian task drafts; docs must distinguish them.
  - LOW: local model quality fallback is intentionally defensive; keep documented.
- Actions:
  - Mark `AI/proposed-tasks` as legacy/proposal-only, not TaskNotes apply path.
  - Keep timer disabled until interaction lifecycle and authority split are complete.

## Recovery and intervention modules

### `recovery-trigger/recovery_trigger.py`

- Purpose: deterministic recovery nudge generator using agent context and proposal gate.
- Current status: implemented but disabled by default.
- Inputs: agent context facts, current phone interaction state, recovery cooldowns.
- Outputs:
  - `AI/outbox/to-phone/current-nudge.*`
  - `AI/outbox/to-phone/current-question.*`
  - `AI/outbox/to-phone/interaction-state.json`
  - `AI/state/recovery-trigger/*`
  - `AI/events/interventions/YYYY-MM-DD.jsonl`
- Side effects: outbox/state/events writes.
- Authority: draft/propose/review-surface mutate, not TaskNotes.
- Evidence:
  - writes phone outputs at lines 63-104.
  - decision writes and intervention event writes at lines 215-269.
- Tests: `interventions_smoke.py`, `intervention_outcomes_smoke.py`, proposal gate tests.
- Issues:
  - LOW/MEDIUM: disabled by default, but docs must distinguish implemented-disabled from future.
- Actions:
  - Document status as implemented/disabled, not planned-only.

### `recovery-manager/recovery_manager.py`

- Purpose: classifies ongoing recovery attempts from observed app/open/close evidence.
- Current status: current.
- Inputs: `AI/state/recovery/current.json`, phone/desktop events.
- Outputs:
  - `AI/state/recovery/current.json`
  - `AI/state/recovery/status.{json,md}`
  - `AI/events/recovery/YYYY-MM-DD.jsonl`
- Side effects: state/event writes.
- Authority: local-state mutate.
- Evidence: reads recovery state at line 538, writes updated recovery at lines 565-568.
- Tests: `recovery_smoke.py`.
- Issues:
  - LOW: good lifecycle classification coverage; docs should include rapid abort/no launch/possible success semantics.
- Actions:
  - Include recovery state machine in `PROTOCOLS.md` and `SAFETY_MODEL.md`.

### `intervention-outcomes/intervention_outcomes_reporter.py`

- Purpose: summarizes intervention events/outcomes across a date window.
- Current status: current; timer enabled by default.
- Inputs: intervention/recovery/action event JSONL files.
- Outputs:
  - `AI/state/interventions/current-report.json`
  - `AI/state/interventions/stats.json`
  - `AI/state/interventions/status.md`
- Side effects: state/report writes when `--write`.
- Tests: `intervention_outcomes_reporter_smoke.py`.
- Issues:
  - LOW: event log authority level must be documented as analytic evidence, not immutable audit truth yet.
- Actions:
  - Document report semantics and event sources.

## Obsidian and LLM proposal boundary modules

### `python/ai_system/obsidian_ingress.py`

- Purpose: converts Obsidian-origin messages/action requests into bounded intent records.
- Current status: current.
- Inputs: CLI/payload from Obsidian/Templater.
- Outputs: `AI/inbox/obsidian/messages/*.json`.
- Side effects: writes intent files only.
- Authority: review/intake.
- Evidence: module doc says it never executes actions; writes `obsidian_intent.v1` via `atomic_write_json` at lines 4 and 108-116.
- Tests: `obsidian_ingress_smoke.py`.
- Issues: none high.

### `python/ai_system/obsidian_intent_planner.py`

- Purpose: turns Obsidian intent into reviewable proposal artifacts.
- Current status: current.
- Outputs: `AI/outbox/to-obsidian/proposals/*` and current proposal files.
- Authority: draft/propose.
- Evidence: writes proposal/current files at lines 324-336 and states no direct commands.
- Tests: `obsidian_intent_planner_smoke.py`.
- Issues: none high.

### `python/ai_system/obsidian_proposal_action.py`

- Purpose: records explicit approve/reject/revise decisions from Obsidian.
- Current status: current.
- Outputs: `AI/inbox/obsidian/actions/*.json`, latest decision state.
- Authority: review decision capture; not live execution.
- Evidence: normalizes `executes_now=False` and `writes_live_action_queue=False` at lines 105-107; writes files at lines 133-153.
- Tests: `obsidian_proposal_action_smoke.py`.
- Issues: none high.

### `python/ai_system/obsidian_approval_bridge.py`

- Purpose: validates explicit proposal approval and writes reviewed artifact only.
- Current status: current.
- Outputs: approved proposal outbox/current files.
- Authority: review bridge; not live execution.
- Evidence: validates proposal policy and writes `executes_now=False`, `writes_live_action_queue=False` at lines 135-205; writes reviewed artifact at lines 278-281.
- Tests: `obsidian_approval_bridge_smoke.py`.
- Issues: none high.

### `python/ai_system/obsidian_task_draft.py`

- Purpose: converts approved proposal into reviewable TaskNotes draft artifact.
- Current status: current.
- Outputs: `AI/outbox/to-obsidian/task-drafts/*`, current/latest task draft files.
- Authority: draft; explicitly not TaskNotes mutate.
- Evidence: module doc says it does not edit Obsidian notes directly; rejects direct execution fields at lines 238-242; writes draft files at lines 379-384.
- Tests: `obsidian_task_draft_smoke.py`.
- Issues:
  - MEDIUM: there is no deterministic apply/promote gate into real TaskNotes yet; docs must avoid implying drafts are real tasks.
- Actions:
  - Build deterministic apply/promote gate after authority split.

### `python/ai_system/llm_proposal_contract.py`

- Purpose: constrains LLM output to safe Obsidian proposal records.
- Current status: current and strong.
- Inputs: LLM output JSON.
- Outputs: validated/sanitized proposal result.
- Authority: pure validation / proposal shaping.
- Evidence: rejects direct execution fields at lines 341-345; produces `obsidian_proposal.v1` with contract refs around lines 382-416.
- Tests: `llm_proposal_contract_smoke.py`.
- Issues: none high.

### `python/ai_system/proposal_gate.py`

- Purpose: deterministic validation gate for recovery proposals.
- Current status: current for recovery; not yet TaskNotes apply gate.
- Evidence: allowed actions limited to `start_recovery_target` and `snooze_nudge` at line 16; rejects direct execution fields at lines 150-169.
- Tests: `proposal_gate_smoke.py`.
- Issues:
  - LOW: name is generic but current scope is recovery proposals, not all proposals.
- Actions:
  - Keep current scope clear; create separate TaskNotes apply gate rather than overloading recovery gate.

## Shared infrastructure

### `python/ai_system/io_utils.py`

- Purpose: shared atomic read/write and JSONL helpers.
- Current status: current and improved.
- Evidence:
  - `atomic_write_text` uses temp file, flush, chmod/chown preservation, `fsync`, `os.replace`, and parent dir fsync at lines 61-84.
  - `append_jsonl` opens append and writes JSON line at lines 119-124 but does not lock/fsync.
- Authority: utility.
- Issues:
  - MEDIUM: atomic writes are strong; JSONL append is not equivalent and should not be documented as authoritative audit storage until hardened.
- Actions:
  - Clarify event JSONL as evidence log, not immutable audit log.
  - Add append locking/fsync or per-event atomic files if logs become authoritative.

### `python/ai_system/queue.py`

- Purpose: stable queue-file discovery and unique move helper.
- Current status: current.
- Evidence: ignores dotfiles, temp/partial/swap files, only processes `.json`, enforces age stability at lines 6-64; moves via `shutil.move` at lines 81-89.
- Tests: multiple queue smoke tests.
- Issues:
  - LOW: move semantics are acceptable for local vault but should be documented as local-filesystem oriented.
- Actions:
  - Document queue stability and same-filesystem expectations.
