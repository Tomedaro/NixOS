# Current state

Snapshot date: 2026-07-23.

This file records what is true in the repository now. It separates implemented behavior, partial behavior, runtime defaults, unresolved architecture, and planned work. Code and tests remain authoritative when this file drifts.

## Repository verification represented by this snapshot

The archived repository was reviewed as source code and documentation:

- all Python sources compiled successfully in the review environment;
- all 31 `tests/*_smoke.py` files passed after recreating the repository path expected by the test helpers;
- documentation link/drift checks passed in the reconstructed repository layout;
- no Nix evaluation, NixOS rebuild, systemd service run, live vault mutation, Tasker interaction, Ollama inference, or remote API call was verified in that environment.

Passing smoke tests prove important protocol mechanics. They do not yet prove usefulness in daily life or correctness on the target machine.

## Implemented now

### Safety and authority

- `action-bridge` processes the canonical live action queue with validation, stable-file checks, idempotency records, processing journals, explicit handlers, and conservative replay behavior.
- `ACTION_CAPABILITY_POLICY` inventories named action capabilities alongside the transitional numeric authority level.
- `recovery.target.start` is the first completed default-off named capability migration and requires explicit opt-in.
- `promote_task_proposal` / `promote_proposal` are disabled legacy actions and do not write real TaskNotes.
- Anki task output supports `off` and `propose`; raw legacy direct mode falls back to proposal behavior.

### Obsidian and proposal boundary

- Obsidian ingress, intent planning, proposal actions, approval bridging, reviewed proposal artifacts, and TaskNotes-compatible draft generation are implemented.
- `llm_proposal_contract` rejects direct-execution fields and produces schema-bound proposal packages.
- The current reviewed TaskNotes path reaches deterministic validation:

```text
intent
  -> proposal
  -> explicit decision
  -> reviewed proposal
  -> TaskNotes-compatible draft
  -> deterministic dry-run validation
```

- `tasknotes_apply_validator` verifies approval identity, schemas, forbidden fields, target safety, collisions, and idempotency inputs.
- The final atomic write into real TaskNotes is not implemented.

### Context, interaction, recovery, and outcomes

- `agent_context` and `context_providers` build bounded read-only context snapshots.
- `tasknotes.read_context` is implemented with provenance, freshness, limits, safe-off behavior, and prompt-boundary omission of raw content and absolute roots.
- Interaction lifecycle and projection helpers model active nudges, questions, expiry, clear reasons, and phone interaction state.
- Recovery proposal construction and deterministic proposal gating are implemented.
- Intervention event records, outcome summaries, statistics, and an outcome reporter exist.
- Phone, dialog, session, coach, recovery, intervention, Anki, vault, and planner services/modules exist, with several automatic triggers intentionally disabled.

### Development and verification

- The repository contains 31 smoke-test files covering action processing, context, Obsidian contracts, proposal gates, interaction lifecycle/projection, recovery, sessions, phone/desktop behavior, TaskNotes validation, and planner output mechanics.
- `dev/run-obsidian-agent-loop.sh` provides an operator/development loop for exercising the Obsidian proposal chain.
- Documentation and patch verification scripts exist under `dev/llm/`.

## Effective repository defaults

The top-level Nix composition currently expresses these defaults:

- local Ollama module enabled;
- Ollama CPU package selected;
- `llm-planner` enabled but its timer disabled;
- `dialog-bridge` enabled but its timer disabled;
- `recovery-trigger` disabled;
- `intervention-outcomes` timer enabled;
- `coach-daemon`, phone bridge, Anki bridge, session manager, action bridge, and recovery manager enabled;
- action authority level remains `2` as a transitional coarse guard;
- `ALLOW_RECOVERY_TARGET_START` defaults off;
- Anki task output defaults to `propose`.

These are repository defaults, not proof of the live target-machine configuration.

## Strong current properties

- LLM-facing paths are proposal/review/draft oriented rather than silent-execution paths.
- Real TaskNotes mutation is absent from current AI execution paths.
- Atomic replacement is used for many state and protocol artifacts.
- Action replay is conservative and ambiguous/stale runs can be moved to manual review.
- Passive phone telemetry is separated from intentional action commands.
- Prompt context is bounded and provenance-aware.
- The implementation is decomposed into narrow, testable components.

