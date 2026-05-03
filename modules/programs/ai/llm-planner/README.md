# llm-planner

The planner converts compact productivity evidence into:

- daily report
- proposed tasks
- phone nudge
- pending question

It deliberately does not mutate real TaskNotes yet.

## Inputs

- `AI/state/desktop/now.json`
- `AI/state/phone/latest.json`
- `AI/events/desktop/YYYY-MM-DD.jsonl`
- `AI/events/phone/YYYY-MM-DD.jsonl`
- `AI/logs/desktop/YYYY-MM-DD.md`
- `AI/logs/phone/YYYY-MM-DD.md`
- `AI/anki/status.json`
- `AI/control/*.md`
- recent TaskNotes snippets

## Outputs

- `AI/context/today.md`
- `AI/context/today.json`
- `AI/state/llm/last-output.json`
- `AI/state/llm/last-output.md`
- `AI/state/llm/pending-question.json`
- `AI/reports/daily/YYYY-MM-DD.md`
- `AI/proposed-tasks/YYYY-MM-DD.md`
- `AI/outbox/to-phone/current-nudge.md`
- `AI/outbox/to-phone/current-question.md`

## Modes

Default mode is `OLLAMA_FORMAT=json`.

Schema mode can be tested with:

```text
OLLAMA_FORMAT=schema
Use JSON mode until the compact context and output quality are stable.
