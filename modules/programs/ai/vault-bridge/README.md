# vault-bridge

Vault folder initializer for the local AI productivity system.

Service:

```text
ai-vault-init.service
```

---

## Purpose

`vault-bridge` creates the shared file-protocol structure inside the Obsidian vault.

The vault is the API between:

```text
NixOS services
Obsidian
TaskNotes
Tasker
Syncthing
Anki / AnkiConnect
local LLM planner
phone UI
future recovery/lifecycle daemons
```

The folder structure must be predictable, inspectable, and safe to recreate.

---

## Main AI folder

Default path:

```text
/home/daniil/Sync/Perseverance.Gu/AI
```

TaskNotes path:

```text
/home/daniil/Sync/Perseverance.Gu/TaskNotes
```

---

## Ownership model

The vault is not just notes. It is a local file protocol.

Desktop/local services write:

```text
AI/state/
AI/events/
AI/logs/
AI/context/
AI/reports/
AI/outbox/
AI/proposed-tasks/
```

Phone/Tasker writes intentional actions:

```text
AI/inbox/actions/*.json
```

Phone/Tasker writes passive telemetry:

```text
AI/inbox/from-phone/events/*.json
```

Human-editable configuration lives mainly in:

```text
AI/control/
AI/policy/
```

LLM-created obligations should first go to:

```text
AI/proposed-tasks/
```

Real TaskNotes live outside `AI/`:

```text
../TaskNotes/
```

---

## Current important directories

Core control and policy:

```text
AI/control/
AI/policy/
```

Runtime state:

```text
AI/state/desktop/
AI/state/phone/
AI/state/session/
AI/state/llm/
AI/state/action-bridge/
AI/state/recovery/
```

Inboxes:

```text
AI/inbox/actions/
AI/inbox/actions-processed/
AI/inbox/actions-failed/

AI/inbox/from-phone/events/
AI/inbox/from-phone/processed/
AI/inbox/from-phone/failed/
```

Outboxes:

```text
AI/outbox/to-phone/
AI/outbox/to-desktop/
```

Events:

```text
AI/events/actions/
AI/events/desktop/
AI/events/phone/
AI/events/anki/
AI/events/recovery/
AI/events/tasknotes/
AI/events/proofs/
```

Logs and reports:

```text
AI/logs/desktop/
AI/logs/phone/
AI/logs/anki/
AI/reports/help-now/
AI/reports/daily/
AI/reports/weekly/
```

Other protocol folders:

```text
AI/anki/
AI/proofs/
AI/reflections/
AI/proposed-tasks/
AI/templates/
AI/templates/actions/
AI/schemas/
AI/tmp/
AI/cache/
AI/archive/
```

---

## Phone interaction protocol files

The current canonical phone outbox files are:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

Markdown mirrors:

```text
AI/outbox/to-phone/current-nudge.md
AI/outbox/to-phone/current-question.md
```

These should exist even if inactive, because Tasker/WebView reads stable paths.

See:

```text
modules/programs/ai/PHONE_INTERACTION_PROTOCOL.md
```

---

## Recovery state files

Current recovery files:

```text
AI/state/recovery/current.json
AI/state/recovery/status.md
AI/events/recovery/YYYY-MM-DD.jsonl
```

Recovery starts from canonical action files:

```text
AI/inbox/actions/*start_recovery_target*.json
```

See:

```text
modules/programs/ai/RECOVERY_TARGET_LOOP.md
```

---

## Seed files

`vault-bridge` may seed human-readable defaults such as:

```text
AI/README.md
AI/control/current-task.md
AI/control/current-block.md
AI/control/current-mode.md
AI/policy/apps.md
AI/policy/domains.md
AI/policy/proof.md
AI/policy/retention.md
AI/outbox/to-phone/current-nudge.md
AI/outbox/to-phone/current-question.md
```

Seed files should be conservative and should not overwrite existing user-edited files.

---

## Design principles

`vault-bridge` should be:

```text
idempotent
boring
safe to rerun
minimal
declarative where practical
friendly to Syncthing
```

It should not:

```text
process actions
process phone telemetry
call Ollama
start sessions
own recovery lifecycle
mutate TaskNotes content
overwrite user-edited policy files
```

---

## Current pending improvements

Useful next improvements:

```text
seed inactive phone JSON files, not only Markdown
ensure AI/state/recovery exists
ensure AI/events/recovery exists
document schemas in AI/schemas/
possibly generate protocol example files
avoid obsolete current-task defaults that imply Anki is always active
```

The initializer should reflect the current architecture:

```text
structured phone interaction
canonical action bridge
strict action/event separation
generic recovery target loop
session-centered policy
deterministic fallback first
```