## Partial or transitional behavior
- Milestone 1 task-initiation contracts are frozen (commit `a7bffe6`): five stable boundary validators (stuck, card, response, context, proposal), a documented provisional card_receipt (frozen in Milestone 3), a private pure aggregate reducer, and 249 smoke checks covering all lifecycle, ordering, and authority scenarios. Outcome evidence is documented but not implemented (deferred to Milestone 5). The laptop kernel, SQLite database, Tasker transport, provider integration, live queues, services, and real-use evaluation remain unimplemented.

- The system contains most kernel components but not one implemented canonical runtime orchestrator. ADR 0008 now fixes the intended first-loop ownership: a deterministic laptop-side kernel, while current routing remains distributed across services, scripts, queues, and Python modules.
- Named capabilities exist, but numeric action authority and several default-enabled gates remain transitional.
- TaskNotes apply validation exists; real apply, atomic mutation, conflict recovery, and authoritative apply journaling do not.
- Two proposal families still coexist in code. ADR 0008 selects the newer Obsidian proposal/approval/task-draft chain as the direction for future durable proposals and treats the older `llm-planner`/`AI/proposed-tasks` surface as legacy/specialist compatibility pending adaptation or retirement.
- Interaction and outcome records are mechanically useful, but the end-to-end personal learning loop is not canonical.
- Goal IDs and intervention references exist, but values, goals, projects/habits, commitments, sessions, interventions, and outcomes are not yet one first-class hierarchy.
- Cooldowns and TTLs exist, but a holistic attention/receptivity policy is not enforced across all producers.
- JSONL files are evidence logs, not specified crash-safe, writer-serialized, tamper-evident audit records.

## Accepted near-term architecture direction

ADR 0008 accepts a narrow first product loop and target runtime:

- the first loop addresses inability to begin an already-known task;
- Tasker is the first required interaction adapter;
- a deterministic kernel runs on the laptop and owns event lifecycle, queueing, state, validation, and outcomes;
- one remote API provider is used first behind a narrow provider interface;
- model context starts with a code-enforced allowlist rather than whole-vault retrieval;
- Tasker/laptop/API unavailability is handled through bounded queues, retries, idempotency, expiry, and supersession;
- durable tasks, note edits, calendar changes, messages, and consequential actions remain approval-gated;
- real TaskNotes apply is not required for the first loop;
- success is evaluated through start behavior, meaningful engagement, friction, and burden.

This is an accepted direction, not implemented behavior. The repository still lacks the laptop kernel, Tasker first-loop transport, remote provider adapter, allowlisted context-packet runtime, and real-use evaluation.

## Model runtime status

The implemented planner remains Ollama-specific and configured for local models. There is no provider-neutral model adapter or remote API implementation in this repository.

ADR 0008 now establishes the target direction:

- one API provider first behind a narrow adapter;
- local secret ownership;
- schema-bound outputs and deterministic validation;
- data-minimized allowlisted context;
- bounded request, token, latency, retry, expiry, and cost policies;
- no multi-provider router or general autonomous harness in the first loop;
- the old Ollama planner is not the canonical future kernel and may remain only as legacy/specialist code until deliberately adapted or retired.

## Product maturity

The repository currently proves mechanical safety and protocol behavior more strongly than product usefulness.

It does not yet establish through real-use evaluation that interventions reliably:

- reduce time to start;
- select the right next action;
- reduce felt burden or shame;
- recover gracefully after avoidance;
- improve meaningful completion rather than notification interaction alone.

## Do not assume

- Do not assume repository defaults equal the live target-machine state.
- Do not assume roadmap items are implemented.
- Do not assume smoke tests are product evaluations.
- Do not assume JSONL evidence is an authoritative audit trail.
- Do not assume the older proposal surface has already been adapted or retired; ADR 0008 settles the direction for new work, not the current implementation.
- Do not assume a remote API provider is already integrated.
- Do not assume any LLM output may directly execute actions or mutate TaskNotes.
