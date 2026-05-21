# AI documentation audit handoff

> Superseded status: later patches disabled the previously identified direct TaskNotes mutation paths. `36f5813` removed/hard-disabled Anki direct TaskNotes mode, and `ac274a9` disabled action-bridge `promote_task_proposal`. Reviewable proposal/draft paths remain; deterministic TaskNotes apply/promote is still future work.

## Status

The AI documentation has been reorganized into canonical truth surfaces. Future work should read the new docs first and should not resurrect old TODO-style material as authority.

## Start here

1. `CURRENT_STATE.md` - implementation truth.
2. `SAFETY_MODEL.md` - authority and side-effect boundaries.
3. `PROTOCOLS.md` - queue/state/event/draft paths.
4. `MODULES.md` - module roles and side effects.
5. `ARCHITECTURE.md` - architecture and runtime views.
6. `ROADMAP.md` - planned work.
7. `docs/REFACTOR_BACKLOG.md` - implementation backlog.
8. `docs/MODULE_REVIEW_REGISTER.md` - audit detail.

## Philosophy to preserve

This project is a local-first adaptive AI goal-achievement companion.

It should be:

- local-first;
- inspectable;
- recovery-oriented;
- agentic but gated;
- friendly and coach-like rather than punitive;
- explicit about authority;
- explicit about user control;
- careful with durable state;
- careful with TaskNotes as human commitments;
- careful with LLM outputs as proposals, not execution.

TaskNotes is the durable human commitment surface.
The AI vault is the protocol, state, queue, event, draft, and evidence layer.
Obsidian is the review and interaction surface.

## Non-negotiable boundary

LLM-facing paths may read, classify, summarize, propose, and draft. They must not silently create, edit, archive, delete, launch, execute, or mutate durable commitments.

## Known legacy/direct paths

These paths currently exist and must not be treated as the target architecture:

- Superseded by ac274a9: `action-bridge promote_task_proposal` is disabled and no longer writes real TaskNotes.
- Superseded by 36f5813: `anki-bridge taskNoteMode = "direct"` is removed/hard-disabled; raw `TASKNOTE_MODE=direct` falls back to `propose`.
- `dialog-bridge` still has lifecycle behavior that should move behind canonical `answer_question` / `dismiss_question` actions.

## Next implementation order

1. Add/verify tests around legacy/direct mutation behavior.
2. Split or lower broad `action-bridge` authority.
- Done by ac274a9: keep `promote_task_proposal` disabled until deterministic TaskNotes apply/promote exists.
- Done by 36f5813: keep Anki direct TaskNotes mode removed/hard-disabled.
5. Move `dialog-bridge` answer/dismiss handling to canonical action files.
6. Add first-class read-only TaskNotes context.
7. Build deterministic TaskNotes apply/promote gate.
8. Add product scenario evals before adaptive behavior changes.

## How future LLMs should proceed

- Establish ground truth from code, tests, Nix options, dev scripts, and current docs.
- Use `CURRENT_STATE.md` over old memories.
- Record uncertainties explicitly.
- Prefer small verifiable doc/code changes.
- Never assume a roadmap item is implemented.
- Never assume an LLM output may execute or mutate TaskNotes.
- Never mutate live queues during analysis unless explicitly asked.
