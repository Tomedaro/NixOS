# Roadmap

This file records dependency-ordered future work. It does not claim implementation and does not assign dates.

ADR 0008 resolves the architecture gate for the first product loop. The immediate roadmap is therefore deliberately narrow: prove a laptop-first Tasker-triggered task-initiation loop before expanding into general planning, broader automation, or durable commitment mutation.

## Continuing invariants

These are not roadmap features; they must remain true during every future change:

- LLM/model paths remain proposal-side.
- Ordinary software owns lifecycle, authority, queues, validation, and side effects.
- Direct TaskNotes mutation remains disabled until a deterministic reviewed apply path is complete.
- Default-off `recovery.target.start` regression coverage remains intact.
- Dangerous authority is represented by explicit capabilities and gates, not prompt wording alone.
- Remote model context is allowlisted, bounded, provenance-aware, and selected by code.
- Ambiguous replay, conflict, or stale work moves to refusal/expiry/manual review rather than repeated side effects.
- Product usefulness and user burden are evaluated separately from mechanical correctness.

## Accepted baseline - ADR 0008

The first loop is:

```text
known task
  -> Tasker Stuck trigger
  -> laptop kernel
  -> bounded blocker/next-action proposal
  -> Start / Shrink / Blocked / Defer
  -> outcome
```

Accepted boundaries:

- laptop-hosted deterministic kernel;
- Tasker as the first required adapter;
- one API provider behind a narrow adapter;
- SQLite-scale persistence is sufficient initially;
- requests are queued during laptop/API unavailability and expire when stale;
- context starts with an explicit allowlist;
- the newer Obsidian proposal chain is canonical for future durable proposals;
- real TaskNotes apply is deferred and not on the first-loop critical path;
- the older Ollama planner is legacy/specialist rather than the canonical kernel.

## Milestone 1 - freeze boundary contracts, defer internal records

Status: implementation candidate under review. Validators and smoke tests exist, but the contract set is not frozen until external message schemas are separated from kernel-internal records and the corrected invariants are accepted.

Define five stable boundary contract candidates:

- `task_initiation_stuck.v1` — Tasker ingress event with inline TaskRef, zero client expiry/idempotency;
- `task_initiation_card.v1` — immutable display/countdown authorization with kernel-issued IDs and server expiry;
- `task_initiation_response.v1` — minimal user action evidence; accepted before Receipt, first-response-wins;
- `task_initiation_context.v1` — local disclosure/audit manifest with a derived minimal API payload;
- `task_initiation_proposal.v1` — semantic-only blocker and tiny-start output.

Document as provisional (not in frozen set):

- `task_initiation_card_receipt.v1` — Tasker notification-posted evidence; exact shape validated by live test in Milestone 3.

Document as deferred (not implemented):

- Outcome evidence, metrics, and identifiers — designed and frozen only in Milestone 5 when all evidence producers exist.

Keep one private unversioned InteractionAggregate with pure reducer functions covering server expiry, idempotency, first-response-wins, Response-before-Receipt ordering, delivery-evidence branches, revision limits, and terminal immutability. Keep all orchestration/persistence records (error, idempotency, interaction, run, queue, revision, transition) as private data without schema_version.

Define task resolution as explicit task ID, then active session task, then short user description (no fallback from invalid explicit reference to description). Define which existing protocol paths are reused and which new paths are necessary before writing runtime code.

Exit condition: five boundary contracts have exact owners, authority rules, and validators; task resolution, private lifecycle, idempotency, expiry, Response-before-Receipt ordering, and TaskNotes safety are executable as pure tests; Receipt and Outcome are explicitly assigned forward to Milestones 3 and 5.

## Milestone 2 - establish the laptop kernel skeleton

Implement the smallest deterministic runtime capable of:

- authenticated event ingress;
- schema validation and deduplication;
- SQLite-backed interaction/run state;
- expiry and supersession;
- deterministic route selection;
- explicit no-model handlers for button responses;
- structured logs linking event, run, card, response, and outcome;
- restart-safe processing without duplicate consequences.

Do not add general autonomous tool loops, multi-agent orchestration, or durable-workflow frameworks.

Exit condition: a synthetic `Stuck` event can travel through a restart-safe deterministic lifecycle without calling a model.

## Milestone 3 - add the Tasker transport and queue

