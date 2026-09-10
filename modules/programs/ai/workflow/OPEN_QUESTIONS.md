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
3. What trial thresholds justify retaining, redesigning, or stopping the loop after the initial evaluation period?

4. Milestone 3 Receipt proof: can Tasker reliably emit and replay posted_at_epoch on the target platform? Does Receipt need device/notification-instance identity? If reliable posting evidence is unavailable, do not freeze Receipt and do not claim posting-anchored metrics.

5. Milestone 4 provider boundary: which first API provider/model satisfies structured-output, latency, cost, and privacy requirements? Default provider payload remains semantic disclosed_facts only; provenance/omissions stay local unless a reviewed provider requirement proves otherwise.

6. Milestone 5 Outcome freeze: which producers supply micro-action completion, ten-minute engagement, subjective friction, wrong-task/privacy correction? Evidence precedence, finalization timing, and retention/report consumer must be decided before a stable Outcome schema exists.

## Clock synchronization

Milestone 3 Tasker integration must demonstrate that Tasker and laptop clocks remain synchronized within the configured skew allowance (currently 300 seconds). Unreliable device clocks are a known risk; live validation is deferred to Milestone 3. If clock drift exceeds the allowance in practice, the skew tolerance or synchronization mechanism must be chosen before Milestone 3 exit.