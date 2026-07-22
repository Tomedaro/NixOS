# Review inventory

Snapshot date: 2026-07-22.

This document records the scope and limits of the repository review represented by the current canonical docs.

## Review basis

Reviewed from the uploaded archive:

- top-level canonical and design documentation;
- Nix composition and module defaults;
- service Python modules and READMEs;
- shared `python/ai_system` package;
- development and documentation-check scripts;
- all smoke-test source files;
- Obsidian proposal/operator flow;
- TaskNotes boundary and apply validator;
- action capability and replay behavior.

## Verification performed in the review environment

- Python source compilation: passed.
- Smoke-test files found: **30**.
- Smoke tests: all passed after recreating the repository path expected by helper scripts/imports.
- Documentation link/drift checks: passed in reconstructed repository layout.

## Verification not performed

- Nix evaluation or flake checks;
- NixOS/Home Manager rebuild;
- actual systemd units/timers;
- live AI vault ownership and permissions;
- real Tasker/phone payloads;
- desktop notification behavior;
- live Ollama inference or model quality;
- remote API-provider integration;
- real TaskNotes mutation, because no apply writer exists;
- long-term product usefulness.

## Current module inventory

### Composition and configuration

- `default.nix`
- `core`
- `vault-bridge`
- `compat`
- `ollama`
- optional/stub integration modules

### Live services and bridges

- `action-bridge`
- `phone-bridge`
- `dialog-bridge`
- `session-manager`
- `coach-daemon`
- `recovery-manager`
- `recovery-trigger`
- `intervention-outcomes`
- `anki-bridge`
- `llm-planner`

### Shared kernel package

- context assembly and providers;
- interaction lifecycle and projection;
- intervention and outcome records;
- Obsidian contracts, ingress, planning, approval, and drafts;
- LLM proposal contract;
- recovery proposals and gate;
- TaskNotes apply validator;
- IO, queue, event, status, and time helpers.

### Development and surfaces

- smoke and live diagnostic scripts;
- Obsidian operator loop;
- development interaction surface;
- phone webview assets/installer;
- documentation/patch checks.

See `MODULES.md` and `docs/MODULE_REVIEW_REGISTER.md` for role details.

## Current live-path families

- canonical live action queue and processed/failed/manual-review archives;
- passive phone and desktop event inboxes;
- Obsidian message and review-action inboxes;
- phone/desktop/Obsidian outbox projections;
- proposal, reviewed-proposal, and task-draft histories;
- state for action processing, sessions, interactions, recovery, interventions, context, Anki, and planners;
- JSONL evidence events;
- older `AI/proposed-tasks` proposal surface;
- external `TaskNotes/` durable commitment surface with no current AI writer.

Exact orientation is in `PROTOCOLS.md`; versioned contracts are in `docs/SCHEMA_REGISTRY.md`.

## Side-effect classes observed

### Read/derive

Context providers, schema helpers, lifecycle decisions, validators, statistics, and proposal normalization.

### Local protocol/state mutation

Queue moves, atomic state/projection files, reports, reviewed artifacts, drafts, session/control files, and evidence events.

### Live local action

Explicit `action-bridge` handlers for interaction responses, session lifecycle, check-ins, recovery target start when opted in, and proof submission when gated.

### Durable TaskNotes mutation

None in current active AI paths. Legacy promotion is disabled and Anki direct mode is removed/hard-disabled.

## Review conclusion

The archive is technically coherent enough for dependency-based planning. Remaining uncertainty is concentrated in canonical orchestration, model-provider direction, proposal consolidation, TaskNotes apply timing, and product-loop selection rather than in an obvious undiscovered direct mutation path.
