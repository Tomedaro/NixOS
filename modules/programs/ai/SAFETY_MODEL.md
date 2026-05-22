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
- `tasknotes.apply_reviewed_draft`

Dangerous capabilities should default off.

## Action bridge capability inventory

## Action capability authority defaults

`ACTION_AUTHORITY_LEVEL` remains a transitional coarse guard, not the primary future authority model. The emerging policy surface is named capabilities in `ACTION_CAPABILITY_POLICY`.

Current named gates remain default-enabled for compatibility:

- `ALLOW_PROOF_SUBMIT`
- `ALLOW_RECOVERY_TARGET_START`
- `ALLOW_SESSION_CHECK_IN`

This default-enabled state is transitional, not the long-term safety target. Dangerous capabilities should eventually default off once the user-facing flow, disable behavior, and regression coverage are clear.

`submit_proof` is still dual-gated: it requires both `ALLOW_PROOF_SUBMIT=1` and `ACTION_AUTHORITY_LEVEL >= 1`. It should not be described as independent of numeric authority.

The first future default-off candidate is likely `recovery.target.start` / `ALLOW_RECOVERY_TARGET_START`, because it starts a recovery target flow and is more action-like than passive interaction-state updates. Do not flip that default until a separate plan verifies user impact, recovery UX, and tests.

The action bridge still has a broad numeric `ACTION_AUTHORITY_LEVEL` setting. The source now keeps a small `ACTION_CAPABILITY_POLICY` registry for dispatched action capability classes. Each entry declares status, side-effect class, default-enabled state, and gate metadata where applicable so policy drift is visible before adding more gates. This is an inventory and incremental enforcement point, not a full policy engine. Existing named gates remain default-enabled except disabled legacy actions:

| Action | Capability | Current behavior | Side-effect class |
| --- | --- | --- | --- |
| `ack_nudge` | `interaction.nudge.respond` | Supported | Updates nudge/interaction state and action events. |
| `snooze_nudge` | `interaction.nudge.respond` | Supported | Updates nudge/interaction state, snooze metadata, and action events. |
| `answer_question` | `interaction.question.respond` | Supported | Records question answer state/events. |
| `dismiss_question` | `interaction.question.respond` | Supported | Records question dismissal state/events. |
| `start_session` | `session.lifecycle` | Supported | Writes session state, control files, and action/session events. |
| `end_session` | `session.lifecycle` | Supported | Writes session completion, archive/control state, and events. |
| `check_in` | `session.check_in` | Supported when `ALLOW_SESSION_CHECK_IN=1` | Writes check-in state/events and may trigger help-now planning. |
| `start_recovery_target` | `recovery.target.start` | Supported when `ALLOW_RECOVERY_TARGET_START=1` | Writes recovery state/events and starts the configured recovery target flow. |
| `submit_proof` | `proof.submit` | Supported when `ALLOW_PROOF_SUBMIT=1` and `ACTION_AUTHORITY_LEVEL >= 1` | Writes proof artifacts/events. |
| `promote_task_proposal` / `promote_proposal` | `disabled.legacy` | Disabled | Must fail without writing real TaskNotes. |

There is no live `tasknotes.promote` capability. Future real TaskNotes writes must wait for deterministic reviewed apply/promote.


## Real TaskNotes mutation paths

Current direct TaskNotes mutation paths are removed or disabled:

- `action-bridge promote_task_proposal` is disabled and should fail without writing TaskNotes.
- `anki-bridge` no longer supports `taskNoteMode = "direct"` in Nix config.
- Raw `TASKNOTE_MODE=direct` falls back to `propose` and does not write real TaskNotes.

Future real TaskNotes writes should go through a deterministic, explicit, reviewed apply/promote gate.

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

- `promote_task_proposal` real TaskNotes mutation is disabled.
- `anki-bridge direct` real TaskNotes mutation is removed/hard-disabled; raw `TASKNOTE_MODE=direct` falls back to `propose`.
- Legacy Obsidian paths such as `AI/inbox/from-obsidian` should remain marked legacy if mentioned.
- Any future desktop popup or automation that executes without review must be treated as high risk until explicitly modeled.
