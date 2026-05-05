# AI Architecture Review

This document records the current architecture after introducing the unified action bridge, phone interaction protocol, recovery lifecycle manager, and deterministic recovery trigger.

The goal is an agentic adaptive system, not a static rule engine. The deterministic components below are the substrate that lets an LLM agent reason and act safely.

---

## Current architecture

```text
phone / Tasker / WebView
  UI adapter only
  reads phone outbox JSON
  writes intentional actions
  writes passive telemetry
  launches Android apps only after user action

phone-bridge
  passive phone telemetry processor
  from-phone/events -> events/phone
  rejects action-shaped files in passive telemetry

action-bridge
  canonical intentional action router
  inbox/actions -> state/events
  owns action lifecycle, nudge ack/snooze, question responses, recovery start

recovery-manager
  recovery lifecycle classifier
  reads active recovery and passive evidence
  writes recovery classification
  does not create nudges or launch apps

recovery-trigger
  deterministic v0 nudge proposal source
  currently disabled
  writes structured decision record
  may write phone recovery nudge only when gates pass

llm-planner / future agent
  strategic reasoning, prioritization, wording, target choice, adaptation
  should emit structured proposals
  should not directly mutate arbitrary state

coach / desktop sensors
  current context and alignment detection
```

---

## Core principle

```text
facts are separate from decisions
decisions are separate from execution
execution is separate from UI
LLM reasoning is gated by deterministic state machines
```

This preserves debuggability and keeps the future agent from becoming noisy or unsafe.

---

## Component responsibilities

### phone-bridge

Owns passive phone facts.

Reads:

```text
AI/inbox/from-phone/events/*.json
```

Writes:

```text
AI/events/phone/YYYY-MM-DD.jsonl
AI/logs/phone/YYYY-MM-DD.md
AI/state/phone/latest.json
AI/state/phone/latest.md
```

Must not process intentional actions.

Examples of passive events:

```text
opened_ankidroid
closed_ankidroid
opened_obsidian_app
closed_obsidian_app
phone_unlock
```

### action-bridge

Owns intentional commands.

Reads:

```text
AI/inbox/actions/*.json
```

Writes:

```text
AI/events/actions/YYYY-MM-DD.jsonl
AI/state/action-bridge/status.json
AI/state/llm/last-answer.json
AI/state/recovery/current.json
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

Canonical actions:

```text
start_session
end_session
check_in
answer_question
dismiss_question
ack_nudge
snooze_nudge
start_recovery_target
promote_task_proposal
submit_proof
```

### recovery-manager

Owns recovery lifecycle interpretation.

Reads:

```text
AI/state/recovery/current.json
AI/events/phone/YYYY-MM-DD.jsonl
```

Writes:

```text
AI/state/recovery/current.json
AI/state/recovery/status.json
AI/state/recovery/status.md
AI/events/recovery/YYYY-MM-DD.jsonl
```

Current states:

```text
active
observing
possible_success
possible_abort
expired
```

Safety behavior:

```text
possible_success is terminal
possible_abort waits until observation window ends
terminal_status_unchanged does not rewrite files
closing app after possible_success does not downgrade
```

### recovery-trigger

Owns deterministic v0 recovery nudge proposal.

Currently disabled.

Reads:

```text
AI/state/session/current.json
AI/state/anki/status.json
AI/state/desktop/now.json
AI/state/recovery/current.json
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
AI/events/actions/YYYY-MM-DD.jsonl
```

Writes:

```text
AI/state/recovery-trigger/last-decision.json
AI/state/recovery-trigger/status.md
```

When enabled and all gates pass, may also write:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

v0 gate:

```text
no active session
+ no active nudge
+ no active question
+ no active recovery
+ no recent terminal recovery
+ no recent snooze
+ Anki due > 0
+ desktop verdict is idle/no_plan/off_task/distracted/unknown
-> write Start Anki recovery nudge
```

---

## LLM / agent role

The LLM should become the adaptive intelligence layer, but not the raw executor.

Future agent loop:

```text
state + events + policies
-> context pack
-> LLM agent decision
-> structured proposal
-> deterministic validation gate
-> phone interaction / action bridge
-> evidence collection
-> reflection and adaptation
```

The LLM should do:

```text
target selection
timing judgment
tone adaptation
friction hypothesis
strategy selection
confidence estimation
cooldown recommendation
cross-tool planning
```

The LLM should not directly do:

```text
write arbitrary action files
launch apps
mutate TaskNotes without explicit authority
bypass cooldowns
overwrite recovery lifecycle
silently change policy
```

Preferred future proposal shape:

```json
{
  "schema_version": "agent_recovery_proposal.v1",
  "decision": "write_nudge",
  "target_id": "anki",
  "target_name": "Anki",
  "confidence": 0.72,
  "reason_codes": ["anki_due", "idle", "no_active_session"],
  "blocked_reasons": [],
  "cooldown_seconds": 1800,
  "message": "Anki recovery: start a tiny 5-minute block.",
  "recommended_next_action": "Tap Start Anki.",
  "allowed_actions": ["start_recovery_target", "snooze_nudge"],
  "agent_notes": "User recently succeeded with a 5-minute Anki recovery."
}
```

The deterministic gate should validate this before anything reaches the phone.

---

### recovery-trigger proposal gate wiring

`recovery-trigger` now routes its deterministic recovery proposal through `proposal_gate.py` before writing any phone nudge.

This means deterministic and future LLM/agent proposals share the same validation boundary:

```text
facts/context
  -> proposal producer
       deterministic recovery-trigger now
       LLM/agent later
  -> proposal_gate.py
  -> normalized safe phone_nudge
  -> phone outbox
  -> action-bridge after user action
