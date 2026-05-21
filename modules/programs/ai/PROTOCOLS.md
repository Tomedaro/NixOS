# Protocols

This is the reference for AI vault paths and protocol status. Status values: current, legacy, planned, deprecated.

## Current key paths

| Path | Status | Writer | Reader | Purpose |
| --- | --- | --- | --- | --- |
| `AI/inbox/actions/*.json` | current | bounded UI/bridge/protocol producers, including phone commands/check-ins | `action-bridge` | Canonical live action queue. |
| `AI/inbox/from-phone/events/*.json` | current telemetry inbox | Tasker/phone telemetry producers | `phone-bridge` | Passive phone telemetry only; intentional commands should not be routed here. |
| `AI/inbox/session-requests/*` | current/legacy transition | older session request producers | diagnostics/session tooling | Historical session-request inbox still detected by diagnostics; prefer canonical action handling for new live requests. |
| `AI/inbox/obsidian/messages/*.json` | current | Obsidian ingress/protocol producers | Obsidian-facing processors | Reviewable incoming Obsidian messages. |
| `AI/inbox/obsidian/actions/*.json` | current | Obsidian approval/review surface | Obsidian approval/action modules | Approved Obsidian-side protocol actions. |
| `AI/outbox/to-phone/*` | current | phone/action/session modules | phone/webview surfaces | Phone-facing output. |
| `AI/outbox/to-obsidian/*` | current | AI/Obsidian protocol modules | Obsidian | Reviewable Obsidian output. |
| `AI/outbox/to-obsidian/task-drafts/*` | current | `obsidian_task_draft` | Obsidian/human review | TaskNotes draft artifacts, not real TaskNotes. |
| `AI/state/*` | current | many modules | many modules | Local state snapshots and coordination state. |
| `AI/state/anki/status.json` | current | Anki/context modules | context hub and planner consumers | Shared Anki state snapshot. |
| `AI/state/phone/ai-pi-gruvbox-card-v1.html` | current generated UI artifact | phone-webview installer/build step | phone/webview surfaces | Local phone card HTML copied into the vault. |
| `AI/events/*` and JSONL event files | current evidence | many modules | diagnostics/review | Evidence/event records; not authoritative crash-safe/tamper-evident audit logs yet. |
| `AI/events/phone/YYYY-MM-DD.jsonl` | current evidence | `phone-bridge` | diagnostics/review | Appended passive phone telemetry events. |
| `TaskNotes/` | current external durable surface | humans and future deterministic apply/promote only | TaskNotes/Obsidian/humans | Durable human commitments. Current AI paths produce reviewable drafts/proposals, not real TaskNotes writes. |
| `TaskNotes/Tasks` | current external durable surface | TaskNotes/humans and future deterministic apply/promote only | TaskNotes/Obsidian/humans | Common task directory under TaskNotes. Current AI paths should not write here directly. |

## Legacy/deprecated paths

| Path | Status | Notes |
| --- | --- | --- |
| `AI/inbox/from-obsidian` | legacy | Mentioned by diagnostics and docs as a legacy path; current Python protocol code should not depend on it. |

## Action queue rules

- Action files should be explicit JSON objects.
- Actions should have stable identity where possible.
- Processed actions should be journaled or moved so replay does not repeat side effects.
- Dangerous actions must not be mixed with routine actions under broad authority.

## Task draft vs TaskNotes rule

`AI/outbox/to-obsidian/task-drafts/*` is not `TaskNotes/`.

A task draft is reviewable proposed content. A real TaskNote is a durable human commitment. Promotion from draft/proposal to real TaskNote must be deterministic, explicit, idempotent, and reviewed.

## Schema lifecycle target

Future schema docs should include:

- schema name;
- version;
- status;
- producer;
- consumer;
- idempotency key;
- side-effect level;
- example;
- migration notes.
