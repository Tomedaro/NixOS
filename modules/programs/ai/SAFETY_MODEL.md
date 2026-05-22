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

Current named gates default as follows:

- `ALLOW_PROOF_SUBMIT`: enabled;
- `ALLOW_RECOVERY_TARGET_START`: disabled by default;
- `ALLOW_SESSION_CHECK_IN`: enabled.

The remaining default-enabled gates are transitional, not the long-term safety target. Dangerous capabilities should eventually default off once the user-facing flow, disable behavior, and regression coverage are clear.

`submit_proof` is still dual-gated: it requires both `ALLOW_PROOF_SUBMIT=1` and `ACTION_AUTHORITY_LEVEL >= 1`. It should not be described as independent of numeric authority.

`recovery.target.start` / `ALLOW_RECOVERY_TARGET_START` is now default-off. Explicit `ALLOW_RECOVERY_TARGET_START=1` is required for successful `start_recovery_target` behavior.

### `recovery.target.start` default-off regression requirements

The default-off migration is applied. Regression coverage must continue proving all of the following:

- runtime `ALLOW_RECOVERY_TARGET_START` default remains disabled;
- Nix `allowRecoveryTargetStart` default remains `false`;
- Nix wiring still exports `ALLOW_RECOVERY_TARGET_START`;
- default `start_recovery_target` actions are rejected;
- blocked default behavior does not write recovery state;
- blocked default behavior does not append recovery events;
- blocked default behavior does not clear the originating nudge as `recovery_started`;
- explicit `ALLOW_RECOVERY_TARGET_START=1` preserves intended successful `start_recovery_target` behavior;
- `ACTION_CAPABILITY_POLICY` metadata stays consistent, including `default_enabled`;
- no live `tasknotes.promote` capability appears.

The default-off behavior must preserve reviewable proposal/draft paths and must not reintroduce direct TaskNotes mutation.

### Named capability default-off migration checklist

Before flipping any named capability default from enabled to disabled, document and prove all of the following:

- identify the named capability, canonical action, accepted aliases, gate environment variable, and Nix option;
- confirm `ACTION_CAPABILITY_POLICY` covers the canonical action;
- confirm policy metadata declares the expected capability, `gate_env`, and `default_enabled`;
- preserve explicit opt-in success behavior for the intended action path;
- flip runtime fallback and Nix option defaults together;
- preserve Nix environment wiring from the Nix option to the gate environment variable;
- update `ACTION_CAPABILITY_POLICY` metadata in the same patch as the default flip;
- prove default/no-env action requests are rejected;
- prove blocked default behavior writes no state;
- prove blocked default behavior appends no events;
- prove blocked default behavior performs no lifecycle side effects, such as clearing or completing an originating interaction;
- prove no unrelated capability defaults changed;
- prove no live `tasknotes.promote` capability appears;
- update current-state, safety, roadmap, and local bridge docs where behavior is user-visible;
- run full smoke for behavior patches.

Completed example:

- `recovery.target.start` / `start_recovery_target` / `ALLOW_RECOVERY_TARGET_START` / `allowRecoveryTargetStart` is the first completed default-off migration.
- The migration proves default/no-env `start_recovery_target` is rejected, blocked default behavior writes no recovery state/events, blocked default behavior does not clear the originating nudge as `recovery_started`, explicit `ALLOW_RECOVERY_TARGET_START=1` preserves intended successful behavior, policy metadata has `default_enabled = false`, and no live `tasknotes.promote` capability appears.

The action bridge still has a broad numeric `ACTION_AUTHORITY_LEVEL` setting. The source now keeps a small `ACTION_CAPABILITY_POLICY` registry for dispatched action capability classes. Each entry declares status, side-effect class, default-enabled state, and gate metadata where applicable so policy drift is visible before adding more gates. This is an inventory and incremental enforcement point, not a full policy engine. `recovery.target.start` is default-off; remaining enabled named gates are transitional, and disabled legacy actions remain disabled:

| Action | Capability | Current behavior | Side-effect class |
| --- | --- | --- | --- |
| `ack_nudge` | `interaction.nudge.respond` | Supported | Updates nudge/interaction state and action events. |
| `snooze_nudge` | `interaction.nudge.respond` | Supported | Updates nudge/interaction state, snooze metadata, and action events. |
| `answer_question` | `interaction.question.respond` | Supported | Records question answer state/events. |
| `dismiss_question` | `interaction.question.respond` | Supported | Records question dismissal state/events. |
| `start_session` | `session.lifecycle` | Supported | Writes session state, control files, and action/session events. |
| `end_session` | `session.lifecycle` | Supported | Writes session completion, archive/control state, and events. |
| `check_in` | `session.check_in` | Supported when `ALLOW_SESSION_CHECK_IN=1` | Writes check-in state/events and may trigger help-now planning. |
| `start_recovery_target` | `recovery.target.start` | Default-off; supported only when `ALLOW_RECOVERY_TARGET_START=1` | Writes recovery state/events and starts the configured recovery target flow. |
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
