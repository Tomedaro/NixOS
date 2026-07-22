# Open Questions

This file tracks unresolved questions that materially affect architecture, safety, or roadmap order. It is not a task list. Promote resolved decisions to ADRs or `workflow/DECISIONS.md`.

## Blocking architecture questions for the first loop

None.

The previous five architecture gates were resolved by `docs/adr/0008-laptop-task-initiation-kernel.md`:

- a deterministic laptop-side kernel owns the first-loop lifecycle;
- the first product loop addresses inability to start an already-known task;
- Tasker is the first required interaction adapter;
- one API provider is used first behind a narrow adapter;
- context begins with a local allowlist;
- the newer Obsidian proposal chain is canonical for future durable proposals;
- real TaskNotes apply is deferred;
- the older Ollama planner is legacy/specialist rather than the canonical kernel.

## Non-blocking implementation selections

These choices should be made during the corresponding roadmap milestone and recorded when selected. They do not reopen ADR 0008 unless they change its boundaries:

1. Which first API provider/model satisfies structured-output, latency, cost, and privacy requirements?
2. Which authenticated private transport should Tasker use to reach the laptop on the target network?
3. Which exact existing paths should store first-loop run state, queue evidence, cards, and outcomes before `PROTOCOLS.md` is updated?
4. What trial thresholds justify retaining, redesigning, or stopping the loop after the initial evaluation period?
