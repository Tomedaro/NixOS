# Operations

## Safe verification commands

Run from the repository root:

```bash
cd /home/daniil/NixOS
git diff --check
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/check-ai-live.sh
modules/programs/ai/dev/audit-ai-project.sh --verbose
git status --short --branch
stale_typo='They''do'
stale_repo='$''REPO/'
stale_obsidian='AI/inbox/from-'"obsidian"
grep -RIn --color=never "$stale_typo\|$stale_repo\|$stale_obsidian" modules/programs/ai || true
```

## Diagnostics safety

`check-ai-live.sh` should remain safe by default. Mutating checks should require explicit flags such as action processing, recovery manager execution, trigger execution, outcome writing, or interaction refresh.

## Before behavior changes

- Run smoke tests.
- Read `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `MODULES.md`.
- Confirm whether the target path is read-only, proposal-only, draft-only, live action, or real TaskNotes mutation.
- Add tests before changing dangerous paths.

## When inspecting live state

Do not mutate live queues unless explicitly intending to test a mutating flow. Prefer copies, temp vaults, fixtures, and isolated smoke tests.

## Troubleshooting docs consistency

The stale-pattern grep may still report explicitly marked legacy/diagnostic references. Treat unmarked or active-code dependencies as problems; marked documentation and diagnostic warnings are expected until the legacy paths are removed.

- If docs disagree with source, source/tests win.
- If TODOs disagree with current state, current-state docs should be updated and TODOs corrected.
- If an old path is still mentioned, mark it current, legacy, planned, or deprecated.
