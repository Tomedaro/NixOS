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

