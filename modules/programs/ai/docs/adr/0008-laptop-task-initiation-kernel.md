# ADR 0008 - Laptop-first task-initiation kernel

## Status

Accepted

## Date

2026-07-22

## Context

The repository already contains proposal contracts, context providers, interaction lifecycle helpers, action gates, Obsidian review flows, and outcome records, but no canonical runtime owns an interaction from trigger through outcome.

The first product problem has been narrowed deliberately:

> The user already knows the task but cannot begin it.

The first loop is not responsible for choosing priorities, reorganizing the day, creating a project plan, or deciding what the user ought to value. The required first interface is Tasker. The runtime will live on the laptop, and model reasoning will use one remote API provider because the laptop is not intended to run the primary models locally.

## Decision

### Canonical ownership

Introduce a deterministic laptop-side kernel that owns the first loop lifecycle:

```text
Tasker event
  -> validation and deduplication
  -> interaction/run state
  -> known-task resolution
  -> bounded context assembly
  -> deterministic route or one bounded model call
  -> schema and policy validation
  -> Tasker action card
  -> user response
  -> outcome record
```

Ordinary software owns lifecycle, state, queues, expiry, validation, approvals, and side effects. The model is a bounded proposal worker, not the controller of the application loop.

### First product loop

The first complete loop is task initiation for a known task:

```text
known task
  -> user presses Stuck
  -> identify the initiation barrier
  -> propose one small physical/digital starting action
  -> Start / Shrink / Blocked / Defer
  -> record what happened
```

Task resolution follows this order:

1. explicit task identity supplied by the trigger;
2. active session task when `status == "active"`;
3. a short user-provided task description.

The kernel must not silently choose a different task or show the full backlog when the known task cannot be resolved.

### Runtime and interaction persistence

- The kernel runs on the laptop.
- The first implementation may use a small HTTP service plus SQLite; no distributed workflow engine is required.
- Interaction state survives ordinary process restarts and remains useful for hours, not indefinitely.
- The initial `stuck` request expiry is two hours and is a trial default, not a permanent behavioral claim.
- A task change invalidates or stales an outstanding initiation card.

### Tasker and queue behavior

Tasker is the required first interaction adapter.

- If Tasker cannot reach the laptop, it queues the event locally, shows that it is queued, and retries when the laptop becomes reachable.
- If the laptop receives the event but the model API is unavailable, the kernel queues the model job with bounded retry/backoff.
- Expired or superseded initiation requests are not delivered later as if still current.
- Queue operations require stable event IDs/idempotency keys.

### Model-provider direction

- Use one remote API provider first behind a narrow internal provider interface.
- Preserve schema-bound outputs and deterministic validation.
- The exact first provider/model is an implementation selection, not a change to action authority.
- Do not build multi-provider routing, automatic failover, multiple cooperating agents, MCP infrastructure, or a general agent harness for the first loop.
- The current Ollama planner is not the canonical future kernel. It may remain temporarily as legacy/specialist code, but it is not on the first-loop critical path.

### Context and privacy boundary

Remote models receive only code-selected, allowlisted context. Initial automatic context is limited to:

- the current task or explicit task description;
- the linked project summary when explicitly linked and allowed;
- the last relevant session capsule;
- a small number of recent task outcomes;
- material explicitly marked as helper-accessible.

The model must not browse the whole vault or decide which private files to retrieve. Journals, health notes, relationship notes, unrelated daily notes, and attachments are excluded by default unless a later explicit policy allows them.

### Authority and approval

The first loop may automatically:

- read allowlisted context;
- maintain temporary interaction/run state;
- queue and retry requests;
- create proposal/card artifacts;
- record button responses and outcomes.

Explicit approval remains required for:

- creating or changing durable commitments;
- editing ordinary personal notes;
- modifying TaskNotes;
- changing calendar entries;
- sending messages;
- consequential external actions.

Real TaskNotes apply is not required for the first loop and remains deferred.

### Proposal surfaces

For future durable proposals, the newer Obsidian intent/proposal/approval/task-draft chain is the canonical direction. The older `llm-planner`/`AI/proposed-tasks` surface is legacy/specialist compatibility until deliberately retired or adapted. New work must not create a third proposal protocol.

The first task-initiation loop itself does not need to create a durable task proposal.

### Evaluation

The first trial is judged primarily by behavior and burden:

- **start rate**: proportion of `Stuck` interactions followed by `Start` within ten minutes;
- **meaningful engagement**: proportion of starts followed by completion of the proposed micro-action or at least ten minutes of work;
- **subjective friction**: occasional answer to “Did this make starting easier?”;
- **guardrails**: dismissal, repeated-shrink, wrong-task, annoyance, latency, retry, and expiry rates.

Mechanical schema success alone is not sufficient evidence that the loop should be retained.

## Consequences

- The project has a canonical direction without claiming that the kernel is already implemented.
- Most simple button actions remain deterministic and model-free.
- Tasker becomes the first low-friction interface, while Obsidian remains the durable review surface.
- API cost, latency, privacy, and offline behavior become explicit engineering concerns.
- TaskNotes apply, general prioritization, broad coaching, and autonomous agents are removed from the first-loop dependency chain.
- Existing components should be reused where their contracts fit, but no existing service is assumed to be the canonical orchestrator merely because it already exists.

## Alternatives considered

- **Autonomous harness reads the vault and controls the loop.** Rejected because it weakens predictability, privacy minimization, authority separation, and evaluation.
- **Combine task choice and task initiation.** Rejected because it mixes two different problems and makes the first trial difficult to interpret.
- **Run the primary kernel on a Pi/cloud server.** Deferred because laptop-first operation is sufficient for the selected loop and reduces deployment complexity.
- **Use local models as the primary reasoning path.** Rejected for the first loop because of laptop hardware limits; Ollama may remain as non-critical legacy/fallback experimentation.
- **Support multiple providers immediately.** Rejected as premature complexity.
- **Permit whole-vault retrieval and forbid sensitive areas later.** Rejected because remote disclosure cannot be undone; context starts allowlisted.
- **Complete TaskNotes apply before testing usefulness.** Rejected because the initiation loop does not require durable task mutation.
- **Introduce LangGraph, Temporal, DBOS, or MCP immediately.** Rejected until actual pause/resume, distributed execution, or shared-tool requirements justify them.

## Conditions for revisiting

Revisit this decision if:

- laptop availability makes the Tasker loop materially unreliable;
- interactions routinely need to survive for days rather than hours;
- one-provider operation creates unacceptable availability or quality problems;
- the first loop requires complex branching or durable human approval waits;
- real-use evidence shows that task selection, not initiation, is the dominant problem;
- a broader context category is demonstrably necessary and can be allowed safely.
