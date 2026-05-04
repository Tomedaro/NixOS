# anki-bridge

Anki status bridge for the local AI productivity system.

`anki-bridge` reads Anki / AnkiConnect state and writes inspectable Anki status into the vault.

It is a sensor/status bridge. It should not own phone nudges, recovery lifecycle, or user interaction.

---

## Purpose

The bridge answers factual questions such as:

```text
Is AnkiConnect available?
Which decks have due cards?
How many reviews are due?
How many cards were reviewed today?
Is Anki backlog low, medium, high, or urgent?
```

This evidence can then be used by:

```text
llm-planner
deterministic fallback logic
future recovery trigger logic
daily review reports
```

---

## Outputs

Current canonical outputs:

```text
AI/anki/status.json
AI/anki/status.md
```

Optional/proposal outputs may include:

```text
AI/proposed-tasks/
TaskNotes/AI/
```

depending on configuration.

---

## Current role in recovery architecture

Anki is currently the first recovery target.

That does **not** mean `anki-bridge` should own the recovery loop.

Correct separation:

```text
anki-bridge:
  observes Anki state

planner / deterministic trigger:
  may decide that Anki recovery is useful

phone outbox:
  presents Start Anki action

Tasker:
  opens AnkiDroid

action-bridge:
  records start_recovery_target

future recovery lifecycle logic:
  interprets opened_ankidroid / closed_ankidroid / Anki progress evidence
```

---

## What anki-bridge should not own

`anki-bridge` should not:

```text
write phone nudges directly
process Tasker button actions
own recovery session lifecycle
decide whether the user is procrastinating
mutate TaskNotes without explicit authority/configuration
trigger punishment or strict enforcement
```

---

## TaskNotes authority model

TaskNotes mutation should be conservative.

Preferred flow:

```text
Anki status detects backlog
→ write proposal
→ user or explicit action promotes proposal
→ real TaskNote is created/updated
```

Avoid silently creating obligations.

Current intended modes:

```text
none
propose
write
```

`propose` is preferred during active development.

---

## Recovery evidence

For future recovery lifecycle classification, useful Anki evidence may include:

```text
reviewed_today increased
due count decreased
AnkiDroid opened
AnkiDroid stayed open long enough
Anki desktop / AnkiConnect reachable
```

But absence of evidence should be treated carefully. It may mean:

```text
sync delay
phone offline
AnkiConnect unavailable
user reviewed on another device
bridge not running
```

Do not overinterpret missing data.

---

## Design principles

`anki-bridge` should be:

```text
local-first
deterministic
read-mostly
inspectable
safe if AnkiConnect is unavailable
conservative with TaskNotes writes
```

It should treat backlog as a load-management signal, not as failure.

---

## Current pending work

Useful future improvements:

```text
better per-deck recovery suggestions
Anki progress delta events
sync-aware status
explicit recovery evidence summaries
proposal cleanup/retention
integration with generic recovery lifecycle
```
