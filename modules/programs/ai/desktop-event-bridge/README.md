# desktop-event-bridge

Consumes event files from:

`AI/inbox/from-desktop/events/*.json`

Normalizes them into:

`AI/events/desktop/YYYY-MM-DD.jsonl`

When an event has `answer` or `answer_label`, it updates:

`AI/state/llm/last-answer.json`

Meaningful check-ins trigger:

`llm-planner-help-now.service`

This makes Obsidian check-ins and future desktop-panel inputs part of the same event protocol as dialog/phone answers.
