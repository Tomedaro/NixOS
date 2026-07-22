# Architecture findings

Snapshot date: 2026-07-22.

This is the current architecture assessment. Earlier audit findings that have been resolved are retained here only as status context; code, tests, and canonical top-level docs remain authoritative.

## Executive summary

No current red-level implementation defect was found in the reviewed archive. The repository has strong proposal/execution separation, bounded context, disabled direct TaskNotes mutation, deterministic validation, conservative action replay, and broad smoke coverage.

The main risks are now architectural consolidation and product validation rather than an obvious unsafe code path.

## Resolved high-severity findings

### RESOLVED-HIGH-001 - Direct action-bridge TaskNotes promotion

`promote_task_proposal` / `promote_proposal` are disabled and fail without writing real TaskNotes. There is no live `tasknotes.promote` capability.

### RESOLVED-HIGH-002 - Anki direct TaskNotes mode

Nix direct mode is removed/hard-disabled. Raw legacy `TASKNOTE_MODE=direct` falls back to proposal behavior.

### RESOLVED-MEDIUM-001 - Dialog answer bypass

`dialog-bridge` queues canonical `answer_question` actions; `action-bridge` owns lifecycle mutation. A desktop dismiss action should not be emitted until the UI has a genuine dismiss signal.

## Current findings

### HIGH-001 - Canonical runtime orchestration is unresolved

The repository contains context, routing/gating, proposal, approval, action, projection, and outcome components, but no single component owns the full event-to-outcome lifecycle.

Why it matters:

- state ownership can diverge across services;
- model calls and deterministic handlers may evolve separately;
- end-to-end tracing and idempotency remain fragmented;
- adding more triggers risks parallel brains.

Treatment: decide and document the canonical orchestrator before adding broad autonomous behavior.

### HIGH-002 - Implemented model runtime conflicts with intended API direction

The current planner is Ollama-specific and local-model configured. The intended user direction is API-hosted models because of hardware limits, but no provider abstraction, secret boundary, privacy-minimized context contract, cost budget, or fallback policy exists.

Treatment: record a provider/runtime decision before refactoring planner internals or adding API-triggered automation.

### HIGH-003 - Proposal ownership is duplicated

The older planner writes reports, questions, nudges, and `AI/proposed-tasks`; the newer Obsidian chain produces intents, proposals, decisions, reviewed proposals, and task drafts.

Both preserve proposal-side authority, but their canonical relationship is unresolved.

Treatment: consolidate ownership or explicitly define one as adapter/specialist/legacy compatibility.

### MEDIUM-001 - TaskNotes apply is partially implemented and easily misdescribed

The repository implements reviewed drafts and deterministic apply validation. It does not implement the real atomic TaskNotes mutation, apply journal, or conflict/replay result path.

Treatment: consistently say **validation**, not **apply**, until the mutation path exists.

### MEDIUM-002 - Protocol and schema documentation lagged implementation

Source contains 44 versioned schema identifiers and many queue/state/projection paths. Earlier `PROTOCOLS.md` described only a small subset.

Treatment: maintain `PROTOCOLS.md` plus `docs/SCHEMA_REGISTRY.md`; eventually generate/check inventories from source.

### MEDIUM-003 - JSONL remains evidence-only

JSONL append helpers are useful but do not currently specify writer locking, fsync, recovery, tamper evidence, or canonical ordering sufficient for authoritative audit claims.

Treatment: keep evidence-only wording or introduce a stronger run ledger.

### MEDIUM-004 - Product usefulness is not yet validated

Smoke tests demonstrate mechanical behavior, not whether interventions reduce resistance or improve meaningful execution.

Treatment: validate one end-to-end product loop with burden, timing, correction, and recovery outcomes before expanding automation.

### MEDIUM-005 - Policy is distributed across several authority surfaces

Nix options, environment variables, numeric authority, named capability metadata, lifecycle helpers, and producer-specific rules all influence behavior.

Treatment: preserve deterministic local gates while making ownership and precedence explicit.

### LOW-001 - Historical audit documents can masquerade as current plans

Earlier findings, inventory, restructuring, and handoff documents contained completed tasks and stale counts.

Treatment: mark historical documents clearly and route current truth through the canonical top-level docs.

### LOW-002 - Target-machine verification remains required

Archive review cannot prove Nix evaluation, service state, vault permissions, Tasker behavior, provider connectivity, or live user experience.

Treatment: preserve a separate target-machine verification log.

## Positive findings

### POS-001 - Proposal/execution boundary is coherent

The strongest design property is the repeated separation of context/proposal/draft from deterministic action and durable commitment mutation.

### POS-002 - Replay and idempotency protections are substantial

Stable-file checks, identity caches, processing journals, explicit result states, and manual-review handling provide a strong prototype foundation.

### POS-003 - Context privacy and boundedness are taken seriously

TaskNotes context and LLM prompt packages omit raw/absolute provider details and carry limits/provenance.

### POS-004 - Mechanical regression surface is broad

Thirty smoke-test files cover many of the important protocol boundaries.

### POS-005 - The design resists the “one giant autonomous agent” failure mode

Modules are narrow, proposal-side, inspectable, and generally safe-off. The next task is consolidation, not replacement with an unconstrained harness.
