# Recovery Target Loop

This document describes the generic recovery-loop architecture.

Anki is the first concrete target, but the architecture should not become Anki-specific.

---

## Product purpose

A recovery loop exists to reduce the cost of restarting after friction.

It should not nag the user after they already did the right transition.

Bad pattern:

```text
user opens Anki
→ system says "do Anki"
```

Better pattern:

```text
user appears stuck / drifting / no-plan / off-task
+ recovery target is available
→ system offers one tiny executable action
→ one tap opens the right tool
→ system observes follow-through
```

---

## Core loop

```text
detect stuck state
→ choose recovery target
→ offer tiny start
→ user starts / snoozes / dismisses / answers friction
→ action-bridge records response
→ recovery state updates
→ later logic observes follow-through
```

---

## Recovery target abstraction

A recovery target is a reusable structure:

```json
{
  "target_id": "anki",
  "display_name": "Anki",
  "kind": "app",
  "entry_action": {
    "type": "launch_android_package",
    "android_package": "com.ichi2.anki"
  },
  "micro_actions": [
    "1 card",
    "3 cards",
    "5 cards",
    "5 minutes"
  ],
  "success_evidence": [
    "opened target app",
    "stayed long enough",
    "objective progress increased"
  ],
  "friction_answers": [
    "overwhelmed",
    "tired",
    "unclear",
    "not_now"
  ]
}
```

Anki is only the first target.

Later targets can include:

```text
coding
writing
reading
admin
language practice
exercise
sleep routine
TaskNotes cleanup
```

---

## Current Anki v1 behavior

Current start path:

```text
recovery nudge appears
→ phone user taps Start Anki
→ Tasker writes start_recovery_target
→ Tasker opens AnkiDroid
→ action-bridge writes AI/state/recovery/current.json
→ action-bridge consumes the active nudge
```

Current recovery state:

```text
AI/state/recovery/current.json
AI/state/recovery/status.md
AI/events/recovery/YYYY-MM-DD.jsonl
```

Example state:

```json
{
  "schema_version": "recovery_session.v1",
  "recovery_id": "recovery-anki-1777898450",
  "status": "active",
  "source": "tasker",
  "device": "phone",
  "target": {
    "target_id": "anki",
    "name": "Anki",
    "kind": "app",
    "android_package": "com.ichi2.anki"
  },
  "goal": {
    "text": "5 cards or 5 minutes",
    "stop_condition": "Stop after 5 cards or 5 minutes"
  },
  "launch": {
    "requested": true,
    "android_package": "com.ichi2.anki",
    "handled_by": "tasker"
  }
}
```

---

## Why not nudge inside Anki by default?

Once the user has opened the target app, the system should usually stay quiet.

Inside-target prompts are risky because they can interrupt the exact behavior the system wants to support.

Default rule:

```text
Before target app:
  help start

Inside target app:
  stay quiet

After rapid exit or failure:
  ask what made it hard

After plausible success:
  record evidence and leave user alone
```

---

## Recovery lifecycle v1

Current implemented lifecycle:

```text
start_recovery_target
→ active
```

Next required lifecycle:

```text
active
→ launched
→ possible_success / possible_abort / expired
```

Proposed deterministic rules for Anki:

```text
opened_ankidroid within 2 minutes of recovery start
→ launched

closed_ankidroid within 90 seconds of launch
→ possible_abort

closed_ankidroid after 5 minutes
→ possible_success

no relevant phone event after 15 minutes
→ expired
```

These states should be logged, not treated as moral judgments.

---

## Automatic recovery nudge criteria

Do not implement automatic nudges until recovery lifecycle is stable.

When implemented, a conservative first trigger could be:

```text
no active session
+ Anki due > 0
+ desktop verdict is no_plan / off_task / idle
+ no active nudge
+ no active question
+ no recent snooze
+ no active recovery session
→ write recovery nudge
```

The nudge should offer:

```text
Start Anki
Not now
Too much / question option later
```

---

## What v1 should avoid

Avoid these until the basic loop is reliable:

```text
strict enforcement
TaskNotes mutation
proof requirements
screenshot analysis
multi-target ranking
complex learning model
in-app overlays
```

---

## Design principle

The recovery loop is not a punishment system.

It treats avoidance, rapid exit, and snoozing as context signals:

```text
too big
too vague
too much energy
wrong moment
unclear next step
```

The correct response is to reduce friction, not increase pressure.
