# Local AI Architecture

This project is a local, file-based productivity assistant. The vault is the runtime surface; the NixOS repo is the source of truth for code, services, tests, and installable artifacts.

## Core principle

Use append-only events as the durable record, and materialized state files as caches/views.

State files may be overwritten by bridges/managers. Event logs should explain why state changed.

## Runtime roots

Default runtime vault:

`/home/daniil/Sync/Perseverance.Gu/AI`

Important queues and state:

- `outbox/to-phone/current-nudge.json`: current nudge rendered by phone WebView.
- `outbox/to-phone/current-question.json`: current question rendered by phone WebView.
- `outbox/to-phone/interaction-state.json`: combined phone interaction state.
- `inbox/actions/*.json`: intentional phone/user commands.
- `inbox/from-phone/events/*.json`: passive phone telemetry only.
- `events/actions/YYYY-MM-DD.jsonl`: processed command events.
- `events/phone/YYYY-MM-DD.jsonl`: processed phone telemetry.
- `events/recovery/YYYY-MM-DD.jsonl`: recovery lifecycle events.
- `events/interventions/YYYY-MM-DD.jsonl`: intervention/nudge presentation events.
- `state/recovery/current.json`: current recovery session cache.
- `state/interventions/current.json`: current intervention outcome cache.
- `state/interventions/stats.json`: current intervention outcome stats cache.

## Components

### Phone WebView

Source of truth:

`modules/programs/ai/phone-webview/`

Installed into the vault by:

`modules/programs/ai/phone-webview/install-to-vault.sh`

Responsibilities:

- Render current nudge/question.
- Write intentional actions to `AI/inbox/actions/*.json`.
- For recovery nudges, write `start_recovery_target` with `nudge_id`, `intervention_id`, target metadata, and `launch_task`.
- Never write passive telemetry.

### Tasker profiles/tasks

Tasker observes Android app lifecycle and writes passive telemetry:

`AI/inbox/from-phone/events/*.json`

Expected Anki events:

- `opened_ankidroid`
- `closed_ankidroid`

Tasker launch task may be called from WebView via `performTask`.

### phone-bridge

Source:

`modules/programs/ai/phone-bridge/phone_bridge.py`

Responsibilities:

- Process passive phone telemetry only.
- Reject command-shaped files in `inbox/from-phone/events`.
- Reject malformed raw phone events such as unexpanded Tasker variables.
- Append normalized events to `events/phone/YYYY-MM-DD.jsonl`.
- Move raw files to processed/failed queues.
- Maintain `state/phone/latest.json` and `state/phone/latest.md`.

### action bridge

Responsibilities:

- Process intentional actions from `AI/inbox/actions/*.json`.
- Convert user actions into action events and state transitions.
- Start recovery sessions from `start_recovery_target`.
- Clear/snooze/ack nudges and questions.
- Preserve `intervention_id` linkage.

### recovery trigger / proposal gate

Responsibilities:

- Decide whether to propose a recovery nudge.
- Use agent context and gates.
- Never launch apps directly.
- Write only a validated phone nudge.

### recovery manager

Responsibilities:

- Observe phone events after a recovery starts.
- Build app-open intervals.
- Sum dwell time across interrupted sessions.
- Collapse duplicate opens so dwell is not double counted.
- Keep terminal recovery classifications stable.
- Emit lifecycle events to `events/recovery/YYYY-MM-DD.jsonl`.

Important thresholds:

- open grace: 30 seconds
- rapid abort: 90 seconds
- success dwell: 300 seconds
- observation window: 900 seconds

### intervention outcome reporter

Responsibilities:

- Join intervention, action, and recovery events.
- Summarize shown/acted/started/terminal/success rates.
- Write `state/interventions/current.json`, `stats.json`, and `status.md`.

## Invariants

1. `inbox/actions` is for commands; `inbox/from-phone/events` is for passive telemetry.
2. Action-shaped files in phone telemetry are invalid.
3. Unexpanded Tasker variables such as `%ai_event_epoch` are invalid in raw phone event filenames or timestamps.
4. WebView action payloads must include correlation ids when available:
   - `nudge_id`
   - `interaction_id`
   - `intervention_id`
   - `intervention_kind`
5. Recovery classification is terminal once it reaches a terminal outcome; later noise must not downgrade it.
6. Interrupted Anki usage should sum dwell across intervals inside the observation window.
7. Duplicate open events must not double count dwell.
8. Runtime vault files are deploy targets, not source-of-truth code. Repo files are source of truth.
9. Dev scripts must copy full logs with `wl-copy < "$LOG"`, not just echo a path into the clipboard.
10. Live mutating checks must be explicit. Inspection is default.

## Development workflow

Common commands:

```bash
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/check-ai-live.sh
modules/programs/ai/dev/check-ai-live.sh --run-recovery --run-outcomes
modules/programs/ai/dev/check-phone-bridge-live.sh
modules/programs/ai/dev/rebuild-default.sh
modules/programs/ai/phone-webview/install-to-vault.sh check
modules/programs/ai/phone-webview/install-to-vault.sh install
```

Expected before committing:

1. `git diff --check`
2. Python compile checks
3. Smoke suite passes
4. Live check shows no unexpected pending queues
5. If runtime artifacts changed, installer drift check passes

## Current intentional simplification

The project is still in development. Prefer deleting stale compatibility layers over preserving old implementations. Legacy Tasker/WebView versions should not remain on the active vault surface unless they are explicitly needed for debugging.
