# LLM Planner Design Notes

The planner is useful, but it is not the foundation of the system.

The deterministic layer must continue to work when Ollama fails, times out, returns invalid JSON, or produces low-quality advice.

---

## Current planner role

The planner reads curated local context and writes:

```text
AI/context/today.json
AI/context/today.md
AI/state/llm/planner-status.json
AI/state/llm/planner-status.md
AI/state/llm/last-output.json
AI/state/llm/last-output.md
AI/state/llm/last-error.md
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
AI/outbox/to-phone/current-nudge.md
AI/outbox/to-phone/current-question.md
AI/reports/help-now/
AI/reports/daily/
AI/proposed-tasks/
```

Current modes:

```text
help-now
block-plan
daily-review
```

---

## Deterministic fallback

`help-now` must always have a deterministic fallback.

If the LLM fails, the system should still write a concrete small next action.

Examples:

```text
Overwhelmed mode: 5 Anki cards or 5 minutes. Stop after that.
Tired mode: 3 easy Anki cards or 3 minutes.
Unclear mode: define the next visible step, then 5 minutes.
```

Fallback output must be:

```text
small
specific
bounded
non-moralizing
safe if repeated
```

---

## Session context rule

Planner context must distinguish active session state from historical session state.

Use:

```text
session.has_active_session = true / false
session.current = active session only
session.last = inactive/completed previous session
```

Completed sessions are useful history, but they must not be treated as the current active plan.

This matters because fallback behavior should respect active intent only when a session is truly active.

Bad behavior:

```text
completed smoke-test session
→ fallback still says to work on smoke-test
```

Correct behavior:

```text
no active session
+ Anki backlog exists
→ fallback may suggest a tiny Anki recovery step
```

---

## Phone output rule

The planner writes structured phone outbox JSON.

Canonical files:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

Markdown mirrors are for human inspection.

The phone outbox should contain action metadata that Tasker/WebView can render.

Normal nudge actions:

```json
{
  "action": "ack_nudge",
  "label": "Done"
}
```

```json
{
  "action": "snooze_nudge",
  "label": "Not now",
  "snooze_minutes": 15
}
```

Recovery nudge action:

```json
{
  "action": "start_recovery_target",
  "label": "Start Anki",
  "target_id": "anki",
  "target_name": "Anki",
  "goal_text": "5 cards or 5 minutes",
  "stop_condition": "Stop after 5 cards or 5 minutes",
  "android_package": "com.ichi2.anki",
  "launch_task": "AI PI Launch AnkiDroid"
}
```

---

## What the planner should not own

The planner should not own:

```text
question lifecycle after user response
nudge ack/snooze lifecycle
recovery session lifecycle
Tasker UI state
TaskNotes mutation authority
proof verification
passive phone telemetry normalization
```

Those belong to deterministic services, especially `action-bridge`, `phone-bridge`, and future lifecycle daemons.

---

## Recovery target relationship

The planner may propose or phrase recovery nudges, but it should not be the only authority deciding whether a recovery nudge exists.

Automatic recovery nudges should be deterministic first.

A future deterministic trigger may be:

```text
no active session
+ Anki due > 0
+ no active nudge
+ no active question
+ no active recovery session
+ no recent snooze
+ desktop verdict is no_plan / off_task / idle
→ write recovery nudge
```

The LLM can later improve wording or choose among already-safe deterministic options.

---

## Good planner behavior

Prefer:

```text
5 cards or 5 minutes
3-minute reset
write one next-step sentence
open the target tool
stop after the defined limit
```

Avoid:

```text
catch up on everything
be more disciplined
finish the backlog
try harder
vague encouragement
large multi-step obligations
```

---

## Safety and inspectability

Every planner run should leave inspectable state:

```text
context used
status
warnings
last output
last error if any
phone outbox files
report file
```

Planner failure should preserve previous useful outputs unless a deterministic fallback is available and appropriate.

---

## Current pending work

Before automatic recovery nudges, implement:

```text
recovery lifecycle end states
rapid-exit detection
possible_success / possible_abort / expired classification
old failed action cleanup / retention
multi-target recovery policy
```
