# dialog-bridge

Desktop question/notification UI adapter for the local AI productivity system.

`dialog-bridge` exists to show local desktop prompts and route user responses into the canonical action protocol.

It should be a thin UI layer, not a lifecycle owner.

---

## Current architectural role

The canonical interaction lifecycle is now owned by:

```text
action-bridge
```

The canonical phone/desktop response inbox is:

```text
AI/inbox/actions/*.json
```

The canonical outbound interaction files are:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

Although the current name says `to-phone`, the JSON protocol is generic enough to be read by multiple UI surfaces.

---

## Intended direction

`dialog-bridge` should become a desktop UI adapter:

```text
read current-question/current-nudge JSON
→ show desktop notification/dialog
→ write canonical action JSON
→ action-bridge handles lifecycle
```

UI adapters should write canonical actions such as:

```text
answer_question
dismiss_question
ack_nudge
snooze_nudge
```

Current `dialog-bridge` desktop answer UI queues `answer_question` only into `AI/inbox/actions`. It must not emit `dismiss_question` until there is a real desktop dismiss signal.

It should not directly mutate:

```text
AI/state/llm/pending-question.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/interaction-state.json
```

Those lifecycle transitions belong to `action-bridge`.

---

## Question lifecycle

Planner writes a question:

```text
AI/outbox/to-phone/current-question.json
AI/state/llm/pending-question.json
```

A UI adapter displays it and writes one of:

```text
AI/inbox/actions/*answer_question*.json
AI/inbox/actions/*dismiss_question*.json
```

Then `action-bridge`:

```text
logs the answer/dismissal
processes queued answer_question/dismiss_question action files
clears pending-question
sets current-question inactive
updates interaction-state
optionally triggers help-now after an answer
```

---

## Nudge lifecycle

A UI adapter may display an active nudge and write one of:

```text
ack_nudge
snooze_nudge
start_recovery_target
```

Then `action-bridge` owns the transition:

```text
ack_nudge
→ current nudge inactive / acknowledged

snooze_nudge
→ current nudge inactive / snoozed

start_recovery_target
→ recovery starts
→ originating nudge inactive / recovery_started
```

---

## What dialog-bridge should not own

`dialog-bridge` should not:

```text
decide when to nudge
own question lifecycle
own nudge lifecycle
own recovery lifecycle
call Ollama directly
mutate TaskNotes
process passive phone telemetry
treat completed sessions as active
```

---

## Relationship to Tasker/WebView

Tasker/WebView is currently the primary phone UI adapter.

`dialog-bridge` can provide the desktop equivalent.

Both should follow the same pattern:

```text
read structured outbox JSON
render UI
write canonical action JSON
let action-bridge update state
```

This keeps desktop and phone interaction behavior consistent.

---

## Current pending work

Useful future improvements:

```text
refactor to read structured JSON instead of old Markdown/pending-question assumptions
add a real dismiss UI signal before emitting dismiss_question actions
support ack_nudge and snooze_nudge
respect interaction-state active_nudge/active_question
avoid repeated prompts after snooze or recovery start
make desktop prompt style non-intrusive
```


Current status: `dialog-bridge` queues canonical `answer_question` action files into `AI/inbox/actions`; `action-bridge` processes queued `answer_question` and `dismiss_question` actions and owns lifecycle/state side effects. The current desktop notification UI emits answer actions only; `dismiss_question` remains canonical in `action-bridge` for surfaces that emit a real dismiss signal.
