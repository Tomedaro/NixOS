# Open Questions

This file tracks unresolved questions that materially affect architecture, safety, or roadmap order. It is not a task list. Promote resolved decisions to ADRs or `workflow/DECISIONS.md`.

## Current open questions

### 1. What owns the canonical runtime lifecycle?

Which component should receive a typed event, reduce state, choose a deterministic handler or bounded model skill, build context, validate the result, request approval, dispatch an action, and link later outcomes?

Current state: these responsibilities are distributed across bridges, planners, shared modules, queues, and `dev/run-obsidian-agent-loop.sh`.

### 2. What is the model-provider strategy?

The implemented planner is Ollama-specific, while the intended user direction is API-hosted models because of hardware limits.

Decision needs: provider abstraction, secrets, privacy boundary, structured outputs, retries/timeouts, cost budgets, fallback/offline behavior, and the future role of Ollama.

### 3. Which proposal surface is canonical?

How should the older `llm-planner`/`AI/proposed-tasks` outputs relate to the newer Obsidian intent/proposal/approval/task-draft chain?

New work should not create a third parallel proposal protocol.

### 4. What is the first complete product loop?

Which one loop should be validated end to end before broader expansion: stuck/help-now, low-energy recovery, stale-task review, or another bounded loop?

The answer determines which context, interface, outcome, and automation work is actually necessary next.

### 5. Is real TaskNotes apply required for that first loop?

TaskNotes dry-run validation exists, but atomic apply does not. Decide whether real apply is a near-term dependency or should remain deliberately deferred while non-commitment loops are validated.
