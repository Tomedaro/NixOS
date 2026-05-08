# AI System Debug / Refactoring / Cleanup TODO

This file is separate from `TODO.md`. It tracks safety, cleanup, architecture clarity, and refactoring work that should not be mixed with product feature phases.

## Current checkpoint

The project is in Phase 1.5/1.6 stabilization. Queue semantics, action replay safety, manual-review visibility, and Obsidian queue readers are much safer than earlier versions. Before moving deeper into TaskNotes-heavy Phase 2, the project direction must be explicit: this is an adaptive local productivity companion with inspectable learning, not merely a task writer or reminder bot.

## Immediate before Phase 2

- [ ] Rebuild/switch and verify the committed services are live.
- [ ] Confirm `AI/inbox/actions-manual-review/` exists after `ai-vault-init.service`.
- [ ] Confirm canonical Obsidian queues exist after vault init: `AI/inbox/obsidian/messages/` and `AI/inbox/obsidian/actions/`.
- [ ] Run `modules/programs/ai/dev/check-ai-live.sh` and resolve unexpected missing queue/status paths.
- [ ] Run `modules/programs/ai/dev/audit-ai-project.sh --verbose`.
- [ ] Run `modules/programs/ai/dev/run-smoke.sh`.
- [ ] Remove or explicitly mark all remaining `AI/inbox/from-obsidian/...` references as legacy.
- [ ] Keep `DEVELOPMENT.md` as the project operating guide.
- [ ] Decide whether Obsidian inbox readers should use a nonzero stability delay or whether all Obsidian writers are guaranteed atomic.
- [ ] Update `TODO.md` Phase 1 status so completed Obsidian proposal/action/draft pieces are not treated as missing.

<!-- AI-CONFIG-CENTRALIZATION:START -->

## Configuration centralization track

The project should be futureproof and adjustable from one place. The intended control surface is `modules/programs/ai/default.nix`, backed by typed submodule options.

Near-term cleanup:

* [ ] Replace one-off hardcoded paths in active Nix settings with the shared `aiDir` / `taskNotesDir` bindings.
* [ ] Add a shared timezone option and thread it through service environments.
* [ ] Inventory hardcoded runtime paths in Python and shell scripts.
* [ ] Prefer `AI_DIR`, `TASKNOTES_DIR`, `AI_TIMEZONE`, and explicit CLI flags over absolute defaults.
* [ ] Document which relative paths are protocol contracts and which are configurable implementation details.
* [ ] Do not introduce new feature modules with hidden path or policy constants.

<!-- AI-CONFIG-CENTRALIZATION:END -->

## Adaptive personal model track

- [ ] Define approved facts, inferred patterns, preferences, and capacity-state contracts.
- [ ] Define goal, goal-link, nudge-policy, scheduling-policy, suppression-rule, adaptation-policy, and experiment-policy contracts.
- [ ] Define feedback/outcome vocabulary that includes inaction: ignored, no_response, dismissed, quick_exit, sustained, fallback_accepted, corrected_inference.
- [ ] Define natural-language intent classes: immediate action, memory update, policy adjustment, durable-change proposal, reflective dialogue, unsafe request.
- [ ] Define Obsidian review surfaces for arbitrary periods: personal model review, goal review, policy review, learning review.
- [ ] Implement one narrow learning loop first, probably Anki/recovery nudge timing/frequency/fallback adaptation.
- [ ] Add correction commands: "that inference is wrong", "less like this", "more like this", "forget/supersede this pattern", "quiet mode".

## Near-term cleanup

- [ ] Add direct smoke coverage for `ai_system.queue.is_complete_json_queue_file`.
- [ ] Split `audit-ai-project.sh` output into `FAIL`, `WARN`, and `INFO` classes so expected live observations do not look like failures.
- [ ] Add manual-review queue summary fields: count, newest reason, newest path, retry instructions.
- [ ] Add status freshness language to service docs: status files are materialized views, not proof that the corresponding service is currently active.
- [ ] Review `anki-bridge` direct TaskNotes mode; keep default `propose` until TaskNotes write schemas and gates are stronger.
- [ ] Reduce hardcoded personal paths in docs/examples where a config variable would communicate better.

## Projection/cache freshness inventory

Materialized files are caches/views. They are useful runtime surfaces, but they are not the durable source of truth.

Tasks:

- [ ] Classify each materialized file by producer, consumer, freshness model, and stale-state risk.
- [ ] Start with:
  - `AI/outbox/to-phone/current-nudge.json`
  - `AI/outbox/to-phone/current-question.json`
  - `AI/outbox/to-phone/interaction-state.json`
  - `AI/state/recovery/current.json`
  - `AI/state/interventions/stats.json`
  - `AI/state/recovery-trigger/status.md`
- [ ] For each file, decide whether stale state is harmless, warning-only, or requires deterministic refresh.
- [ ] Keep diagnostics explicit about whether they are showing durable events, live service state, or materialized views.

## Interaction lifecycle cleanup

Known issue class: deterministic lifecycle logic can decide a nudge is expired before the phone-visible materialized files are cleared.

Planner output already clears stale nudges opportunistically when the planner runs. That is useful, but the planner should not become the implicit lifecycle authority.

Goals:

- [ ] Keep diagnostics showing active nudge/question id, status, source, updated time, age, consistency, and stale reason.
- [ ] Keep `check-ai-live.sh` and `audit-ai-project.sh` read-only by default.
- [ ] Decide whether stale interaction projection refresh belongs to:
  - planner opportunistic output refresh;
  - a deterministic projection maintainer;
  - client-side TTL fallback;
  - or a combination of the above.
- [ ] Keep `interaction_projection.py` dry-run by default until ownership is decided.
- [ ] If adding a maintainer, implement pure projection logic first, then a dry-run CLI, then an explicit `--write` mode.
- [ ] If projection refresh mutates live state, append a small local event such as `interaction_projection_cleared_nudge`.
- [ ] Ensure phone/webview consumers can distinguish active, inactive, expired, and unknown state.
- [ ] Avoid enabling more autonomous recovery nudges until stale materialized interaction behavior is boring and obvious.

## Systemd hardening track

- [ ] Inventory each user service: long-running vs oneshot, read paths, write paths, network needs, subprocess needs.
- [ ] Add low-risk settings first: `NoNewPrivileges`, `PrivateTmp`, `TasksMax`, `MemoryMax`.
- [ ] Verify with `systemctl --user status`, `journalctl --user-unit`, smoke tests, and live queue checks.
- [ ] Only later consider `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths`, `PrivateDevices`, and `SystemCallFilter`.

## Later backlog

- [ ] Consider a small shared Nix helper for Python wrapper scripts so `PYTHONPATH` handling is uniform.
- [ ] Consider a package-style Python layout if direct-script import friction grows.
- [ ] Add replay fixtures for proposal/gate/intervention decisions.
- [ ] Add property-style queue filename tests.
- [ ] Add JSON Schema only after schemas stabilize through actual use.
