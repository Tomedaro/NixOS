# ai_system shared package

`ai_system` contains shared, deterministic helpers for the local AI productivity system.

The package exists to keep critical contracts centralized instead of duplicated across bridges, managers, triggers, and future agent code.

## Current modules

### `io_utils.py`

Shared filesystem helpers:

```text
atomic_write_text
atomic_write_json
read_text
read_json
read_jsonl
append_jsonl
```

These helpers are intentionally boring and deterministic. They are safe for services and smoke tests.

### `time_utils.py`

Shared timezone/time helpers:

```text
get_timezone
now
now_iso
today
```

### `events.py`

Event normalization and append helpers used by telemetry bridges.

### `queue.py`

Stable-file and unique-move helpers for inbox processing.

### `status.py`

Small status JSON/Markdown writer.

### `recovery_targets.py`

Shared recovery target registry.

This is the source of truth for target metadata such as:

```text
target id
display name
Android package
phone open/close event names
default goal
default stop condition
launch task
nudge message
recommended next action
```

Action handling, recovery lifecycle classification, and recovery nudges should use this registry rather than duplicating target metadata.

### `proposal_gate.py`

Pure deterministic validation gate for future AI/LLM proposals.

Important rule:

```text
LLM/agent may propose.
proposal_gate validates.
action-bridge executes only validated/user-triggered actions.
```

The gate rejects unknown targets, direct execution fields, unsupported actions, and unsafe write conditions.

### `agent_context.py`

Read-only context pack for deterministic and future LLM proposal producers.

It gathers:

```text
session state
Anki state
desktop state
recovery state
current nudge/question
interaction state
recent action/recovery/phone events
derived safety facts
```

It emits `agent_context.v1`.

The module must remain non-executing:

```text
no LLM calls
no action files
no phone nudges
no direct execution
optional writes only to state/agent/context.json and status.md
```

## Safety architecture

The intended agentic loop is:

```text
facts/context
  -> proposal producer
       deterministic trigger now
       LLM/agent later
  -> proposal_gate.py
  -> normalized safe proposal
  -> phone outbox
  -> user action
  -> action-bridge
  -> recovery-manager evidence classification
```

The LLM should never bypass the deterministic gate or write action files directly.

## Smoke tests

Run the current AI safety smoke suite:

```zsh
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/agent_context_smoke.py
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/proposal_gate_smoke.py
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/action_bridge_smoke.py
nix run nixpkgs#python3 -- modules/programs/ai/tests/recovery_smoke.py
```

## Adaptive agent contracts

The shared package is the contract layer for the future adaptive system.

The long-term goal is not to give an LLM direct tool access. The goal is to let deterministic and LLM proposal producers share the same input and validation path.

Current and future contract shape:

```text
agent_context.py
  -> proposal producer
       deterministic recovery-trigger now
       shadow-mode LLM later
       specialist agents later
  -> proposal_gate.py or another deterministic gate
  -> normalized safe proposal
  -> user-visible artifact or phone nudge
  -> user action / bridge execution
  -> evidence classification
  -> auditable learning
```

### Context contract

`agent_context.py` should remain read-only and non-executing.

Allowed:

```text
read vault state
read recent event tails
derive facts
write state/agent/context.json
write state/agent/status.md
```

Not allowed:

```text
write action files
write phone nudges
launch apps
call an LLM as a side effect
mutate recovery/session/task state
```

### Proposal contract

Proposal producers may produce structured JSON such as:

```text
agent_recovery_proposal.v1
daily_plan_proposal.v1
schedule_change_proposal.v1
environment_change_proposal.v1
feature_proposal.v1
policy_change_proposal.v1
```

A proposal is not an action. It is an argument for a possible action.

### Gate contract

Gates must remain deterministic and side-effect-free where possible.

They should:

```text
validate schema
reject direct execution fields
reject unknown capabilities or targets
enforce active-state blockers
enforce cooldowns and quiet hours
enforce risk limits
regenerate executable fields from trusted registries
return normalized proposals
return explicit rejection reasons
```

They should not call an LLM.

### Execution contract

The LLM must not choose executable details such as:

```text
android_package
launch_task
command
path
action_file
raw action payload
```

Executable details must come from trusted deterministic registries.

### Learning contract

Self-improvement should be evidence-based and auditable.

The system may later learn by recording:

```text
proposal
validation result
user response
bridge action
observed evidence
outcome classification
hypothesis
suggested policy or feature change
```

The system must not silently rewrite policies, enable services, add actions, or change autonomy levels.

### `recovery_proposals.py`

Pure recovery proposal construction for deterministic and future LLM/agent producers.

Responsibilities:

```text
consume agent_context.py derived facts
produce agent_recovery_proposal.v1 candidate proposals
produce explainable reason and blocker codes
avoid all vault writes, phone writes, action files, app launches, and LLM calls
```

This keeps `recovery-trigger` as orchestration glue instead of the owner of proposal logic.

### Recovery proposal smoke test

```zsh
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/recovery_proposals_smoke.py
```


### `interventions.py`

Pure helpers for append-only intervention audit events.

Initial recovery-trigger events:

```text
intervention_proposed
intervention_gated
intervention_nudge_written
```

These records support later outcome analysis without giving the LLM or trigger new execution authority.

### Intervention smoke test

```zsh
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/interventions_smoke.py
```


## Vocabulary for scaling beyond Anki

Recovery is the current narrow loop for small bounded re-entry actions.

Intervention is the broader audit/logging concept: a user-facing attempt to improve state.

Capability is the future generalization of recovery targets. A capability should declare trusted metadata such as risk level, allowed proposal schemas, allowed actions, cooldowns, evidence signals, success criteria, and approval requirements.

This means sport, math, books, and projects should not be added as arbitrary LLM tools. They should become registered capabilities with deterministic gates and outcome classifiers.

### `intervention_outcomes.py`

Pure intervention outcome summarization.

It groups existing append-only evidence by `intervention_id`:

```text
events/interventions
events/actions
events/recovery
```

It classifies conservative outcomes such as:

```text
not_shown
shown_no_response
acknowledged
snoozed
started
possible_success
possible_abort
expired
unknown
```

This is a learning/readout layer only. It must not write files, execute actions, call LLMs, or change policies.

### Intervention outcome smoke test

```zsh
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/intervention_outcomes_smoke.py
```

