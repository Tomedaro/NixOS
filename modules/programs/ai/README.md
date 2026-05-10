# Local-first AI productivity companion

This directory contains the AI subsystem for a local-first, inspectable, recovery-oriented productivity companion.

The system is intentionally not a broad autonomous agent. It is a set of local protocols, bridges, planners, review surfaces, and safe action gates that help the user reflect, recover, plan, and act while preserving control.

## Start here

Read these documents in order:

1. `CURRENT_STATE.md` - what is implemented now, what is planned, and what is legacy/direct.
2. `SAFETY_MODEL.md` - authority boundaries, side-effect rules, TaskNotes rules, and LLM boundaries.
3. `PROTOCOLS.md` - exact AI vault queue, state, event, and draft paths.
4. `MODULES.md` - module responsibilities, side effects, and review status.
5. `ARCHITECTURE.md` - conceptual architecture and runtime views.
6. `OPERATIONS.md` - safe diagnostics, smoke tests, and runbooks.
7. `DEVELOPMENT.md` - contribution rules and change process.
8. `ROADMAP.md` - planned work in safety/dependency order.
9. `GLOSSARY.md` - canonical terms.

Audit detail and design review material live under `docs/`.

## Core philosophy

- Local-first: the AI vault is local state and protocol, not a cloud command center.
- Inspectable: important proposals, decisions, events, and state should be files a human can inspect.
- Recovery-oriented: the assistant should help the user recover without shame, pressure, or hidden escalation.
- Agentic but gated: planning can be smart, but durable mutation requires explicit authority and review.
- TaskNotes as commitments: TaskNotes is the durable human commitment surface, not an LLM execution backend.
- LLMs propose: LLM-facing paths may read, classify, summarize, propose, and draft. They must not silently create, edit, archive, delete, launch, or execute.

## Main surfaces

| Surface | Role |
| --- | --- |
| AI vault | Protocol, queue, state, event, draft, and evidence layer. |
| Obsidian | Human review and interaction surface. |
| TaskNotes | Durable human commitment surface. |
| Phone/dialog surfaces | Lightweight interaction and notification surfaces. |
| Action bridge | Gated executor for intentional live actions. |
| Context/planner modules | Read, summarize, propose, and draft. |

## Current caution

Two existing paths can mutate real TaskNotes and must be treated as legacy/direct surfaces until consolidated or removed:

- `action-bridge promote_task_proposal` when authority permits it;
- `anki-bridge taskNoteMode = "direct"`.

Do not add new direct TaskNotes mutation. Use reviewable drafts and documented gates.

## Documentation transition

This documentation set intentionally replaces earlier sprawling README/TODO material with canonical surfaces:

- current truth in `CURRENT_STATE.md`;
- planned work in `ROADMAP.md`;
- concrete refactors in `docs/REFACTOR_BACKLOG.md`;
- protocol truth in `PROTOCOLS.md`;
- safety truth in `SAFETY_MODEL.md`.

Old TODO-style documents were removed to avoid stale instructions overriding code and tests.
