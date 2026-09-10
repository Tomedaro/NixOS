# Decisions

## 2026-05-18 - Keep LLM workflow files inside the AI module

Status: accepted

Decision:
Keep project-specific LLM workflow files under `modules/programs/ai`.

Why:
The repository is a NixOS/dotfiles repo, while the AI companion project is only one module inside it. Root-level workflow files would imply that the LLM workflow applies to the whole repo.

Consequences:
- `AGENTS.md` lives at `modules/programs/ai/AGENTS.md`.
- Workflow memory lives under `modules/programs/ai/workflow/`.
- LLM helper scripts live under `modules/programs/ai/dev/llm/`.
- ChatGPT bundles are generated under `modules/programs/ai/chatgpt-bundles/`.

## 2026-05-18 - Use a minimal four-chat workflow

Status: accepted

Decision:
Use four recurring ChatGPT chats:
- `00 Research and Design`
- `01 Implementation`
- `02 Verification and Debugging`
- `03 Release and Retrospective`

Why:
Eight chat types are too much process for a solo developer at day one. Four chats preserve the important boundaries without creating workflow drag.

Consequences:
- Research and architecture share one chat.
- Patch planning and patch creation share one chat.
- Verification and debugging share one chat.
- Final review, handoff, and retrospective share one chat.

## 2026-05-18 - Keep LLMs proposal-side

Status: accepted

Decision:
LLMs may plan, draft, review, and debug, but local checks and human review decide whether work is accepted.

Why:
This matches the project architecture: local-first, inspectable, bounded, and recovery-oriented.

Consequences:
- No patch is considered done until it is applied locally and verified.
- The LLM must not claim implementation success without local evidence.
- Local scripts are the judge for repeatable checks.

## 2026-07-22 - Use a laptop-first task-initiation kernel

Status: accepted

Decision:
Implement the first complete product loop as a Tasker-triggered intervention for an already-known task that the user cannot begin. A deterministic laptop-side kernel owns lifecycle, state, queueing, context selection, validation, and outcomes. One remote API provider supplies bounded proposal-side reasoning behind a narrow adapter.

Why:
Task initiation is a narrower and more testable problem than general prioritization. Laptop-first operation fits the available hardware and current setup. Deterministic ownership preserves the repository's proposal-only, inspectable, and gated architecture.

Consequences:
- Tasker is the first required interface.
- Remote context starts allowlisted; the model does not browse the whole vault.
- Offline/unavailable work is queued with expiry and idempotency.
- Durable task/note/calendar/external mutations still require approval.
- Real TaskNotes apply is not required for this loop.
- The newer Obsidian proposal chain is canonical for future durable proposals.
- The current Ollama planner is not the canonical future kernel.
- Success is judged by lower starting friction and meaningful action, not schema success alone.

Canonical record:
`docs/adr/0008-laptop-task-initiation-kernel.md`

## 2026-07-23 - Narrow task-initiation contracts to five boundary candidates

Status: accepted

Decision:
Narrow the Milestone 1 candidate from 13 schemas to five stable boundary contracts: stuck, card, response, context, and proposal. A provisional card_receipt is documented but excluded from the frozen set (final shape validated in Milestone 3). Outcome is explicitly deferred to Milestone 5. Internal persistence structures (interaction, run, queue, idempotency, error, transition) are unversioned private records. The public contracts use opaque UUIDv4 correlation rather than deterministic ti-* identifiers. Server expiry and first-response-wins are authoritative.

Why:
Only the five message-boundary schemas are genuine interoperability contracts that need frozen identity before transport implementation. Internal records can remain private to the kernel's SQLite store. The narrow set preserves ADR 0008's known-task, laptop-kernel, proposal-only, TaskNotes-safe boundary while removing unnecessary public schema surface.

Consequences:
- Milestone 1 exit requires these five validators and private reducer to pass pure scenarios.
- Milestone 3 freezes the Receipt shape only after live Tasker posting-evidence tests.
- Milestone 5 freezes the Outcome shape only after producers exist.
- Corrected code/docs/tests are still required before Milestone 1 completion.

## 2026-07-23 - Use a three-table SQLite task-initiation kernel skeleton

Status: accepted

Decision:
Milestone 2 uses a synchronous reusable Python kernel plus a thin local CLI. Laptop-local XDG state is stored in standard-library SQLite with one aggregate snapshot table, one immutable message/replay-result table, and one Card-routing table. Writers use explicit `BEGIN IMMEDIATE`; initial Stuck preparation and Shrink/Blocked follow-up Card preparation each commit atomically. Ordinary Responses reconcile only their owner; all-interaction deadline advancement is explicit.

Why:
This is the smallest dependency-free design that proves restart safety, exact replay, concurrent first-response-wins, corruption refusal, and deterministic deadlines across local processes without manufacturing durable intermediate work.

Consequences:
- Context-only, Proposal-only, queued, attached-task-only, and preparing states are not durable.
- Exact replay validates its owning aggregate, reservation, result, and Card routes without mutation.
- The local placeholder worker is deterministic and makes no model call.
- Tasker transport/authentication, Receipt, model/provider work, TaskNotes mutation, Outcome/evaluation, and service wiring remain later milestones.
- Milestone 2 is not marked complete until human review.
