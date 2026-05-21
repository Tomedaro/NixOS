# Architecture findings - draft

> Superseded status: later patches disabled the previously identified direct TaskNotes mutation paths. `36f5813` removed/hard-disabled Anki direct TaskNotes mode, and `ac274a9` disabled action-bridge `promote_task_proposal`. Reviewable proposal/draft paths remain; deterministic TaskNotes apply/promote is still future work.

This file records the accepted audit draft for `modules/programs/ai/docs/ARCHITECTURE_FINDINGS.md`.

## Executive summary

Resolved by 36f5813 and ac274a9: the identified direct TaskNotes mutation paths are now removed or disabled; the remaining future work is deterministic apply/promote.

No critical code failure was found in the read-only audit. The main blockers before implementation are high-severity safety/design issues, not failing tests.

## Findings

### HIGH-001 - Resolved: action TaskNotes promotion disabled

- Severity: high
- Area: action authority / TaskNotes boundary
- Evidence:
  - `modules/programs/ai/default.nix` sets `my.ai.actionBridge.authorityLevel = 2` by default.
  - `action_bridge.py` defaults `ACTION_AUTHORITY_LEVEL` to `2`.
  - Resolved by ac274a9: `handle_promote_task_proposal` rejects promotion before any TaskNotes write.
- Why it matters:
  - The same live bridge that handles low-risk interaction/session actions can also create or overwrite durable human commitments.
  - This conflicts with the desired split between AI vault protocol/state and TaskNotes as a human commitment surface.
- Current mitigations:
  - Target path must be inside `TASKNOTES_DIR`.
  - Existing target is not overwritten unless action sets `overwrite=true`.
  - Action journal/idempotency reduces replay risk.
- Remaining risk:
  - Resolved by ac274a9: action files can no longer promote proposals into real TaskNotes through `promote_task_proposal`.
- Recommended treatment:
  - Disable by default and mark as legacy/direct.
  - Resolved by ac274a9: legacy TaskNotes promotion option/env wiring was removed, and `promote_task_proposal` is disabled.
  - Remove promotion template from ordinary template generation.
  - Add smoke test proving default config cannot mutate TaskNotes.

### HIGH-002 - Resolved: Anki direct TaskNotes mode removed

- Severity: high
- Area: TaskNotes boundary
- Evidence:
  - `anki-bridge/default.nix` exposes `taskNoteMode = enum [ "off" "propose" "direct" ]` and documents `direct` as writing/updating a real TaskNotes task.
  - `anki_bridge.py` writes `DIRECT_RECOVERY_TASK` when `TASKNOTE_MODE == "direct"`.
  - Top-level default is safer: `taskNoteMode = "propose"`.
- Why it matters:
  - Resolved by 36f5813: Anki direct mode is removed/hard-disabled; deterministic apply/promote remains future work.
  - It is telemetry-driven and can make durable human commitment changes.
- Current mitigations:
  - Default is propose mode.
  - Direct mode must be configured explicitly.
- Remaining risk:
  - The code path and option remain normalized and documented as an available mode.
- Recommended treatment:
  - Mark direct mode deprecated immediately.
  - Emit warning status/event when enabled.
  - Remove after the deterministic apply gate is available.

### MEDIUM-001 - `dialog-bridge` owns answer lifecycle outside canonical action queue

- Severity: medium
- Area: protocol consistency / action journal
- Evidence:
  - `dialog_bridge.py` writes question answers directly into `AI/inbox/from-desktop/events`, daily answer JSONL, and `AI/state/llm/last-answer.json`.
  - `action-bridge` already implements `answer_question` and `dismiss_question` through the canonical action queue and action journal.
- Why it matters:
  - Two modules own overlapping question lifecycle semantics.
  - Direct answer events bypass action journal/manual-review/idempotency logic.
- Current mitigations:
  - `dialogBridge.enableTimer = false` by default.
  - `action-bridge` has richer question/nudge lifecycle handling.
- Recommended treatment:
  - Migrate `dialog-bridge` answer/dismiss to emit canonical `AI/inbox/actions/*.json` files.
  - Keep `dialog-bridge` as notification/UI only.

### MEDIUM-002 - Event JSONL logs are evidence, not authoritative audit records yet

- Severity: medium
- Area: durable state / auditability
- Evidence:
  - `io_utils.atomic_write_text/json` is crash-conscious: temp file, flush, fsync, replace, parent dir fsync.
  - `io_utils.append_jsonl` opens the log in append mode and writes one JSON line without fsync or locking.
- Why it matters:
  - Many docs/diagnostics rely on JSONL logs to reconstruct outcomes.
  - Append logs can lose the last event on crash and can interleave if multiple writers append concurrently.
- Current mitigations:
  - Most state files are atomic.
  - Current tests validate behavior at functional level.
