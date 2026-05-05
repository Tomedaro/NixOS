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
