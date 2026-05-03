# session-manager

Starts and ends AI productivity sessions.

A session is the bridge between human intention and monitoring policy.

## Backend command

```sh
ai-session start \
  --task "Anki Language recovery" \
  --mode anki \
  --duration 25 \
  --strictness 2

This command is mostly for modules, tests, and debugging.

Human-facing interface

Normal user-facing control should happen through request files created by:

Obsidian template/button
Tasker widget
TaskNotes action
future desktop panel

Drop request files into:

AI/inbox/session-requests/*.json

The request bridge processes them and calls ai-session.

Example request
{
  "command": "start",
  "source": "obsidian",
  "task": "Anki Language recovery",
  "project": "Anki Recovery",
  "mode": "anki",
  "duration": 25,
  "strictness": 2,
  "language_level": 1
}
Writes
AI/state/session/current.json
AI/state/session/current-policy.json
AI/state/session/current-policy.md
AI/state/session/request-bridge-status.md
AI/control/current-task.md
AI/control/current-mode.md
AI/control/current-block.md
AI/events/desktop/YYYY-MM-DD.jsonl
Modes
ai-session modes
Design

The session manager is deterministic in v0.

Later the policy compiler can be upgraded to include LLM-suggested policy changes, TaskNotes metadata, long-term goals, browser context, and learned user patterns.
