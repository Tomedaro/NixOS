# AI System Debug / Refactoring / Cleanup TODO

This file tracks safety, cleanup, and refactoring work that should stay separate from feature phases in `TODO.md`.

Treat this as a working checklist, not as source of truth. Current code, current diffs, and fresh diagnostics override this file.

## Current checkpoint

Phase 1.5 stabilization: Obsidian-first protocol pieces exist, phone/action queue semantics are hardened, durable action journaling exists, and Obsidian queue readers use shared complete-file filtering.

Before moving deeper into TaskNotes-heavy Phase 2, keep tightening contracts and diagnostics.

## Immediate before Phase 2

- [ ] Verify a live rebuild/switch has activated the committed service definitions.
- [ ] Confirm `AI/inbox/actions-manual-review/` exists after `ai-vault-init.service`.
- [ ] Confirm `AI/inbox/obsidian/messages/`, `AI/inbox/obsidian/actions/`, and `AI/outbox/to-obsidian/` exist after `ai-vault-init.service`.
- [ ] Run `modules/programs/ai/dev/check-ai-live.sh`.
- [ ] Run `modules/programs/ai/dev/audit-ai-project.sh --verbose`.
- [ ] Run `modules/programs/ai/dev/run-smoke.sh`.
- [ ] Keep `AI/inbox/from-obsidian/...` references removed or explicitly marked historical.
- [ ] Decide whether Obsidian inbox readers need a nonzero stability delay, or whether all Obsidian writers are guaranteed atomic.
- [ ] Update `TODO.md` Phase 1 status so completed Obsidian proposal/action/draft pieces are not treated as missing.
- [ ] Decide and document the owner of phone interaction projection freshness: planner opportunistic cleanup, client TTL, or deterministic projection maintainer.
- [ ] Add a deterministic non-LLM projection-refresh path if planner cadence is not enough.

## Near-term cleanup

- [ ] Add direct smoke coverage for `ai_system.queue.is_complete_json_queue_file`.
- [ ] Split `audit-ai-project.sh` output into hard failures, warnings, and informational live observations.
- [ ] Add manual-review queue summary fields: count, newest reason, newest path, and retry guidance.
- [ ] Add status freshness language to service docs: status files are materialized views, not proof a producer is currently active.
- [ ] Review `anki-bridge` direct TaskNotes mode; keep default behavior conservative until TaskNotes write schemas and gates are stronger.
- [ ] Reduce hardcoded personal paths in docs where a config variable would communicate better.

## Projection/cache freshness inventory

Materialized files are caches/views. They are useful runtime surfaces, but they are not the durable source of truth.

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
- [ ] If adding a maintainer, implement pure projection logic first, then a dry-run CLI, then an explicit `--write` mode.
- [ ] Ensure phone/webview consumers can distinguish active, inactive, expired, and unknown state.
- [ ] Avoid enabling more autonomous recovery nudges until stale materialized interaction behavior is boring and obvious.

## Systemd hardening prerequisites

- [ ] Inventory each user service: long-running vs oneshot, read paths, write paths, network needs, subprocess needs.
- [ ] Apply low-risk guardrails first: `NoNewPrivileges`, `PrivateTmp`, `TasksMax`, `MemoryMax`.
- [ ] Verify each service with `systemctl --user status`, `journalctl --user-unit`, smoke tests, and live queue checks.
- [ ] Only later consider `ProtectSystem`, `ProtectHome`, `ReadWritePaths`, `PrivateDevices`, `SystemCallFilter`, and address-family restrictions.

## Later backlog

- [ ] Consider a small shared Nix helper for Python wrapper scripts so `PYTHONPATH` handling is uniform.
- [ ] Consider a package-style Python layout only if direct-script import friction grows.
- [ ] Add replay fixtures for proposal/gate/intervention decisions.
- [ ] Add property-style queue filename tests.
- [ ] Add JSON Schema only after schemas stabilize through actual use.
- [ ] Consider a small operator CLI only after dev scripts stop being sufficient.
