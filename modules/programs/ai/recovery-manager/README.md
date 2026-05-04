# recovery-manager

Deterministic recovery lifecycle classifier for the local AI productivity system.

It reads active recovery state and passive phone telemetry, then classifies weak lifecycle evidence.

It does not create nudges, launch apps, call the LLM, mutate TaskNotes, or decide punishment.

---

## Inputs

Current recovery state:

```text
AI/state/recovery/current.json
```

Passive phone events:

```text
AI/events/phone/YYYY-MM-DD.jsonl
```

For Anki v1, relevant events are:

```text
opened_ankidroid
closed_ankidroid
```

---

## Outputs

```text
AI/state/recovery/current.json
AI/state/recovery/status.json
AI/state/recovery/status.md
AI/events/recovery/YYYY-MM-DD.jsonl
```

---

## Lifecycle states

Current v1 states:

```text
active
observing
possible_success
possible_abort
expired
```

These are evidence labels, not moral judgments.

`observing` means the target was seen, but the observation window is still open.

`possible_success` means the target was observed long enough.

`possible_abort` means the observation window ended and target dwell was still too short.

`expired` means no target open was observed within the recovery observation window.

---

## Conservative design

The manager uses an observation window so unrelated later app opens are ignored.

For v1:

```text
recovery start
-> observe until start + 15 minutes
-> ignore later target app events
```

It uses dwell time instead of first-close alone, because Android/Tasker app context events can be noisy.

Rapid exit is stored as evidence:

```text
rapid_exit_detected = true
```

but it does not immediately create terminal `possible_abort`.

---

## Current architecture role

This module is intentionally separate from `phone-bridge`.

```text
phone-bridge:
  records passive facts

recovery-manager:
  interprets facts for current recovery lifecycle
```

Automatic nudges should come later, after lifecycle classification is trusted.
