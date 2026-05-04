# Phone Interaction Protocol

This document defines the outbound phone interaction protocol for the local AI productivity system.

The protocol exists to make phone interactions structured, inspectable, and safe:

```text
planner / coach / recovery logic
→ structured phone outbox JSON
→ Tasker/WebView phone UI
→ one-tap user response
→ canonical action file
→ action-bridge updates state
```

The phone is a UI adapter. It should not own planning, policy, lifecycle, or learning logic.

---

## Ownership rules

Desktop/local services write:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
AI/outbox/to-phone/*.md
```

Phone/Tasker writes intentional user actions:

```text
AI/inbox/actions/*.json
```

Phone/Tasker writes passive telemetry:

```text
AI/inbox/from-phone/events/*.json
```

Action bridge owns response lifecycle:

```text
AI/state/action-bridge/status.json
AI/state/llm/last-answer.json
AI/state/recovery/current.json
AI/events/actions/YYYY-MM-DD.jsonl
AI/events/recovery/YYYY-MM-DD.jsonl
```

---

## Intentional actions vs passive events

Intentional user actions go to:

```text
AI/inbox/actions/*.json
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

Passive phone telemetry goes to:

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

If an intentional action appears as a passive phone event, the file was written to the wrong inbox.

---

## Nudge schema

Canonical file:

```text
AI/outbox/to-phone/current-nudge.json
```

Example recovery nudge:

```json
{
  "schema_version": "phone_interaction.v1",
  "kind": "nudge",
  "status": "active",
  "nudge_id": "n-2026-05-04-1234567890",
  "created_at": "2026-05-04T14:21:29+02:00",
  "updated_at": "2026-05-04T14:21:29+02:00",
  "source": "llm-planner",
  "planner_mode": "recovery",
  "urgency": "normal",
  "message": "Anki recovery: 5 cards or 5 minutes.",
  "recommended_next_action": "Tap Start Anki. Stop after 5 cards or 5 minutes.",
  "actions": [
    {
      "action": "start_recovery_target",
      "label": "Start Anki",
      "target_id": "anki",
      "target_name": "Anki",
      "goal_text": "5 cards or 5 minutes",
      "stop_condition": "Stop after 5 cards or 5 minutes",
      "android_package": "com.ichi2.anki",
      "launch_task": "AI PI Launch AnkiDroid"
    },
    {
      "action": "snooze_nudge",
      "label": "Not now",
      "snooze_minutes": 15
    }
  ]
}
```

Nudge statuses:

```text
active
inactive
```

Known inactive `last_status` values:

```text
acknowledged
snoozed
recovery_started
```

---

## Question schema

Canonical file:

```text
AI/outbox/to-phone/current-question.json
```

Example:

```json
{
  "schema_version": "phone_interaction.v1",
  "kind": "question",
  "status": "active",
  "question_id": "q-2026-05-04-1234567890",
  "created_at": "2026-05-04T09:40:00+02:00",
  "updated_at": "2026-05-04T09:40:00+02:00",
  "source": "llm-planner",
  "planner_mode": "help-now",
  "question": "What is the main blocker right now?",
  "reason": "The system needs one response to choose a smaller next action.",
  "answer_options": [
    {
      "id": "overwhelmed",
      "label": "Overwhelmed"
    },
    {
      "id": "tired",
      "label": "Tired"
    },
    {
      "id": "unclear",
      "label": "Unclear"
    }
  ],
  "free_text_allowed": true,
  "response_action": "answer_question",
  "dismiss_action": "dismiss_question"
}
```

---

## Interaction state

Canonical file:

```text
AI/outbox/to-phone/interaction-state.json
```

This file is a compact snapshot for phone UI surfaces.

Example:

```json
{
  "schema_version": "phone_interaction_state.v1",
  "updated_at": "2026-05-04T14:40:50+02:00",
  "source": "action-bridge",
  "planner_mode": "recovery",
  "active_nudge": null,
  "active_question": null,
  "last_nudge_ack": {
    "action_id": "action-ack_nudge-example",
    "nudge_id": "n-example",
    "processed_at": "2026-05-04T10:05:38+02:00"
  },
  "last_nudge_snooze": {
    "action_id": "action-snooze_nudge-example",
    "nudge_id": "n-example",
    "reason": "not_now",
    "snooze_minutes": 15,
    "snoozed_until": "2026-05-04T14:04:54+02:00",
    "processed_at": "2026-05-04T13:49:54+02:00"
  }
}
```

---

## Canonical response actions

### `ack_nudge`

Acknowledges and clears the current nudge.

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "ack_nudge",
  "nudge_id": "n-example",
  "timestamp_epoch": "1777890000"
}
```

### `snooze_nudge`

Clears the current nudge temporarily and records a snooze.

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "snooze_nudge",
  "nudge_id": "n-example",
  "reason": "not_now",
  "snooze_minutes": 15,
  "timestamp_epoch": "1777890000"
}
```

### `answer_question`

Answers the current question and may trigger help-now replanning.

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "answer_question",
  "question_id": "q-example",
  "answer": "overwhelmed",
  "answer_label": "Overwhelmed",
  "free_text": "",
  "timestamp_epoch": "1777890000"
}
```

### `dismiss_question`

Dismisses the current question without triggering replanning.

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "dismiss_question",
  "question_id": "q-example",
  "reason": "not_now",
  "timestamp_epoch": "1777890000"
}
```

### `start_recovery_target`

Starts a generic recovery target such as Anki.

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "start_recovery_target",
  "nudge_id": "n-example",
  "target_id": "anki",
  "target_name": "Anki",
  "goal_text": "5 cards or 5 minutes",
  "stop_condition": "Stop after 5 cards or 5 minutes",
  "android_package": "com.ichi2.anki",
  "timestamp_epoch": "1777890000"
}
```

When this action includes a `nudge_id`, action-bridge should consume the nudge:

```text
current-nudge.status = inactive
current-nudge.last_status = recovery_started
interaction-state.active_nudge = null
```

---

## Current Tasker role

Tasker should:

```text
read outbox JSON
render a phone UI
write canonical action JSON into AI/inbox/actions/
optionally launch Android apps through small Tasker tasks
```

Tasker should not:

```text
decide when to nudge
own question lifecycle
own recovery lifecycle
mutate TaskNotes
invent planner policy
```

---

## Current phone UI

Current primary phone UI file:

```text
AI/state/phone/ai-pi-gruvbox-card-v1.html
```

Current known launcher task:

```text
AI PI Launch AnkiDroid
```

This task should use:

```text
App → Load App → AnkiDroid
```

The WebView card calls the task when the user taps a recovery start button.

---

## Current implementation status

Implemented:

```text
current-nudge.json
current-question.json
interaction-state.json
ack_nudge
snooze_nudge
answer_question
dismiss_question
start_recovery_target
Tasker/WebView button writes actions
Tasker/WebView can launch AnkiDroid through a helper task
```

Still pending:

```text
recovery lifecycle end states
automatic recovery nudges
rapid-exit detection
success/abort classification
multi-target recovery policies
```

