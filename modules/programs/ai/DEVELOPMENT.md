# AI System Development Guidelines

This project is a local-first, file-queue based adaptive productivity companion. Optimize for safety, inspectability, and boring operational behavior before adding autonomy.

## Product direction

<!-- AI-CONFIG-RULES:START -->

## Configuration and path rules

Treat `modules/programs/ai/default.nix` as the high-level profile layer for this project.

Best practice for new code:

* expose a typed Nix option when behavior should be adjustable;
* set user-facing defaults in `modules/programs/ai/default.nix`;
* pass resolved values into scripts through environment variables or CLI flags;
* use `AI_DIR` instead of hardcoded absolute vault paths;
* use `AI_TIMEZONE` instead of hardcoded timezone strings;
* keep protocol-relative paths stable and documented;
* use temporary directories in tests;
* avoid mixing docs-only updates with behavior changes unless the diff is explicitly reviewed as behavior.

Acceptable:

```python
ai_dir = Path(os.environ.get("AI_DIR", default))
```

Preferred for CLIs:

```text
--ai-dir "$AI_DIR"
```

Avoid in active runtime code:

```python
Path("/home/daniil/Sync/Perseverance.Gu/AI")
```

Hardcoded absolute paths may appear in examples or migration notes, but docs must not imply they are the authority.

<!-- AI-CONFIG-RULES:END -->

The system should help the user reach long-term and short-term goals by observing behavior, learning patterns, adapting nudges/plans, asking useful questions, and recording outcomes. It should value sustainable goal progress and quality productive hours over raw time or notification volume.

The system may automatically adapt from evidence, including inaction, but adaptations must be inspectable, reversible, locally stored, and bounded by explicit goals, safety policies, capacity state, and user correction.

## Running checks

From the NixOS repo root:

```bash
cd /home/daniil/NixOS || exit 1
```

Focused smoke test:

```bash
nix shell nixpkgs#python3 -c python3 modules/programs/ai/tests/<name>_smoke.py
```

Full smoke suite:

```bash
modules/programs/ai/dev/run-smoke.sh
```

Live/project audit:

```bash
modules/programs/ai/dev/audit-ai-project.sh --verbose
```

Compile all Python files:

```bash
nix shell nixpkgs#python3 -c python3 -m compileall -q modules/programs/ai
```

When running scripts directly, make the shared Python library importable:

```bash
PYTHONPATH=/home/daniil/NixOS/modules/programs/ai/python   python3 modules/programs/ai/path/to/script.py
```

## Queue semantics

File inboxes are queues, not shared mutable state.

Queue readers must:

1. process only complete non-hidden `.json` files;
2. ignore dotfiles, editor/sync temp files, backup files, partial files, and non-JSON files;
3. wait for file stability when reading live queues unless all writers are proven atomic;
4. drain all ready files on each activation;
5. treat systemd path activation only as a wakeup signal;
6. archive raw files to processed, failed, or manual-review directories.

Use `ai_system.queue.list_stable_json_queue_files` for queue readers. Do not hand-roll `glob("*.json")` for live inboxes unless the reason is documented.

## Canonical Obsidian queues

The canonical Obsidian inbox paths are:

```text
AI/inbox/obsidian/messages/*.json
AI/inbox/obsidian/actions/*.json
```

Legacy references to `AI/inbox/from-obsidian/...` should be removed or explicitly marked as historical.

## Action safety

Anything that can trigger user-visible or system-visible side effects must pass through the action/proposal safety boundary.

Rules:

* Obsidian planning writes reviewable proposals only.
* Proposal approval writes reviewed artifacts only.
* Live actions go through `AI/inbox/actions`.
* The action bridge writes a durable journal before side effects.
* Duplicate processed action ids must not repeat side effects.
* Stale `processing` journals must go to manual review, not replay.

To retry a manual-review action, inspect the archived file and create a new action with a new `action_id` or `idempotency_key`. Never move the same raw file back into `AI/inbox/actions`.

## Adaptive personal model rules

Personalization must not become opaque or manipulative.

Use these distinctions:

* approved facts: explicit user-provided or confirmed information;
* inferred patterns: confidence-scored hypotheses backed by local evidence;
* policies: behavior-changing rules for nudging, scheduling, suppression, adaptation, and review;
* goals: desired outcomes, habits, projects, recovery targets, and maintenance baselines;
* interventions: nudges, questions, plans, reviews, and fallback suggestions;
* outcomes: acted, ignored, snoozed, dismissed, quick-exit, sustained, fallback accepted, completed, or corrected.

Learning modules may automatically adjust timing, tone, channel, frequency, fallback choice, planning strategy, and question style when evidence supports it. They should require a proposal or confirmation for durable commitments, external writes, increased pressure, disabling important goals, or enabling new executors/services.

Store behavior patterns, not identity judgments. Prefer "late Anki nudges have low response" over "user is undisciplined at night".

## Live state

The live vault under `AI/` contains queues, state, outboxes, logs, and archives. Tests must use temporary directories and must not mutate the live vault.

Status files are materialized views. They may be stale if the corresponding service/timer is disabled or not installed. Prefer dev scripts that show unit state next to status files.

## Formatting and commits

Avoid mixing behavior changes with large formatting-only changes. Run formatters only on files intentionally touched for the change. If a broad formatting pass is useful, commit it separately.

Before committing behavior changes:

```bash
git diff --stat
git diff --check
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/audit-ai-project.sh --verbose
```

## Systemd hardening approach

Add hardening incrementally and per service. Start with low-risk guardrails such as `NoNewPrivileges`, `PrivateTmp`, and resource limits after live queue behavior is verified. Do not enable `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths`, or syscall filters until each service has an explicit read/write path inventory.
