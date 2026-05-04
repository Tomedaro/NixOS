# phone-bridge

Passive phone telemetry bridge for the local AI productivity system.

`phone-bridge` processes factual phone events written by Tasker/Syncthing.

It does **not** own intentional user actions, phone UI lifecycle, nudges, questions, or recovery decisions.

---

## Input

Passive phone telemetry goes here:

```text
AI/inbox/from-phone/events/*.json
```

Examples:

```text
phone_unlock
opened_ankidroid
closed_ankidroid
opened_obsidian_app
closed_obsidian_app
```

Example event:

```json
{
  "schema_version": "event.v1",
  "source": "tasker",
  "device": "phone",
  "event": "opened_ankidroid",
  "message": "Opened AnkiDroid",
  "timestamp_epoch": "1777875676"
}
```

---

## Output

`phone-bridge` writes:

```text
AI/events/phone/YYYY-MM-DD.jsonl
AI/logs/phone/YYYY-MM-DD.md
AI/state/phone/latest.json
AI/state/phone/latest.md
```

These files are factual telemetry state.

They should be usable by:

```text
llm-planner
future recovery lifecycle daemon
future automatic nudge logic
debugging / inspection
```

---

## Important separation

Intentional actions do **not** belong in `phone-bridge`.

Intentional actions go to:

```text
AI/inbox/actions/*.json
```

Handled by:

```text
action-bridge
```

Examples:

```text
ack_nudge
snooze_nudge
answer_question
dismiss_question
start_recovery_target
check_in
start_session
end_session
```

Passive phone events go to:

```text
AI/inbox/from-phone/events/*.json
```

Handled by:

```text
phone-bridge
```

If `ack_nudge`, `answer_question`, or `start_recovery_target` appears as a phone telemetry event, Tasker wrote it to the wrong folder.

---

## Current Tasker role

Tasker currently has two separate jobs:

```text
1. Passive telemetry
   → write AI/inbox/from-phone/events/*.json

2. Phone interaction UI
   → read AI/outbox/to-phone/*.json
   → write AI/inbox/actions/*.json
```

`phone-bridge` only handles job 1.

The phone interaction UI is documented in:

```text
modules/programs/ai/PHONE_INTERACTION_PROTOCOL.md
```

---

## Recovery lifecycle relationship

`phone-bridge` does not decide recovery success or failure.

It only records events such as:

```text
opened_ankidroid
closed_ankidroid
```

A future deterministic lifecycle component can interpret those events:

```text
start_recovery_target
→ active

opened_ankidroid soon after start
→ launched

closed_ankidroid very quickly
→ possible_abort

closed_ankidroid after enough time
→ possible_success
```

This keeps telemetry collection separate from interpretation.

---

## Design principles

`phone-bridge` should be:

```text
boring
deterministic
append-only for events
inspectable
safe under repeated runs
strict about processed/failed queues
```

It should not:

```text
launch apps
create nudges
answer questions
mutate TaskNotes
trigger planner runs
decide user intent
```

---

## Current status

Implemented:

```text
passive Tasker event ingestion
processed/failed queue handling
daily phone JSONL events
daily phone Markdown log
latest phone state JSON/Markdown
strict separation from canonical action bridge
```

Pending / future:

```text
shared recovery lifecycle consumer
better passive event schemas
optional retention cleanup
more phone app events
battery / charging / focus-mode telemetry if useful
```
