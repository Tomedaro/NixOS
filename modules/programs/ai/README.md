# Local AI Productivity System

This module tree implements a local-first productivity system using:

- ActivityWatch / awatcher for desktop activity
- Anki bridge for study state
- Tasker/Syncthing for phone events
- Obsidian vault as durable shared memory
- Ollama for local LLM planning
- swaync notifications for low-friction interaction

## Design principles

1. Raw sensors should be deterministic and cheap.
2. Raw events should be compacted before reaching the LLM.
3. The LLM should reason over curated context, not noisy logs.
4. The LLM may propose actions before it mutates real task systems.
5. Files should have clear ownership.
6. Boot-time stale state must not cause wrong interventions.

## Service responsibilities

- `vault-bridge`: creates folder structure and seed templates.
- `activitywatch`: starts ActivityWatch server/watchers.
- `coach-daemon`: immediate rule-based desktop feedback.
- `phone-bridge`: compacts Tasker phone events.
- `anki-bridge`: writes Anki status/progress files.
- `llm-planner`: builds compact context, calls local LLM, writes reports/nudges/questions.
- `dialog-bridge`: presents LLM questions and records answers.

## LLM authority level

Current authority:

- write reports
- write proposed tasks
- write phone nudges
- write pending questions

Not yet allowed:

- delete files
- freely mutate TaskNotes
- close apps
- block websites
- reschedule all tasks
