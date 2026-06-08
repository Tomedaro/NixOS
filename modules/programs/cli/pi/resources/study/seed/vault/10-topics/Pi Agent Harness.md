---
type: topic
status: learning
created: 2026-06-06
tags: [pi, agents, tooling]
related: ["[[Agent Memory]]", "[[NixOS]]"]
confidence: 2
---

# Pi Agent Harness

## Core idea

Pi is a terminal coding harness extended through settings, packages, extensions, skills, prompts, themes, and project resources.

## What to remember

- Keep global context small.
- Use project-specific `.pi/settings.json` for project-specific packages/resources.
- Use skills/prompts for repeatable workflows.
- Use policies and wrappers for safety boundaries.
- Use real OS sandboxing only when a future `pi-sandbox` profile exists.
