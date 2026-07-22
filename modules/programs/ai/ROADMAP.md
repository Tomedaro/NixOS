# Roadmap

This file records dependency-ordered future work. It is not current-state documentation and does not assign dates.

The roadmap is intentionally divided into **decision gates**, **implementation milestones**, and **continuing invariants**. A precise delivery sequence is possible only after the decision gates are resolved in `workflow/OPEN_QUESTIONS.md` and promoted to ADRs or `workflow/DECISIONS.md`.

## Continuing invariants

These are not roadmap features; they must remain true during every future change:

- LLM/model paths remain proposal-side.
- Direct TaskNotes mutation remains disabled until a deterministic reviewed apply path is complete.
- Default-off `recovery.target.start` regression coverage remains intact.
- Dangerous authority is represented by explicit capabilities and gates, not prompt wording alone.
- Bounded context omits unnecessary private material and preserves provenance.
- Ambiguous replay or conflict moves to refusal/manual review rather than repeating side effects.
- Automatic interventions remain conservative until product scenarios demonstrate acceptable burden and recovery quality.

## Decision gate 0 - establish canonical ownership

Resolve and record:

1. **Canonical runtime orchestrator**: which component owns event ingress, routing, context assembly, optional model invocation, validation, approval, action dispatch, and outcome linkage.
2. **Model-provider direction**: provider-neutral API runtime, treatment of the current Ollama planner, secrets, privacy boundary, cost limits, fallback, and offline behavior.
3. **Canonical proposal surface**: relationship between `AI/proposed-tasks`, planner reports/nudges, and the newer Obsidian proposal/approval/task-draft chain.
4. **First complete product loop**: one end-to-end loop to validate before broad feature expansion.
5. **TaskNotes apply timing**: whether real TaskNotes apply is required for the first product loop or can remain deferred.

Exit condition: accepted decisions exist and contradictory ownership statements are removed from canonical docs.

## Milestone 1 - canonicalize protocols and runtime truth

- Keep `CURRENT_STATE.md`, `MODULES.md`, `ARCHITECTURE.md`, `PROTOCOLS.md`, and `docs/SCHEMA_REGISTRY.md` synchronized with code.
- Define one run/trace identity linking event, context references, model/proposal result, validation, human decision, action result, and later outcome.
- Clarify state ownership for interactions, recovery, proposals, and current projections.
- Decide whether JSONL remains evidence-only or is replaced/hardened for authoritative run history.
- Complete the module-contract register for implemented kernel components.

Exit condition: each canonical path/schema has an owner, each side effect has a capability/gate, and one runtime flow can be traced end to end.

## Milestone 2 - consolidate the model and proposal boundary

- Introduce a provider boundary rather than embedding one model runtime throughout planning code.
- Preserve schema-bound model outputs and deterministic validators.
- Define privacy-minimized context packets for remote APIs.
- Resolve the older planner versus Obsidian proposal-chain ownership.
- Add per-run budgets for requests, tool calls, tokens, latency, and estimated cost.

Exit condition: switching model/provider does not change action authority or protocol ownership, and no model output bypasses proposal validation.

## Milestone 3 - complete or deliberately defer TaskNotes apply

Already complete:

- read-only TaskNotes context;
- reviewed proposal artifacts;
- TaskNotes-compatible drafts;
- deterministic dry-run validation.

Remaining if real apply is selected:

- atomic write into an allowed TaskNotes root;
- explicit apply request and approval identity;
- idempotent replay behavior;
- target conflict/manual-review handling;
- apply result and provenance record;
- accepted/refused/conflict/replay smoke tests.

Exit condition: either the apply path is complete and tested, or its deferral is an explicit accepted product decision.

## Milestone 4 - validate one useful product loop

Choose one bounded loop, likely `stuck/help-now`, low-energy recovery, or stale-task review.

Required evaluation dimensions:

- correct routing;
- concrete next action quality;
- time and friction to invoke;
- start/continuation outcome;
- burden and annoyance;
- wrong-inference correction;
- safe silence/backoff;
- recovery after dismissal or failure.

Exit condition: scenario tests and real-use records demonstrate that the loop is useful enough to retain and safe enough to automate conservatively.

## Milestone 5 - inspectable learning and policy adaptation

- Define evidence references and hypothesis records.
- Add correction, rejection, expiry, and supersession semantics.
- Define the goal hierarchy and commitment semantics.
- Implement attention/receptivity policy across producers.
- Permit only bounded, reviewable policy proposals before automatic adaptation.

Exit condition: every learned claim is inspectable, correctable, attributable to evidence, and reversible.

## Milestone 6 - expand interfaces and instruments

Only after earlier milestones are stable:

- Tasker action cards and richer phone controls;
- desktop command palette or popup;
- calendar/context adapters;
- body-doubling or distraction-control adapters;
- additional read-only context providers;
- richer planning and study/coaching skills.

Exit condition: new interfaces are thin adapters over canonical events and capabilities rather than new parallel brains.
