# coach-daemon

Immediate desktop context observer for the local AI productivity system.

Service:

```text
productivity-coach.service
```

---

## Purpose

`coach-daemon` observes current desktop context and classifies whether the user appears aligned with the active session policy.

It is a deterministic sensor/classifier layer, not a planner.

It should answer:

```text
what app/window appears active
whether the user is idle
whether there is an active session
whether current activity looks on-task, off-task, idle, unknown, or no-plan
```

---

## Inputs

Primary inputs:

```text
ActivityWatch window / AFK state
AI/state/session/current.json
AI/state/session/current-policy.json
AI/control/current-task.md
AI/control/current-mode.md
AI/control/current-block.md
```

The active-session rule matters:

```text
status == "active"
→ use session policy

status != "active"
→ do not treat last session as current intent
```

---

## Outputs

`coach-daemon` writes:

```text
AI/state/desktop/now.json
AI/state/desktop/now.md
AI/events/desktop/YYYY-MM-DD.jsonl
AI/logs/desktop/YYYY-MM-DD.md
```

These files are inspectable local state.

Example verdicts:

```text
on_task
off_task
idle
unknown
no_plan
```

---

## Current role in architecture

`coach-daemon` is currently responsible for classification only.

It may later feed deterministic recovery triggers, but it should not directly own phone interaction lifecycle.

Current clean architecture:

```text
coach-daemon
→ writes desktop now/verdict

future recovery trigger logic
→ reads desktop now + Anki state + phone state + interaction state
→ writes current-nudge.json

Tasker/WebView
→ shows nudge
→ writes action

action-bridge
→ owns action lifecycle
```

---

## What coach should not own

`coach-daemon` should not:

```text
own nudge ack/snooze lifecycle
own question lifecycle
own recovery lifecycle
write action files on behalf of the user
mutate TaskNotes
require the LLM to classify basic state
treat completed sessions as active intent
```

---

## Interaction with recovery targets

The recovery target loop should use coach output conservatively.

A future deterministic trigger may use:

```text
desktop verdict = no_plan / off_task / idle
+ no active session
+ Anki due > 0
+ no active nudge
+ no active question
+ no active recovery
+ no recent snooze
→ write recovery nudge
```

But `coach-daemon` itself should remain a low-level observer.

---

## Notification behavior

Desktop notifications should be conservative.

Good behavior:

```text
active session + clearly off-task + cooldown passed
→ small reminder
```

Bad behavior:

```text
user is already on task
→ repeated interruptions
```

```text
no active session
→ shame/nag
```

```text
user just acted on a recovery nudge
→ repeat same nudge immediately
```

Strictness is a policy variable, not an ideology.

---

## Design principles

`coach-daemon` should be:

```text
deterministic first
quiet when evidence is weak
cooldown-aware
session-aware
inspectable
safe if ActivityWatch is stale
```

It should treat off-task behavior as a context signal, not as a moral failure.

---

## Current pending work

Useful future improvements:

```text
better stale ActivityWatch handling
clearer no_plan behavior
richer desktop evidence summaries
integration with recovery lifecycle state
deterministic recovery-trigger daemon or mode
browser URL/domain classification through browser-bridge
```
