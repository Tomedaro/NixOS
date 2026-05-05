# AI dev workflow

Repo-owned commands for local development and controlled live checks.

## Commands

```bash
modules/programs/ai/dev/run-smoke.sh
```

Runs Python syntax checks and the AI smoke suite.

```bash
modules/programs/ai/dev/rebuild-default.sh
```

Rebuilds and switches the NixOS flake configuration `#Default`. It refuses to run from a dirty tree unless called with:

```bash
modules/programs/ai/dev/rebuild-default.sh --allow-dirty
```

```bash
modules/programs/ai/dev/check-phone-bridge-live.sh
```

Inspects the live `phone-bridge.service`, runs its installed wrapper with `--once`, and reports raw/processed/failed phone event queue state.

## Output handling

Each command writes full output to `/tmp/...txt` and copies the full output with:

```bash
wl-copy < "$LOG"
```

This avoids the previous mistake of copying only the output path.

## Boundary rule

Phone writes only:

* `AI/inbox/actions/*.json` for intentional commands.
* `AI/inbox/from-phone/events/*.json` for passive telemetry.

Desktop services own state, reports, and append-only event logs.

```bash id="w7k9lc"
modules/programs/ai/dev/check-ai-live.sh
```

Inspects the live AI services and queues. By default it only runs the safe passive check:

```bash id="0w951g"
phone-bridge --once
```

It does **not** process live action/recovery/trigger queues unless explicitly requested:

```bash id="yx0z5a"
modules/programs/ai/dev/check-ai-live.sh --process-actions
modules/programs/ai/dev/check-ai-live.sh --run-recovery
modules/programs/ai/dev/check-ai-live.sh --run-trigger
modules/programs/ai/dev/check-ai-live.sh --run-outcomes
```

Use these mutating flags one at a time when debugging live state.
