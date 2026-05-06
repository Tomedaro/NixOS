# AI dev workflow

Repo-owned commands for local development, controlled live checks, and before-push validation.

## Before pushing AI changes

Use this checklist before `git push`:

```bash
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/check-ai-live.sh
modules/programs/ai/dev/audit-ai-project.sh

git status --short
git diff --check
git diff --stat
```

Expected result:

* smoke exits `0`
* live check exits `0`
* audit exits `0`
* no malformed processed phone telemetry
* no pending action inbox entries unless intentionally debugging them
* `git diff --check` is empty
* `git status --short` only shows files you intend to commit, or nothing after commit

## Commands

### Smoke tests

```bash
modules/programs/ai/dev/run-smoke.sh
```

Runs Python syntax checks and the AI smoke suite.

### Live AI check

```bash
modules/programs/ai/dev/check-ai-live.sh
```

Inspects the live AI services and queues. Default mode is compact and mostly inspect-only. It runs the safe passive phone bridge once check:

```bash
phone-bridge --once
```

It does **not** process live action, recovery, trigger, or outcome queues unless explicitly requested:

```bash
modules/programs/ai/dev/check-ai-live.sh --process-actions
modules/programs/ai/dev/check-ai-live.sh --run-recovery
modules/programs/ai/dev/check-ai-live.sh --run-trigger
modules/programs/ai/dev/check-ai-live.sh --run-outcomes
```

Use mutating flags one at a time when debugging live state.

Use verbose mode when the compact output is not enough:

```bash
modules/programs/ai/dev/check-ai-live.sh --verbose
```

### Project audit

```bash
modules/programs/ai/dev/audit-ai-project.sh
```

Runs a broad non-mutating repo/runtime audit: compile checks, dev script syntax, source tree summary, queue health, materialized state summary, expected systemd user units, legacy guardrails, and dev script executability.

Use verbose mode when investigating details:

```bash
modules/programs/ai/dev/audit-ai-project.sh --verbose
```

### Rebuild Default

```bash
modules/programs/ai/dev/rebuild-default.sh
```

Rebuilds and switches the NixOS flake configuration `#Default`. It refuses to run from a dirty tree unless called with:

```bash
modules/programs/ai/dev/rebuild-default.sh --allow-dirty
```

### Phone bridge focused check

```bash
modules/programs/ai/dev/check-phone-bridge-live.sh
```

Inspects the live `phone-bridge.service`, runs its installed wrapper with `--once`, and reports raw, processed, and failed phone event queue state.

## Output handling

Each command writes full output to `/tmp/...txt` and copies the full output with:

```bash
wl-copy < "$LOG"
```

This avoids copying only the output path.

## Boundary rule

Phone writes only:

* `AI/inbox/actions/*.json` for intentional commands.
* `AI/inbox/from-phone/events/*.json` for passive telemetry.

Desktop services own state, reports, and append-only event logs.

## Cleanup rule

Malformed phone telemetry, especially filenames containing unexpanded Tasker variables, should not remain in processed queues. The live check reports this explicitly:

```text
===== malformed processed phone telemetry =====
none
```

Processed and failed queue listings are intentionally compact by default. Use verbose mode only when investigating.
