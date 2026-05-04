# session-manager

Session and deterministic policy compiler for the local AI productivity system.

Command:

```text
ai-session
```

Supported commands:

```text
ai-session start
ai-session status
ai-session end
ai-session modes
```

---

## Purpose

A session represents the current intentional block of behavior.

Examples:

```text
Anki recovery
coding
writing
reading
learning-video
admin
free/rest
```

A session compiles a deterministic policy that other services can use without asking the LLM.

The policy answers:

```text
what task is active
which mode is active
which apps/domains/titles are allowed
which apps/domains/titles are distracting
what proof may be expected
what reflection questions are relevant
what intervention level is appropriate
```

---

## Files written

Current session state:

```text
AI/state/session/current.json
AI/state/session/current-policy.json
AI/state/session/current-policy.md
```

Human-readable control mirrors:

```text
AI/control/current-task.md
AI/control/current-mode.md
AI/control/current-block.md
```

Events:

```text
AI/events/desktop/YYYY-MM-DD.jsonl
```

Archived ended sessions:

```text
AI/state/session/archive/YYYY-MM-DD/<session-id>.json
```

---

## Important active-session rule

`current.json` may contain the last session even after it has ended.

Therefore consumers must check:

```text
status == "active"
```

before treating the session as current intent.

Correct behavior:

```text
status = active
→ enrich events with session_id/mode/task/project
→ planner/fallback may respect current task
```

```text
status = completed / abandoned / paused / interrupted
→ treat as historical context only
→ do not enrich new action events as if active
→ do not fallback to that task as current intent
```

This prevents stale smoke-test or previous-session state from contaminating current nudges.

---

## Modes

Current deterministic modes include:

```text
study
anki
coding
writing
reading
learning-video
admin
free
```

Each mode has default policy fields:

```text
allowed_apps
distracting_apps
allowed_domains
distracting_domains
allowed_title_keywords
distracting_title_keywords
proof
reflection_questions
language
intervention
```

---

## Session-centered design

The system should not rely forever on a manually edited `current-task.md`.

The runtime object is the session:

```text
session
→ compiled policy
→ coach classification
→ planner context
→ phone nudges/questions
→ proof/reflection expectations
```

The same app or website can be allowed or distracting depending on the active session.

Examples:

```text
YouTube during free time:
  possibly fine

YouTube lecture during learning-video:
  allowed

YouTube Shorts during Anki recovery:
  distracting
```

---

## Relationship to action-bridge

`session-manager` owns session creation and policy compilation.

`action-bridge` owns canonical action routing.

Phone/Tasker or Obsidian should usually start/end sessions by writing actions to:

```text
AI/inbox/actions/*.json
```

Examples:

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "start_session",
  "task": "Anki Language recovery",
  "project": "Anki Recovery",
  "mode": "anki",
  "duration": 25,
  "strictness": 2
}
```

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "end_session",
  "status": "completed",
  "reason": "Finished block"
}
```

`action-bridge` delegates these to `ai-session`.

---

## Relationship to recovery targets

Recovery targets are not the same as sessions.

A recovery target is a tiny restart path:

```text
tap Start Anki
→ open AnkiDroid
→ do 5 cards or 5 minutes
```

A full session is a stronger intentional block:

```text
start Anki session
→ policy active
→ desktop/phone coach can classify behavior
→ reflection/proof expectations may apply
```

For v1, recovery can exist without an active session.

Later, successful recovery may optionally propose or start a real session, but that should be explicit and inspectable.

---

## Safety principles

`session-manager` should be:

```text
deterministic
local-first
inspectable
safe without LLM
small enough to debug with cat/jq
```

It should not:

```text
call Ollama
process phone telemetry
own nudge/question lifecycle
mutate TaskNotes directly
treat completed sessions as active
```

---

## Current pending work

Useful future improvements:

```text
explicit active/inactive session index
session pause/resume semantics
session expiry handling
better policy templates
generic recovery-to-session handoff
markdown docs for each mode
```
