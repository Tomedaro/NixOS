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

### agent context pack

The read-only agent context pack is the stable input contract for deterministic and future LLM proposal producers.

Implemented module:

```text
modules/programs/ai/python/ai_system/agent_context.py
```

Smoke tests:

```text
modules/programs/ai/tests/agent_context_smoke.py
```

The context gathers session, Anki, desktop, recovery, current phone interaction state, and recent event tails into `agent_context.v1`.

Execution boundary:

```text
agent_context.py reads facts
proposal producer suggests
proposal_gate.py validates
phone outbox/action-bridge execute only after deterministic validation and user action
```

This prepares the system for LLM-generated proposals without giving the LLM direct write or execution authority.

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

## Destination architecture: adaptive productivity on deterministic rails

The desired destination is an agentic, smart, adaptive productivity and recovery system that learns the user's patterns, supports short-term and long-term goals, proposes better environments and schedules, and can suggest new capabilities when evidence indicates they may help.

The safety model is not:

```text
LLM sees tools -> LLM directly executes
```

The safety model is:

```text
adaptive intelligence over deterministic rails
```

The long-term loop should remain:

```text
observations + state + goals + policies
  -> agent_context.py
  -> proposal producer
       deterministic producers now
       shadow-mode LLM producers later
       specialist agents later
  -> deterministic gates
  -> user-visible proposal / phone nudge / draft
  -> user approval or validated bridge action
  -> evidence collection
  -> outcome classification
  -> auditable learning and policy proposals
```

Core authority rule:

```text
LLM / agent may observe and propose.
Deterministic code validates.
User action / action-bridge executes.
Recovery-manager and future outcome managers classify evidence after the fact.
```

### What the LLM may eventually do

The LLM may become useful for:

```text
recognizing user patterns
summarizing friction
selecting among known safe intervention types
adapting tone and timing
proposing daily or weekly plans
proposing environment changes
estimating confidence
generating feature proposals
explaining tradeoffs
forming auditable hypotheses from outcomes
```

The LLM should produce structured proposals, not side effects.

Examples:

```text
agent_recovery_proposal.v1
daily_plan_proposal.v1
schedule_change_proposal.v1
environment_change_proposal.v1
feature_proposal.v1
policy_change_proposal.v1
```

### What the LLM must not do

The LLM must not directly:

```text
write action files
write phone nudge files
launch apps
choose android_package
choose launch_task
run shell commands
edit Nix modules
enable timers or services
mutate TaskNotes
mutate calendar state
change recovery lifecycle state
change policy or cooldowns silently
bypass proposal gates
treat browser, email, notification, note, or webpage text as trusted instructions
```

Executable details must be regenerated from trusted registries such as `recovery_targets.py` and future capability registries.

### Self-improvement contract

The system may become self-improving only through auditable evidence and explicit proposal records.

Allowed self-improvement shape:

```text
observe recurring friction
  -> generate hypothesis
  -> link supporting evidence
  -> propose experiment / policy / feature
  -> deterministic validation
  -> user review
  -> implementation and tests
```

Not allowed:

```text
observe behavior
  -> silently change policy
  -> silently enable autonomy
  -> silently add new actions
  -> silently rewrite execution rules
```

A safe future feature proposal should look like:

```json
{
  "schema_version": "feature_proposal.v1",
  "title": "Add morning planning nudge",
  "problem": "User often starts work without an explicit first block.",
  "evidence": [
    "Several mornings had no active session before the first work block.",
    "Planning nudges were accepted more often after idle terminal periods."
  ],
  "proposed_capability": "morning_plan_prompt",
  "risk_level": "low",
  "required_tests": [
    "quiet hours are respected",
    "active sessions block the nudge",
    "daily maximum is enforced",
    "proposal contains no executable fields"
  ],
  "execution_authority": "none"
}
```

### Learning layer required before autonomy

Before adding automatic LLM-driven nudges or actions, the system should record intervention outcomes.

Every intervention should become inspectable as:

```text
proposal
  -> validation result
  -> user response
  -> bridge action
  -> evidence
  -> outcome classification
  -> later hypothesis or policy proposal
```

Future files may include:

```text
AI/events/interventions/YYYY-MM-DD.jsonl
AI/state/interventions/current.json
AI/state/interventions/stats.json
AI/state/agent/last-proposal.json
AI/state/agent/last-validation.json
AI/state/agent/hypotheses.json
```

The learning layer should answer:

```text
What was proposed?
Why was it proposed?
Was it accepted by the gate?
Did the user act?
What happened after the action?
Was the timing useful?
Was the intervention annoying or helpful?
Should this strategy be repeated, modified, or retired?
```

### Autonomy ladder

Capabilities should move through explicit autonomy levels:

```text
Level 0: observe only
Level 1: write private status or analysis
Level 2: create proposal for user review
Level 3: create draft artifact
Level 4: create approved-shape phone nudge
Level 5: execute only after explicit user action
Level 6: automatic low-risk execution after prior approval and tests
Level 7: high-risk actions require explicit confirmation every time
```

Current recovery work should remain around Levels 0-5.

Do not jump directly from shadow-mode LLM proposals to automatic execution.

### Capability registry direction

`recovery_targets.py` is the first narrow trusted registry. Long-term, it should evolve into or be complemented by a capability registry.

Each capability should declare:

```text
capability id
kind
risk level
allowed proposal schemas
trusted executable fields
required user approval level
cooldowns
daily and weekly limits
quiet-hour behavior
evidence signals
success criteria
rollback behavior
required smoke tests
```

The LLM may propose a capability id. Deterministic code hydrates executable details from the trusted registry.

### Near-term sequencing

The safe next sequence is:

```text
1. Keep recovery-trigger disabled unless explicitly enabled.
2. Keep recovery-manager live and conservative.
3. Wire deterministic recovery-trigger to consume agent_context.py facts.
4. Add outcome/intervention logging before adding LLM autonomy.
5. Add shadow-mode LLM proposal producer that writes only state/agent files.
6. Compare deterministic and LLM proposals without writing nudges.
7. Add goal graph and schedule/planning proposal schemas.
8. Add feature proposal schema for system-improvement suggestions.
9. Only promote capabilities after tests, gates, and user approval exist.
```

This preserves the main design invariant:

```text
adaptive proposals may become smarter over time;
execution authority remains explicit, deterministic, and auditable.
```
