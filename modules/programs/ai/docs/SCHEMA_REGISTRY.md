# Schema registry

Snapshot date: 2026-07-23.

This registry inventories versioned protocol identifiers currently present in source. It is documentation, not generated validation code. Exact fields and constraints remain authoritative in the producing/validating modules.

Status legend:

- **current**: active contract used by current code/tests;
- **transitional**: active but expected to be consolidated or replaced;
- **evidence**: record/report rather than command authority;
- **planned**: reserved future contract, not implemented.

## Core action, state, context, and event schemas

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `action.v1` | current | `action-bridge`, `dialog-bridge` | Canonical live action command envelope. |
| `action_id_cache.v1` | current | `action-bridge` | Processed action identity cache. |
| `action_processing_journal.v1` | current | `action-bridge` | Per-action processing/replay journal. |
| `event.v1` | evidence | shared events, bridges | Generic evidence event envelope. |
| `agent_context.v1` | current | `agent_context` | Bounded assembled agent/planner context. |
| `context_provider.v1` | current | `context_schema` | Individual provider result envelope. |
| `context_hub.v1` | current | `context_schema`, `agent_context` | Aggregated provider snapshot. |
| `anki-status.v1` | current | `anki-bridge` | Anki status snapshot. |

## Interaction schemas

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `phone_interaction.v1` | current/transitional | planner, action bridge, projection | Nudge/question interaction artifact. |
| `phone_interaction_state.v1` | current | action bridge, projection, trigger | Materialized active interaction state. |
| `pending_question.v1` | transitional | older `llm-planner` | Older pending-question record. |
| `interaction_projection_event.v1` | evidence | `interaction_projection` | Projection lifecycle evidence. |
| `interaction_projection_refresh.v1` | evidence | `interaction_projection` | Projection refresh result. |

## Recovery and intervention schemas

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `recovery_context.v1` | current | `context_providers` | Recovery context facts. |
| `recovery_reasoning.v1` | current | `recovery_proposals` | Inspectable deterministic recovery reasoning. |
| `agent_recovery_proposal.v1` | current | `recovery_proposals`, `agent_context` | Proposed recovery intervention. |
| `proposal_validation_result.v1` | current | `proposal_gate` | Recovery proposal validation result. |
| `validated_recovery_proposal.v1` | current | `proposal_gate` | Gated recovery proposal. |
| `recovery_trigger_decision.v1` | current | `recovery-trigger` | Trigger decision and references. |
| `recovery_session.v1` | current | `action-bridge` | Recovery lifecycle/session state. |
| `intervention_ref.v1` | current | recovery/action modules | Cross-record intervention identity/reference. |
| `intervention_outcome.v1` | evidence | `intervention_outcomes` | Derived outcome record. |
| `intervention_outcome_stats.v1` | evidence | `intervention_outcomes` | Aggregated outcome statistics. |
| `intervention_outcome_report.v1` | evidence | outcome reporter | Periodic human/machine report. |

## Obsidian interaction and proposal schemas

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `obsidian_message.v1` | current | `obsidian_interaction` | Obsidian-facing message envelope. |
| `obsidian_action.v1` | current | `obsidian_interaction` | Obsidian-side review/control action envelope. |
| `obsidian_interaction.v1` | current | `obsidian_interaction` | Shared interaction artifact. |
| `obsidian_context.v1` | current | `obsidian_context` | Bounded Obsidian context record. |
| `obsidian_intent.v1` | current | `obsidian_ingress` | Bounded user intent. |
| `obsidian_intent_context.v1` | current | `context_providers` | Context-provider representation of current intent. |
| `obsidian_intent_provider.v1` | current | `context_providers` | Provider result details for intent context. |
| `planner_context_refs.v1` | current | `obsidian_intent_planner` | Evidence/context references used by proposal generation. |
| `obsidian_planner_result.v1` | current | `obsidian_intent_planner` | Planner execution/result envelope. |
| `obsidian_proposal.v1` | current | proposal contract/planner | Reviewable proposal. |
| `obsidian_proposal_action.v1` | current | proposal action/approval bridge | Approve/reject/revise decision. |
| `obsidian_reviewed_proposal.v1` | current | approval bridge | Proposal plus explicit reviewed decision. |
| `obsidian_approval_bridge_result.v1` | evidence | approval bridge | Approval processing result. |
| `obsidian_task_draft.v1` | current | task draft normalizer | Reviewable TaskNotes-compatible draft, not a commitment. |
| `tasknotes_apply_validation_result.v1` | current | apply validator | Dry-run validation result; no real write. |

## LLM proposal-package schemas

| Schema | Status | Primary owner | Role |
| --- | --- | --- | --- |
| `llm_intent_ref.v1` | current | `llm_proposal_contract` | Bounded intent reference. |
| `llm_context_refs.v1` | current | `llm_proposal_contract` | Bounded evidence/context references. |
| `llm_contract_ref.v1` | current | `llm_proposal_contract` | Contract/policy reference. |
| `llm_prompt_package.v1` | current | `llm_proposal_contract` | Schema-bound input package for model invocation. |
| `llm_proposal_validation_result.v1` | current | `llm_proposal_contract` | Model-output validation result. |


## Task-initiation first-loop schemas

Review date: 2026-07-23. Five stable boundary contracts are candidates for Milestone 1 freezing. One provisional Receipt and one deferred Outcome are documented but excluded from the frozen set. Internal records (error, idempotency, interaction, run, queue, transition) are unversioned private data structures without `schema_version` or registry entries.

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `task_initiation_stuck.v1` | candidate/external | `task_initiation_contracts` | Untrusted Stuck ingress event with inline TaskRef; zero client expiry/idempotency fields. |
| `task_initiation_card.v1` | candidate/external | `task_initiation_contracts` | Immutable display/countdown card with kernel-generated opaque UUIDs and server expiry. |
| `task_initiation_response.v1` | candidate/external | `task_initiation_contracts` | Minimal user action evidence; accepted before Receipt, first-response-wins. |
| `task_initiation_context.v1` | candidate/model-boundary | `task_initiation_contracts` | Local disclosure/audit manifest with derived minimal API payload (`model_content_sha256`). |
| `task_initiation_proposal.v1` | candidate/model-boundary | `task_initiation_contracts` | Semantic-only blocker + tiny-start output; passes deterministic direct-execution safety gate. |

### Provisional (excluded from frozen set)

| Schema | Status | Primary owner(s) | Role |
| --- | --- | --- | --- |
| `task_initiation_card_receipt.v1` | provisional/planned | `task_initiation_contracts` | Tasker notification-posted evidence; exact shape frozen in Milestone 3 after live posting-evidence test. |

## Missing future schemas

No versioned contract currently exists for:

- `task_initiation_outcome.v1` — deferred to Milestone 5; evidence documented, producers and shape to be finalized;
- first-loop kernel runtime state and transaction contracts;
- canonical general kernel run/trace;
- provider-neutral model request/result metadata;
- model cost/latency/usage budget record;
- authoritative TaskNotes apply request/result/journal;
- personal-model hypothesis/correction/supersession;
- unified goal hierarchy and commitment record;
- cross-producer attention/receptivity decision.

These should be introduced only when ownership and semantics are decided, not predeclared speculatively.