```

The trigger still remains disabled by default. This change only unifies the safety path.

### deterministic proposal validation gate

Future LLM/agent recovery proposals should pass through a pure validation gate before any phone nudge or action file is written.

Implemented module:

```text
modules/programs/ai/python/ai_system/proposal_gate.py
```

Smoke tests:

```text
modules/programs/ai/tests/proposal_gate_smoke.py
```

The gate currently validates recovery proposals by:

```text
rejecting unknown recovery targets
rejecting direct execution fields such as action, command, android_package, launch_task, path
rejecting unsupported allowed actions
blocking write_nudge when facts show active session/nudge/question/recovery, recent snooze, recent terminal recovery, or no Anki due
regenerating executable phone actions from the shared recovery target registry
```

This keeps the future LLM adaptive while preserving deterministic execution safety.

## Known duplication

These concepts are currently duplicated and should be extracted later.

### Time and IO helpers

Duplicated functions:

```text
now
now_iso
today
atomic_write_text
atomic_write_json
read_json
append_jsonl
parse epoch
```

Target location:

```text
modules/programs/ai/python/ai_system/
```

### Recovery target registry

Anki target metadata appears in multiple places.

Current repeated values:

```text
target_id = anki
target_name = Anki
android_package = com.ichi2.anki
open event = opened_ankidroid
close event = closed_ankidroid
default goal = 5 minutes in AnkiDroid
launch task = AI PI Launch AnkiDroid
```

Future registry:

```json
{
  "anki": {
    "display_name": "Anki",
    "kind": "app",
    "android_package": "com.ichi2.anki",
    "phone_open_event": "opened_ankidroid",
    "phone_close_event": "closed_ankidroid",
    "default_goal": "5 minutes in AnkiDroid",
    "launch_task": "AI PI Launch AnkiDroid"
  }
}
```

Do not add many recovery targets before extracting this.

---

## Test priorities

Add temporary smoke tests before more behavior.

### recovery-manager tests

```text
fresh quick exit -> observing
old quick exit -> possible_abort
5 minute dwell -> possible_success
terminal status -> no duplicate event / no file churn
close after success -> terminal_status_unchanged
```

### recovery-trigger tests

```text
anki_due = 0 -> skip
anki_due > 0 and gates clear -> write_nudge
active_nudge -> skip
active_question -> skip
active_recovery -> skip
recent_snooze -> skip
recent_terminal_recovery -> skip
active_session -> skip
```

---

### action-bridge tests

Implemented smoke coverage:

```text
ack_nudge -> current nudge inactive, action event written, raw action processed
snooze_nudge -> current nudge inactive, interaction-state records snooze details
start_recovery_target -> recovery/current.json active, recovery event written, originating nudge consumed
answer_question -> last-answer.json written, current question inactive
dismiss_question -> current question inactive, dismiss event written
```

These tests protect the command execution boundary that future LLM/agent proposals will eventually feed through.

## Near-term plan

1. Keep `recovery-trigger` disabled.
2. Add smoke-test scripts for manager and trigger.
3. Refactor shared helpers only after tests exist.
4. Extract recovery target registry before adding more targets.
5. Design LLM agent proposal schema using `recovery_trigger_decision.v1` as the baseline.
6. Only later enable automatic recovery triggering.

---

## Non-goals right now

```text
automatic multi-target nudging
LLM direct execution
Tasker business logic
more popups
complex planner autonomy
TaskNotes mutation from recovery flow
```

The current priority is reliability, observability, and a clean boundary for future LLM intelligence.
