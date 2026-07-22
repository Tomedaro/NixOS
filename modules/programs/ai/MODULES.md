# Modules

This is the high-level current module map. Detailed review evidence belongs in `docs/MODULE_REVIEW_REGISTER.md`. Side-effect levels describe intended authority, not merely whether a file is written.

## Runtime and service modules

| Module | Purpose | Side-effect level | Current notes |
| --- | --- | --- | --- |
| `core` | Canonical vault, AI, TaskNotes, timezone, and protocol path options. | Configuration reference | Path naming source for Nix modules. |
| `vault-bridge` | Creates the AI vault directory skeleton and seed policy/control files. | Local-state initialization | Also creates `TaskNotes/AI`; seeded text still reflects the older `proposed-tasks` surface. |
| `action-bridge` | Processes the canonical live action queue. | High/live action | Uses validation, capabilities, journals, idempotency, stable-file checks, and manual review; TaskNotes promotion actions are disabled. |
| `phone-bridge` | Ingests passive phone telemetry and updates phone-facing state/logs. | Medium/local state | Intentional commands belong in `AI/inbox/actions`, not the telemetry inbox. |
| `dialog-bridge` | Desktop question/notification adapter. | Medium | Queues `answer_question`; its timer is disabled by default. |
| `session-manager` | Session lifecycle and control-file compiler. | Medium | Writes session/control state and supports explicit session actions. |
| `coach-daemon` | Immediate desktop coaching/context loop. | Medium | Enabled by default; has freshness/grace/cooldown controls. |
| `recovery-manager` | Classifies and records recovery lifecycle state. | Medium | Does not own broad planning. |
| `recovery-trigger` | Builds/gates recovery nudges from state. | Medium | Implemented but disabled by default. |
| `intervention-outcomes` | Periodically summarizes intervention outcomes. | Low/medium | Timer enabled by default; not a complete product evaluator. |
| `anki-bridge` | Reads Anki status and produces recovery/task proposals. | Observe + propose | Direct TaskNotes mode is removed/hard-disabled. |
| `llm-planner` | Older report, question, nudge, and proposed-task planner. | Proposal/local state | Ollama-specific; enabled for manual use but timer disabled. Ownership relative to the newer Obsidian proposal chain is unresolved. |
| `ollama` | Local model runtime module. | Runtime/service | Current implemented model backend; remote API provider support does not exist yet. |
| `phone-webview` | Phone card asset and installer. | Optional local mutation | Presentation/integration surface rather than kernel logic. |
| `activitywatch`, `browser-bridge`, `hypr-agent`, `notifications`, `screenpipe`, `compat` | Optional, stub, compatibility, or future integrations. | Varies | Must not become parallel orchestration layers. |

## Shared kernel components

| Module | Purpose | Authority |
| --- | --- | --- |
| `agent_context.py` | Builds bounded planner/agent context and context-hub snapshots. | Read/derive |
| `context_schema.py` | Shared provider and context-hub result contracts. | Pure schema |
| `context_providers.py` | Read-only providers for interactions, Anki, recovery, interventions, Obsidian, ActivityWatch, and TaskNotes context. | Read/derive |
| `events.py` | Shared event construction helpers. | Pure/record helper |
| `interaction_lifecycle.py` | Pure lifecycle decisions for active nudges, expiry, actions, and recovery terminal state. | Pure policy helper |
| `interaction_projection.py` | Projects event/lifecycle state into current phone interaction views. | Local-state projection |
| `interventions.py` | Records proposed/gated/shown intervention evidence. | Evidence/local state |
| `intervention_outcomes.py` | Derives outcome records and statistics from intervention/action evidence. | Read/derive/write summary |
| `recovery_targets.py` | Recovery target registry/lookup. | Pure configuration helper |
| `recovery_proposals.py` | Builds deterministic recovery proposal/reasoning records. | Draft/propose |
| `proposal_gate.py` | Deterministic gate for recovery proposal actions. | Validation only |
| `io_utils.py` | Atomic JSON/text writes and JSONL append helper. | Utility; side effect depends on caller |
| `queue.py` | Stable queue-file discovery and unique moves. | Utility; local queue mutation |
| `status.py`, `time_utils.py` | Shared status and time normalization. | Pure/helper |

## Obsidian and model proposal components

| Module | Purpose | Authority |
| --- | --- | --- |
| `obsidian_interaction.py` | Shared Obsidian message/action/interaction schemas and rendering. | Protocol helper |
| `obsidian_context.py` | Builds bounded Obsidian context artifacts. | Read/derive |
| `obsidian_contracts.py` | Shared bounds, forbidden execution fields, and parsing/validation helpers. | Pure contract helper |
| `obsidian_ingress.py` | Converts Obsidian-origin input into bounded intent records. | Intake only |
| `obsidian_intent_planner.py` | Produces reviewable proposals from intents/context. | Draft/propose |
| `llm_proposal_contract.py` | Builds prompt packages and validates schema-bound model proposals. | Proposal validation |
| `obsidian_proposal_action.py` | Records approve/reject/revise decisions. | Review capture |
| `obsidian_approval_bridge.py` | Validates approval identity and writes reviewed proposal artifacts. | Review bridge |
| `obsidian_task_draft.py` | Normalizes reviewed proposals into TaskNotes-compatible draft artifacts. | Draft only |
| `tasknotes_apply_validator.py` | Dry-run validator for applying a reviewed draft to an allowed TaskNotes target. | Deterministic validation; no TaskNotes write |

## Development and verification components

| Module | Purpose | Notes |
| --- | --- | --- |
| `dev/run-obsidian-agent-loop.sh` | Operator/development execution of the Obsidian proposal chain. | Not the canonical general runtime kernel. |
| `dev/interaction_surface.py` | Development interaction-surface helper. | UI/testing support. |
| `dev/check-*`, `dev/audit-*`, `dev/llm/*` | Diagnostics and documentation/patch verification. | Live checks should default read-only. |
| `tests/*_smoke.py` | Mechanical regression tests. | 30 smoke-test files in the current repository; product scenarios remain separate. |
| Nix `default.nix` files | Service wiring, options, environment gates, and effective defaults. | Configuration authority. |

## Current orchestration status

No single module currently owns the complete lifecycle:

```text
event ingress
  -> state reduction
  -> route/skill selection
  -> context assembly
  -> optional model call
  -> proposal validation
  -> approval
  -> action dispatch
  -> outcome linkage
```

Those responsibilities are distributed among bridges, planners, queue handlers, operator scripts, and shared Python modules. This decomposition is useful, but canonical orchestration remains an open architecture decision.

## Module review rule

For every meaningful module, the detailed register should list:

- purpose and owner role;
- current status and effective defaults;
- inputs, outputs, queue/state paths, and schemas;
- side effects and required capabilities;
- disable/safe-off behavior;
- tests and evaluation scenarios;
- TaskNotes mutation status;
- known duplication or ownership conflicts.

A read-only module such as `tasknotes.read_context` requires no live action capability. Future real TaskNotes apply must be a separate capability and deterministic gate.