- Recommended treatment:
  - Document JSONL as analytic/evidence logs, not authoritative audit records.
  - If needed later, harden append with file locking + flush/fsync or move high-value events to per-event atomic files.

### MEDIUM-003 - `AI/proposed-tasks` and Obsidian task drafts are two proposal surfaces

- Severity: medium
- Area: protocol clarity
- Evidence:
  - `llm-planner` writes `AI/proposed-tasks/YYYY-MM-DD.md`.
  - `anki-bridge` propose mode writes `AI/proposed-tasks/anki-recovery.md`.
  - Obsidian task drafts are written to `AI/outbox/to-obsidian/task-drafts/*` and current/latest task draft files.
- Why it matters:
  - Future contributors may confuse legacy proposal files with the new reviewable TaskNotes draft protocol.
- Recommended treatment:
  - Mark `AI/proposed-tasks` as current legacy/proposal-only surface.
  - Mark `AI/outbox/to-obsidian/task-drafts` as the preferred reviewable TaskNotes draft surface.
  - Do not implement real TaskNotes apply against both until semantics are consolidated.

### MEDIUM-004 - Documentation structure is missing the required canonical truth docs

- Severity: medium
- Area: docs correctness / future LLM safety
- Evidence:
  - Expected files such as `CURRENT_STATE.md`, `MODULES.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, `OPERATIONS.md`, `ROADMAP.md`, and `GLOSSARY.md` do not exist in the archive.
  - Current `README.md` is large and mixes orientation, current state, architecture, protocols, operations, and roadmap.
- Why it matters:
  - LLMs/future contributors may treat stale TODOs or old README sections as truth.
- Recommended treatment:
  - Generate canonical docs together with audit docs in the first implementation batch.
  - Make `README.md` short and point to canonical documents.

### MEDIUM-005 - Target machine verification still required

- Severity: medium
- Area: verification
- Evidence:
  - In-container direct smoke tests passed, but full `run-smoke.sh` was not completed through the native `nix shell` loop due tool timeouts.
  - Uploaded `check-ai-live.txt` exited 0 and skipped mutating checks by default.
- Why it matters:
  - Nix/systemd/user-service behavior should be checked on the real NixOS machine before implementation.
- Recommended treatment:
  - Before implementing, run exactly the handoff verification commands on `/home/daniil/NixOS`.

### LOW-001 - Legacy `AI/inbox/from-obsidian` references remain as diagnostic/doc text

- Severity: low
- Area: stale path cleanup
- Evidence:
  - No active Python use was found.
  - References remain in `DEVELOPMENT.md`, dev diagnostics, `AI_DEBUG_REFACTORING_TODO.md`, and the handoff grep.
- Recommended treatment:
  - Keep diagnostic greps, but mark doc references historical or remove once `PROTOCOLS.md` is authoritative.

### LOW-002 - Queue move semantics are local-vault oriented

- Severity: low
- Area: filesystem semantics
- Evidence:
  - `queue.py` uses file age stability and `shutil.move` to archive queue entries.
- Why it matters:
  - This is acceptable for local-first vault paths but should not be assumed safe across filesystems/sync boundaries.
- Recommended treatment:
  - Document local filesystem expectations and Syncthing/Obsidian interaction cautions.

### DOCS-001 - README/TODO contain stale “future” or mixed-state statements

- Severity: docs-only
- Area: documentation correctness
- Evidence examples:
  - README/TODO still mix implemented Obsidian pieces, planned TaskNotes gate, and older phase language.
  - Handoff explicitly says not to let old TODOs override code/test reality.
- Recommended treatment:
  - Move factual current state to `CURRENT_STATE.md`.
  - Move planned work to `ROADMAP.md`.
  - Move protocols to `PROTOCOLS.md`.
  - Keep TODOs subordinate or replace them with backlog docs.

## Positive findings

### POS-001 - Obsidian proposal boundary is well aligned with project philosophy

- Ingress writes bounded intent records only.
- Planner writes reviewable proposal artifacts only.
- Proposal actions record explicit approve/reject/revise decisions and set `executes_now=false`, `writes_live_action_queue=false`.
- Approval bridge writes reviewed artifacts only.
- Task draft bridge writes reviewable outbox draft artifacts only.
- LLM proposal contract rejects direct execution fields.

### POS-002 - Action replay/idempotency protection is substantially improved

- Action files are filtered by stable queue semantics.
- Duplicate processed action ids are skipped.
- Action journal records `processing`, `processed`, `failed`, or `manual_review`.
- Stale `processing` and previous failed/manual-review journals are not replayed automatically.

### POS-003 - Atomic state writes are strong

- Shared atomic writer preserves permissions where possible, fsyncs file data, replaces atomically, and fsyncs parent directory best-effort.
- Multiple services use the shared writer.

### POS-004 - Diagnostics are cautious by default

- `check-ai-live.sh` skips mutating checks unless explicit flags are passed.
- Live action queue was not processed during read-only audit.
