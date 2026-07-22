# Architecture

## Purpose

This subsystem is a local-first, inspectable, recovery-oriented goal-achievement companion. It coordinates context, reflection, planning, review, bounded interaction, and selected live actions without turning a model into an unrestricted controller.

The architectural rule is:

```text
ordinary software owns lifecycle and authority;
models provide bounded proposal-side judgment.
```

## System surfaces

| Surface | Role |
| --- | --- |
| AI vault | Machine-readable queues, state, projections, drafts, events, reports, and evidence. |
| Obsidian | Human review, explanation, planning, and interaction surface. |
| TaskNotes | Durable human commitment surface. |
| Phone/desktop | Low-friction capture, telemetry, notifications, and bounded commands. |
| Context providers | Read-only normalization of relevant evidence. |
| Planner/model workers | Structured proposals, summaries, classifications, and drafts. |
| Deterministic gates | Validation, authority checks, idempotency, and safe mutation. |

## Current implementation topology

```text
Phone telemetry ----------> phone-bridge -------------------+
Tasker/live commands ------> AI/inbox/actions --------------+--> action-bridge
Desktop question answer ---> dialog-bridge action file ------+       |
                                                                  state/events/actions

Local sources ---> context providers ---> context_hub / agent_context
                                          |                  |
                                          |                  +--> recovery trigger/proposals
                                          +--> older llm-planner (Ollama)
                                          +--> Obsidian prompt/proposal packages

Obsidian input
  -> obsidian ingress
  -> intent
  -> deterministic or LLM proposal contract
  -> review action
  -> approval bridge
  -> reviewed proposal
  -> TaskNotes-compatible draft
  -> TaskNotes apply validator
  -X-> real TaskNotes write (not implemented)

Intervention/action/recovery evidence
  -> interaction projection
  -> intervention outcomes/statistics
```

This topology contains many kernel components, but orchestration is distributed. There is no canonical general event router that owns every run from ingress through later outcome.

## Architectural layers

### 1. Interaction adapters

Tasker, phone files, desktop notifications, Obsidian commands, and future launchers should translate user/environment signals into typed events or intents. They should contain little behavioral intelligence.

### 2. Event and state layer

- Queue entries represent commands or intents.
- State files are materialized current views.
- Projection modules derive interaction views from lifecycle evidence.
- Event/JSONL records are evidence, not automatically authoritative audit history.
- A future canonical run identity should connect trigger, context, proposal, decision, action, and outcome.

### 3. Context layer

Context providers normalize bounded facts from local sources. Retrieval must decide what a model receives; a model should not roam the vault to choose its own private context.

Provider results should carry:

- source/provenance;
- observed and generated timestamps;
- freshness/expiry;
- limits and omissions;
- availability/warnings;
- no mutation authority.

### 4. Policy and routing layer

Current policy is distributed across Nix options, environment variables, `ACTION_CAPABILITY_POLICY`, deterministic gates, lifecycle helpers, and producer-specific logic.

A future canonical kernel may centralize route selection, but hard enforcement should remain in deterministic validators and action adapters rather than in prompt instructions.

### 5. Planner/model layer

Models may classify, summarize, propose, draft, and explain. Model outputs that affect software behavior must cross a schema boundary and deterministic validation.

Most events should remain model-free. Model calls are appropriate only when judgment is necessary, such as:

- interpreting an ambiguous capture;
- diagnosing a blocker;
- proposing a small next action;
- decomposing a project;
- summarizing weekly patterns.

### 6. Review and approval layer

Obsidian-facing artifacts make proposals inspectable. Approval records must identify the proposal/intent being approved and must not be treated as broad execution authorization.

### 7. Action adapters

`action-bridge` currently owns intentional live actions from `AI/inbox/actions/*.json`. It validates capabilities, journals processing, enforces idempotency, and calls explicit handlers.

The numeric authority level is transitional. Named capabilities are the direction of travel.

### 8. Outcome and learning layer

Interaction projection and intervention outcome modules provide mechanical outcome evidence. The future learning kernel should store:

```text
evidence
  -> bounded hypothesis
  -> proposed policy/intervention
  -> human feedback
  -> observed outcome
  -> correction, expiry, or revision
```

It should not silently convert a few events into permanent personality claims.

## TaskNotes boundary

TaskNotes is not an LLM scratchpad.

Current implemented chain:

```text
intent/proposal
  -> explicit review decision
  -> reviewed proposal
  -> TaskNotes-compatible draft
  -> deterministic apply validation
```

Current missing chain:

```text
validated apply request
  -> atomic write to configured TaskNotes root
  -> apply journal/result
  -> conflict and replay handling
```

Direct legacy promotion remains disabled.

## Proposal-surface transition

Two proposal families coexist:

1. older `llm-planner` reports, nudges, questions, and `AI/proposed-tasks`;
2. newer Obsidian intents, proposals, approvals, and task drafts.

Both are proposal-side, but their ownership and convergence are unresolved. New features should not create a third proposal surface.

## Model-runtime transition

The current planner is coupled to local Ollama. The intended user direction is API-hosted models because client hardware is limited.

The target should remain provider-neutral:

```text
kernel/task contract
  -> provider adapter
  -> schema-bound model result
  -> deterministic validator
```

Changing providers must not widen authority. Remote use additionally requires local secret ownership, context minimization, cost/latency budgets, retry policy, and offline/fallback behavior.

## Target kernel shape - not yet implemented

```text
validated event
  -> append evidence / reduce current state
  -> deterministic route decision
       -> no intervention
       -> deterministic handler
       -> bounded skill/model invocation
  -> context packet selected by code
  -> schema-bound proposal
  -> validator and capability gate
  -> human approval where required
  -> deterministic action adapter
  -> action/run result
  -> later outcome linkage
```

The kernel should know when **not** to think. A done, snooze, start, dismiss, or fixed defer action usually requires no model call.

## Quality attributes

| Attribute | Architectural implication |
| --- | --- |
| Local-first | Full personal state remains local; remote models receive minimized context packets. |
| Inspectable | Important state, proposals, decisions, capabilities, and evidence are reviewable. |
| Recovery-oriented | Optimize for humane re-entry and safe silence, not escalating pressure. |
| Safe mutation | Side effects occur only through explicit deterministic adapters and gates. |
| Idempotent | Repeated or resumed processing must not duplicate consequences. |
| Modular | Skills/providers/adapters communicate through schemas and declared contracts. |
| Evaluated | Mechanical tests and product-usefulness evaluations are separate and both required. |
| Reversible | Personal-model claims and policies can be corrected, expired, or removed. |

## Current architecture questions

Canonical unresolved questions are tracked in `workflow/OPEN_QUESTIONS.md`. Decisions should be recorded in ADRs or `workflow/DECISIONS.md`, not buried in implementation comments.
