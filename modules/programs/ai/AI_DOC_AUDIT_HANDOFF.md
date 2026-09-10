# AI documentation handoff

Snapshot date: 2026-07-22.

## Status

The canonical documentation has been refreshed against the current archive. Direct TaskNotes mutation remains disabled; reviewed TaskNotes drafts and deterministic apply validation exist; real apply does not.

The repository is a strong tested prototype of distributed kernel components, not yet one canonical runtime kernel or a product-validated daily helper.

## Start here

1. `CURRENT_STATE.md` - implementation and verification truth.
2. `SAFETY_MODEL.md` - authority, capability, and mutation boundaries.
3. `ARCHITECTURE.md` - current topology and accepted first-loop kernel direction.
4. `PROTOCOLS.md` - queue/state/outbox path orientation.
5. `docs/SCHEMA_REGISTRY.md` - versioned contract inventory.
6. `MODULES.md` - module ownership map.
7. `docs/adr/0008-laptop-task-initiation-kernel.md` - accepted first-loop architecture decision.
8. `ROADMAP.md` - dependency-ordered future work.
9. `docs/ARCHITECTURE_FINDINGS.md` - current assessment.
10. `docs/REFACTOR_BACKLOG.md` - concrete implementation candidates.

## Current non-negotiable boundary

Models may read bounded context, classify, summarize, propose, draft, and explain. They do not receive implicit authority to mutate TaskNotes or execute broad live actions.

## Current implementation headline

```text
bounded context
  -> proposal
  -> deterministic validation
  -> explicit review
  -> bounded action or draft
  -> inspectable evidence/outcome
```

## Important partial states

- TaskNotes apply **validation** exists; TaskNotes apply **mutation** does not.
- Named action capabilities exist; numeric authority remains transitional.
- Interaction/outcome modules exist; a canonical learning loop does not.
- The older Ollama planner and newer Obsidian proposal chain coexist in code; ADR 0008 selects the newer chain for future durable proposals.
- The API-model direction and laptop-first task-initiation kernel are accepted in ADR 0008 but not implemented.
- Thirty smoke-test files pass in the reconstructed archive environment; target-machine verification remains separate.

## Accepted next direction

ADR 0008 resolves the blocking architecture gate for the first loop:

- deterministic laptop-side kernel;
- Tasker-triggered initiation support for an already-known task;
- one API provider behind a narrow adapter;
- allowlisted remote context;
- bounded queueing and expiry;
- newer Obsidian chain for future durable proposals;
- TaskNotes apply deferred.

`workflow/OPEN_QUESTIONS.md` now contains only non-blocking implementation selections.

## Rules for future work

- Establish truth from code, tests, Nix options, and canonical docs.
- Do not revive historical audit plans as current instructions.
- Keep model context minimal and provenance-aware.
- Add no new parallel proposal or action protocol without an ownership decision.
- Treat product usefulness and mechanical correctness as separate evaluation targets.
- Never claim target-machine behavior without target-machine evidence.
