# Safety model

## Core invariant

LLM-facing paths may read, classify, summarize, propose, and draft. They must not silently create, edit, archive, delete, launch, execute, or mutate durable commitments.

## Surfaces

| Surface | Role | Intended authority |
| --- | --- | --- |
| AI vault | Protocol, state, queue, event, and evidence layer | Local state and review artifacts |
| Obsidian | Review and interaction surface | Human-visible review, approval, drafts |
| TaskNotes | Durable human commitment surface | Human commitments only; AI mutation must be explicit and gated |
| LLM/planner | Proposal generation | No direct execution |
| Action bridge | Live action executor/gate | Bounded action processing, idempotency, journaling |
| Phone/dialog surfaces | Interaction inputs/outputs | Bounded messages/intents, not broad execution |

## Authority levels today

The current implementation still contains numeric authority levels. This is adequate for a prototype but too coarse for the long-term design.

Future work should move toward named capabilities such as:

- `interaction.answer_question`
- `interaction.dismiss_question`
- `session.start`
- `session.stop`
- `recovery.propose`
- `tasknotes.promote_legacy`
- `tasknotes.apply_reviewed_draft`

Dangerous capabilities should default off.

## Real TaskNotes mutation paths

The following are known real TaskNotes writers and must be treated as legacy/direct until consolidated:

1. `action-bridge promote_task_proposal`
   - writes a TaskNotes target only when elevated action authority and explicit legacy TaskNotes promotion opt-in both permit;
   - should be disabled/hard-gated in a later behavior patch.
2. `anki-bridge taskNoteMode = "direct"`
   - writes/updates a direct recovery TaskNote;
   - default should remain safer `propose` behavior;
   - direct mode should be deprecated.

## Obsidian and LLM boundary

Obsidian and LLM-facing modules should produce reviewable artifacts:

- messages;
- proposed actions;
- approved proposal artifacts;
- task drafts;
- summaries;
- context views.

They should not write directly to live action queues or real TaskNotes unless a future deterministic apply gate explicitly authorizes it.

## Action replay and idempotency

Live actions must be idempotent. Action files should include stable IDs or be journaled so replay does not repeat side effects.

## JSONL/event caveat

JSONL event logs are currently useful evidence. They should not be documented as authoritative audit logs until append atomicity, fsync behavior, writer locking, recovery, and tamper-evidence are specified and tested.

## Attention and recovery safety

The companion should be friendly and recovery-oriented:

- no shame language;
- no punitive framing;
- no nag loops;
- quiet hours and low-energy modes should be respected;
- silence should be a valid intervention;
- users should be able to say: wrong inference, less like this, not now, never, this helped, explain why.

## Dangerous or legacy paths

- `promote_task_proposal` real TaskNotes mutation now requires both elevated action authority and explicit legacy TaskNotes promotion opt-in.
- `anki-bridge direct` real TaskNotes mutation.
- Legacy Obsidian paths such as `AI/inbox/from-obsidian` should remain marked legacy if mentioned.
- Any future desktop popup or automation that executes without review must be treated as high risk until explicitly modeled.
