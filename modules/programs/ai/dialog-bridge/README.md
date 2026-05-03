# dialog-bridge

Desktop question/answer bridge for the local AI productivity system.

## Lifecycle

```text
pending-question.json
  -> shown as desktop notification
  -> answer selected
  -> question_answered event written
  -> pending question archived
  -> current-question.md marked inactive
  -> llm-planner triggered
Inputs
AI/state/llm/pending-question.json
Outputs
AI/state/desktop/dialog-bridge-state.json
AI/state/llm/last-answer.json
AI/inbox/from-desktop/events/*.json
AI/events/desktop/YYYY-MM-DD.jsonl
AI/state/llm/questions/archive/YYYY-MM-DD/*.json
AI/outbox/to-phone/current-question.md
Notes

Desktop v0 supports button answers only. Free-text answers should be implemented later through phone Tasker input, wofi/rofi, or another dedicated input surface.
