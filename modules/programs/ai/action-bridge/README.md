# action-bridge

Canonical command/action router for the local AI productivity system.

All intentional commands should be JSON files under:

```text
AI/inbox/actions/*.json
```

Passive telemetry remains handled by sensor bridges such as `phone-bridge`, ActivityWatch/coach, and Anki bridge.

---

## Responsibilities

`action-bridge` owns:

```text
canonical intentional action processing
action queue processed/failed movement
normalized action events
question response lifecycle
nudge acknowledgement/snooze lifecycle
recovery target start lifecycle
session start/end delegation
proof and proposal actions
```

It writes:

```text
AI/state/action-bridge/status.json
AI/state/action-bridge/status.md
AI/state/llm/last-answer.json
AI/state/recovery/current.json
AI/state/recovery/status.md
AI/events/actions/YYYY-MM-DD.jsonl
AI/events/recovery/YYYY-MM-DD.jsonl
AI/events/tasknotes/YYYY-MM-DD.jsonl
AI/events/proofs/YYYY-MM-DD.jsonl
```

---

## Supported actions

Current actions:

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

Aliases are accepted for some actions for backwards compatibility, but new integrations should use the canonical names above.

---

## Intentional actions vs passive events

Intentional actions:

```text
AI/inbox/actions/*.json
```

Examples:

```text
ack_nudge
snooze_nudge
answer_question
start_recovery_target
check_in
start_session
end_session
```

Passive phone telemetry:

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

Do not mix these folders.

---

## Question lifecycle

Planner writes:

```text
AI/outbox/to-phone/current-question.json
AI/state/llm/pending-question.json
```

Phone writes:

```text
AI/inbox/actions/*answer_question*.json
AI/inbox/actions/*dismiss_question*.json
```

Action bridge then:

```text
writes AI/state/llm/last-answer.json for answers
clears AI/state/llm/pending-question.json
sets current-question.json inactive
updates interaction-state.json
logs events/actions/YYYY-MM-DD.jsonl
```

`answer_question` may trigger help-now replanning.

`dismiss_question` does not trigger replanning by default.

---

## Nudge lifecycle

Planner/recovery logic writes:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/interaction-state.json
```

Phone writes:

```text
ack_nudge
snooze_nudge
start_recovery_target
```

Action bridge then:

```text
ack_nudge:
  clears nudge
  last_status = acknowledged

snooze_nudge:
  clears nudge
  last_status = snoozed
  records snoozed_until

start_recovery_target:
  starts recovery state
  clears originating nudge when nudge_id is present
  last_status = recovery_started
```

---

## Recovery target start

`start_recovery_target` is generic. Anki is the first implemented target.

Example:

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

Current result:

```text
AI/state/recovery/current.json status=active
AI/events/recovery/YYYY-MM-DD.jsonl event=recovery_started
AI/outbox/to-phone/current-nudge.json status=inactive
```

---

## Safety principles

`action-bridge` should be deterministic and conservative.

It should:

```text
process stable files only
move processed and failed files
write inspectable JSON/Markdown status
preserve raw action fields in events
avoid stale completed-session enrichment
trigger LLM only for actions that benefit from replanning
```

It should not:

```text
own passive telemetry
invent planner output
mutate TaskNotes without explicit action
treat completed sessions as active context
```

