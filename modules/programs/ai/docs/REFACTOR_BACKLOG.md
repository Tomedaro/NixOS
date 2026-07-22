# Refactor backlog

Snapshot date: 2026-07-22.

This backlog records concrete implementation candidates. `ROADMAP.md` owns dependency order; `CURRENT_STATE.md` owns implementation truth. Completed items are retained only when they clarify prerequisites.

## Completed foundations

### R-0002 - Remove/disable legacy direct TaskNotes mutation

Status: completed.

- `action-bridge` proposal promotion is disabled.
- Anki direct TaskNotes mode is removed/hard-disabled.
- Reviewable proposals and drafts remain available.

### R-0003 - Route dialog answers through canonical actions

Status: completed for answers.

- `dialog-bridge` queues `answer_question` action files.
- `action-bridge` owns lifecycle mutation.
- Remaining UI follow-up: emit dismiss only when a real dismiss signal exists.

### R-0201 - Add read-only TaskNotes context

Status: completed.

- bounded/provenanced provider;
- no TaskNotes mutation capability;
- context-hub exposure;
- safe prompt-boundary metadata;
- smoke coverage.

### R-0202A - Add deterministic TaskNotes apply validation

Status: completed.

- verifies reviewed approval identity and schemas;
- rejects direct-execution fields and unsafe targets;
- detects target collision;
- produces deterministic idempotency inputs and validation result;
- does not write TaskNotes.

## Active architecture blockers

### R-0401 - Decide and document canonical runtime orchestration

Severity: high.

Need:

- event ingress owner;
- state reduction/materialization owner;
- route/skill selection;
- deterministic-versus-model decision;
- context packet assembly;
- run identity and outcome linkage;
- restart/idempotency semantics.

Do not implement a broad autonomous loop before this decision.

### R-0402 - Introduce a provider-neutral model boundary

Severity: high.

Current problem: planner internals are Ollama-specific while intended deployment prefers APIs.

Need:

- provider/model adapter contract;
- local secret ownership;
- privacy-minimized context packets;
- structured output and validation behavior;
- timeout/retry/cost/usage budgets;
- fallback/offline policy;
- explicit treatment of existing Ollama planner.

### R-0403 - Consolidate proposal surfaces

Severity: high.

Decide the ownership relationship between:

- older reports/questions/nudges and `AI/proposed-tasks`;
- newer Obsidian intent/proposal/approval/task-draft chain.

Acceptance condition: new features have one canonical proposal contract or an explicitly documented adapter relationship.

### R-0404 - Select first complete product loop

Severity: high/product.

Choose one bounded loop and define:

- trigger;
- required context;
- deterministic/model decision points;
- interaction card/controls;
- possible actions;
- outcome evidence;
- burden, correction, and backoff evaluation.

## Authority and protocol hardening

### R-0001 - Continue named-capability migration

Status: partial.

- `ACTION_CAPABILITY_POLICY` exists.
- `recovery.target.start` is default-off.
- numeric authority and several default-enabled gates remain transitional.

Any further default flip requires the checklist in `SAFETY_MODEL.md` and full regression coverage.

### R-0103 - Add canonical run/trace record

Severity: medium/high.

Link:

```text
event -> state/context refs -> model/proposal -> validation -> decision -> action result -> outcome
```

This record must not require hidden chain-of-thought.

### R-0104 - Decide authoritative event storage

Severity: medium.

Either:

- keep JSONL explicitly evidence-only; or
- harden/replace it for authoritative run history with locking, fsync, recovery, and ordering semantics.

### R-0105 - Generate/check path and schema inventories

Severity: medium/docs/protocol.

- compare vault-created paths against `PROTOCOLS.md`;
- compare source schema identifiers against `docs/SCHEMA_REGISTRY.md`;
- fail documentation checks on drift where practical.

## TaskNotes apply work - conditional on product decision

### R-0202B - Implement real deterministic TaskNotes apply

Severity: high if selected.

Requires:

- explicit apply request and reviewed identity;
- atomic write under configured root;
- no overwrite without explicit conflict policy;
- idempotent replay;
- apply journal/result and event provenance;
- manual review for ambiguous conflicts;
- accepted/refused/conflict/replay tests.

This item may remain deferred if the first product loop does not require durable commitment creation.

## Product intelligence and evaluation

### R-0301 - First-class goal and commitment contracts

Define values/life areas, goals, projects/habits, commitments/tasks, sessions, interventions, and outcomes without forcing all ideas into tasks.

### R-0302 - Attention and receptivity policy

Unify quiet hours, low-energy mode, repeated-ignore backoff, active-work suppression, channel selection, and silence as a valid action.

### R-0303 - Inspectable personal-model records

Add evidence, confidence, expiry, correction, rejection, and supersession semantics.

### R-0304 - Product scenario and real-use evaluation

Measure next-action quality, time to start, meaningful continuation, burden, wrong inference, stale context, repeated nudges, low energy, and recovery quality.

### R-0305 - UI adapters after canonical events

Tasker cards, desktop launcher/popups, and richer phone surfaces should remain thin adapters over canonical events and capabilities.
