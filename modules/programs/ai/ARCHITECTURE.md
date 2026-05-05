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

## Canonical contract policy

This repository is still in active development. Prefer removing old implementations over adding compatibility layers.

Current active contracts are documented here and in current smoke tests. Historical files such as early architecture reviews, old phone interaction protocols, Tasker v1/v2 exports, WebView debug snapshots, inline backups, and malformed Tasker variable artifacts are not active APIs.

When changing contracts:

1. Update this document.
2. Update or add smoke tests.
3. Run `modules/programs/ai/dev/run-smoke.sh`.
4. Run `modules/programs/ai/dev/audit-ai-project.sh`.
5. Rebuild `Default` if a packaged runtime changed.

## Engineering best practices

This project should stay biased toward simple, observable, file-backed state machines.

### Current development posture

The system is still in active development. Prefer clean contracts over compatibility layers. Old Tasker/WebView/protocol implementations should be removed from the active surface instead of supported indefinitely. If history matters, keep it in Git history or in a short migration note, not in runtime paths.

### Runtime boundaries

- Phone WebView writes intentional user actions only to `AI/inbox/actions/*.json`.
- Tasker app lifecycle profiles write passive telemetry only to `AI/inbox/from-phone/events/*.json`.
- `phone-bridge` is a passive telemetry normalizer.
- `action-bridge` is the authority for user actions.
- Recovery manager classifies observed lifecycle evidence; it should not create nudges.
- Recovery trigger proposes nudges; it should not classify lifecycle outcomes.
- Outcome reporter summarizes interventions; it should not mutate interaction state.

### Queue discipline

Every queue processor should use the same shape:

1. Read stable files only.
2. Validate strictly.
3. Normalize into canonical events.
4. Append immutable JSONL event records.
5. Move raw files to processed or failed.
6. Write a small materialized current/status view.

Invalid files should fail loudly and move out of the hot inbox. Do not silently coerce malformed Tasker data.

### Idempotency and interruption tolerance

Recovery lifecycle logic should be robust to duplicated open events, missing close events, short interruptions, noisy app switches, and late events after terminal classification. Dwell should be summed across valid intervals, but terminal success should not be downgraded by later noise.

### Operational hygiene

- Dev scripts should be runnable from a clean checkout.
- Do not assume host Python exists; use `nix shell nixpkgs#python3 -c python3 ...`.
- Prefer `--once` modes for debug and live checks.
- Default live checks should be inspect-first and non-mutating, except passive safe drains such as `phone-bridge --once`.
- Mutating live operations should require explicit flags.
- Clipboard helpers must copy full output, not only a path.
- Audit scripts should fail on active legacy runtime references, not merely print them.

### Testing expectations

Every runtime contract change should include a smoke/regression test. The minimum useful suite covers:

- valid phone telemetry processing,
- malformed phone telemetry rejection,
- misrouted action rejection,
- action bridge nudge actions,
- recovery interruption and duplicate event handling,
- proposal gate blockers,
- outcome summarization,
- live/dev workflow scripts.

### Documentation expectations

Architecture docs should describe current contracts and invariants, not preserve every historical implementation. Old standalone architecture/protocol docs can be deleted once their live invariants are consolidated into `ARCHITECTURE.md` and `README.md`.