Implement one Tasker entry point and one response surface:

- a `Stuck` widget/action;
- authenticated delivery to the laptop over an approved private transport;
- local Tasker queue when the laptop is unreachable;
- visible queued/cancelled/expired states;
- bounded retry with stable event IDs;
- notification card rendering with `Start`, `Shrink`, `Blocked`, and `Defer`.

Finalize the provisional `task_initiation_card_receipt.v1` shape after a live test verifies whether Tasker can reliably emit and replay `posted_at_epoch`, and whether Receipt needs device/notification-instance identity. Validate that the bounded Tasker countdown has no prohibited side effects (no TaskNotes write, no action.v1 emission, no session/recovery mutation, no app/URI launch).

Exit condition: phone-to-laptop delivery, offline queueing, replay protection, expiry, cancellation, and button callbacks pass live tests on the target devices; Receipt shape is frozen or posting-anchored metrics are explicitly abandoned; bounded countdown is proven safe.

## Milestone 4 - add bounded context and one API model worker

Implement:

- a narrow provider interface with one configured API provider;
- local secret ownership;
- schema-enforced model output;
- request, token, latency, retry, and estimated-cost budgets;
- an allowlisted context builder using only the current task/description, allowed project summary, last session capsule, recent outcomes, and explicitly helper-accessible material;
- no whole-vault browsing by the model;
- API-unavailable queueing with expiry and supersession;
- deterministic fallback behavior for invalid or unsafe model output.

The worker may classify the initiation barrier and propose one tiny starting action. It may not choose a different task, create a durable commitment, or execute external actions.

Exit condition: recorded test cases produce schema-valid, bounded, relevant proposals without unauthorized context or authority expansion.

## Milestone 5 - complete the interaction and outcome loop

Connect proposals to Tasker action cards and record:

- card shown time;
- selected button;
- time to `Start`;
- repeated `Shrink`/`Blocked` paths;
- proposed micro-action completion or ten-minute engagement;
- dismissals, wrong-task reports, latency, retries, expiry, and annoyance feedback;
- occasional subjective “made starting easier” feedback.

Design and freeze `task_initiation_outcome.v1` only after the evidence producers listed above are implemented and live-tested: user action evidence, system terminal status/reason, delivery evidence, observation evidence, and feedback evidence. Define the four latency formulas using available timestamps; return unknown when ordering is contradictory or a required timestamp is absent.

Repeated dismissal must not produce identical escalating prompts. A changed task must stale the old card.

Exit condition: one run can be traced from Tasker trigger through context/model evidence to card, response, and later outcome; Outcome schema is frozen after evidence producers, precedence, finalization, and retention policy are proven.

## Milestone 6 - run a bounded real-use trial

Use the first loop in ordinary work for a predefined trial period, initially two weeks, without adding unrelated features during the evaluation window.

Primary measures:

- start within ten minutes;
- meaningful engagement or micro-action completion;
- subjective reduction in starting friction.

Guardrails:

- annoyance/dismissal rate;
- wrong-task rate;
- repeated shrinking;
- stale or late queued cards;
- privacy corrections;
- API latency and cost.

Exit condition: evidence supports one of three explicit decisions: retain and refine, redesign and repeat, or stop the loop.

## Milestone 7 - consolidate only after evidence

If the loop is retained:

- make the new kernel the documented owner of this lifecycle;
- adapt or retire overlapping older planner paths;
- update `CURRENT_STATE.md`, `ARCHITECTURE.md`, `PROTOCOLS.md`, `MODULES.md`, and `docs/SCHEMA_REGISTRY.md` to implementation truth;
- decide whether other loops should reuse the kernel;
- decide whether the Ollama planner has a justified fallback/specialist role;
- decide whether broader context, a second provider, or longer-lived workflow machinery is justified.

Real TaskNotes apply remains a separate decision and should be implemented only for a product loop that genuinely requires durable commitment mutation.

## Later capabilities - explicitly outside the first sequence

- task selection and daily prioritization;
- low-energy and stale-task loops;
- broad coaching or personal-policy adaptation;
- desktop and Obsidian command interfaces beyond review;
- calendar, distraction-control, or body-doubling adapters;
- multi-provider routing;
- MCP or general agent harnesses;
- long-running distributed workflow engines;
- automatic TaskNotes apply.
