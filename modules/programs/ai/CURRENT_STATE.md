# Current state

This file records what is true in the current implementation. It intentionally separates implemented, partial, planned, and legacy/direct behavior.

## Implemented now

- Local AI module tree under `modules/programs/ai` with Nix modules, Python helpers, smoke tests, development scripts, and module READMEs.
- AI vault protocol paths for inbox/outbox/state/event style coordination.
- Obsidian-facing protocol modules for messages, context, ingress, intent planning, approved proposal actions, approval bridging, and task draft creation.
- LLM proposal contracts that reject direct execution-style fields.
- Action bridge for live action processing, action journaling/idempotency, question answer/dismiss handling, session actions, and selected mutation paths.
- Phone bridge, dialog bridge, session manager, coach daemon, recovery manager/trigger, intervention outcomes, Anki bridge, and planner modules.
- Smoke tests covering major protocol and bridge behavior.

## Strong current properties

- Obsidian/LLM paths are mostly proposal, review, and draft oriented rather than silent execution.
- Atomic JSON writes are used for many state/protocol files.
- Live diagnostics default to read-only unless mutating flags are passed.
- TaskNotes direct mutation is limited to identifiable paths rather than scattered everywhere.

## Known legacy/direct behavior

These are real mutation paths and should not be treated as the future design:

- `action-bridge promote_task_proposal` can write real TaskNotes when authority permits it.
- `anki-bridge taskNoteMode = "direct"` can write/update a real TaskNotes recovery task.

## Partial or transitional behavior

- `dialog-bridge` can own answer event/state writing directly even though `action-bridge` also supports canonical `answer_question` / `dismiss_question` actions.
- JSONL event files are useful evidence logs, but they should not yet be documented as authoritative crash-safe/tamper-evident audit records.
- Planner outputs and context providers contain useful signals, but the end-to-end personal learning loop is not yet canonical.
- Goal IDs and intervention outcomes exist, but goal hierarchy and commitment semantics are not first-class yet.
- Cooldowns/TTL exist, but a holistic attention/receptivity policy is not yet defined.

## Planned but not complete

- Split or lower broad action authority.
- Deprecate direct TaskNotes mutation surfaces.
- Build deterministic TaskNotes apply/promote gate.
- Add first-class read-only TaskNotes context.
- Add richer goal/preference/policy contracts.
- Add inspectable personal model and learning loop.
- Add product eval scenarios for usefulness, burden, correction, and recovery.

## Do not assume

- Do not assume every TODO is current.
- Do not assume `ROADMAP.md` items are implemented.
- Do not assume JSONL logs are authoritative audit logs.
- Do not assume any LLM output may directly mutate TaskNotes or execute actions.
