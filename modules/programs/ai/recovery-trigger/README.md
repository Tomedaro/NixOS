# recovery-trigger

Deterministic v0 trigger for recovery nudges.

This component decides whether to offer a recovery nudge. It does not launch apps, classify recovery lifecycle, call the LLM, or mutate TaskNotes.

It is designed as a future LLM-agent integration point: the deterministic v0 writes the same kind of structured decision record that an agentic planner can later fill more intelligently.

---

## Role

```text
facts/state
-> decision record
-> optional phone nudge
```

`recovery-trigger` is separate from `recovery-manager`.

```text
recovery-trigger:
  decides whether to offer a recovery path

recovery-manager:
  classifies what happened after recovery starts
```

---

## Inputs

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

---

## Outputs

```text
AI/state/recovery-trigger/last-decision.json
AI/state/recovery-trigger/status.md
```

When all gates pass, it also writes:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

---

## v0 trigger rule

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

This is intentionally conservative.

---

## LLM direction

The deterministic v0 is not the final intelligence.

Future LLM agent role:

```text
choose target
adapt timing
adapt tone
infer friction
explain confidence
recommend cooldown
choose between Anki / writing / coding / admin recovery
```

But execution should still pass through deterministic safety gates.
