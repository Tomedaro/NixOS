# AI System Development Guidelines

This project is a local-first, file-queue based productivity system. Optimize for safety, inspectability, and boring operational behavior before adding autonomy.

This document is an operator/developer guide. It is not a substitute for fresh source code, current diffs, or current test output.

## Running checks

From the repo root:

```bash
cd /home/daniil/NixOS
```

Full smoke suite:

```bash
modules/programs/ai/dev/run-smoke.sh
```

Live/project audit:

```bash
modules/programs/ai/dev/audit-ai-project.sh
```

Verbose audit when investigating details:

```bash
modules/programs/ai/dev/audit-ai-project.sh --verbose
```

Compile all AI Python files:

```bash
nix shell nixpkgs#python3 -c python3 -m compileall -q modules/programs/ai
```

Focused smoke test:

```bash
nix shell nixpkgs#python3 -c python3 modules/programs/ai/tests/<name>_smoke.py
```

When running scripts directly, make the shared Python library importable:

```bash
PYTHONPATH=/home/daniil/NixOS/modules/programs/ai/python \
  nix shell nixpkgs#python3 -c python3 modules/programs/ai/path/to/script.py
```

## Queue semantics

File inboxes are queues, not shared mutable state.

Queue readers should:

1. process only complete non-hidden `.json` files;
2. ignore dotfiles, editor/sync temp files, backup files, partial files, and non-JSON files;
3. use a stability delay for live queues unless every writer is proven atomic;
4. drain all ready files on each activation;
5. treat systemd path units as wakeups only;
6. archive raw files to processed, failed, or manual-review directories.

Use `ai_system.queue.list_stable_json_queue_files` for live queue readers. Do not hand-roll `glob("*.json")` or `iterdir()` for live inboxes unless the reason is documented and tested.

## Canonical queues

Phone passive telemetry:

```text
AI/inbox/from-phone/events/*.json
```

Intentional actions and check-ins:

```text
AI/inbox/actions/*.json
```

Obsidian messages and proposal decisions:

```text
AI/inbox/obsidian/messages/*.json
AI/inbox/obsidian/actions/*.json
```

Legacy `AI/inbox/from-obsidian/...` references should be removed or explicitly marked historical.

## Action safety

Anything that can trigger user-visible or system-visible side effects must pass through the proposal/action boundary.

Current rules:

* Obsidian planning writes reviewable proposals only.
* Proposal approval writes reviewed artifacts only.
* Live actions go through `AI/inbox/actions`.
* The action bridge writes a durable journal before side effects.
* Duplicate processed action ids must not repeat side effects.
* Stale `processing` journals go to manual review, not replay.

To retry a manual-review action, inspect the archived file and create a new action with a new `action_id` or `idempotency_key`. Do not move the same raw file back into `AI/inbox/actions`.

## Diagnostics

Default diagnostics should be compact and safe. Verbose output should be opt-in.

Live diagnostics must not mutate action/recovery state unless an explicit flag is passed, such as:

```text
--process-actions
--run-recovery
--run-trigger
--run-outcomes
```

Status files are materialized views. They may be stale if the producing service is disabled, not installed, or has not run recently. Prefer diagnostics that show service/timer state next to status files.

## Formatting and commits

Avoid mixing behavior changes with large formatting-only changes.

Before committing behavior changes, inspect:

```bash
git diff --stat
git diff --check
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/audit-ai-project.sh
```

Run broad formatters only on files intentionally touched for the change. If a broad formatting pass is useful, keep it separate from behavior changes.

## Systemd hardening approach

Do systemd hardening incrementally and per service.

Start only after queue contracts, docs, smoke tests, audit, and live diagnostics are stable.

Low-risk first pass:

```nix
serviceConfig = {
  NoNewPrivileges = true;
  PrivateTmp = true;
  TasksMax = 64;
  MemoryMax = "256M";
};
```

Do not start with strict filesystem, device, syscall, or home-directory sandboxing until each service has an explicit read/write path and subprocess inventory.
