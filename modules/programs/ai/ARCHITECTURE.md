# Architecture

## Purpose

This subsystem is a local-first adaptive AI goal-achievement companion. It helps with recovery, reflection, planning, review, and bounded action. It should become smarter over time, but only through inspectable evidence, reviewable proposals, explicit controls, and safe gates.

## System context

```text
User
  -> Obsidian / TaskNotes / phone / desktop
  -> AI vault files
  -> local bridges, planners, context providers, and action processors
```

The AI subsystem does not replace the user's tools. It coordinates between them using local files:

- Obsidian is the primary review and interaction surface.
- TaskNotes is the durable human commitment surface.
- The AI vault is the protocol, state, queue, draft, event, and evidence layer.
- LLM/planner components generate proposals and summaries, not direct execution.
- Action execution is constrained to explicit action queues and documented handlers.

## Container view

```text
Context producers
  -> AI/state/** and AI/outbox/**

Obsidian protocol modules
  -> AI/inbox/obsidian/messages/*.json
  -> AI/inbox/obsidian/actions/*.json
  -> AI/outbox/to-obsidian/**

Planner / LLM proposal modules
  -> proposed actions, task drafts, summaries
  -> no direct live execution

Phone / dialog bridges
  -> current nudge/question surfaces
  -> bounded user responses and telemetry

Action bridge
  <- AI/inbox/actions/*.json
  -> AI/state/**
  -> live side effects only through explicit handlers

TaskNotes apply/promote path
  -> target design: deterministic reviewed apply gate
  -> current status: direct TaskNotes mutation paths are removed or disabled
  -> future work: deterministic reviewed apply gate
```

## Building blocks

### AI vault

The AI vault is the machine-readable operational layer. It contains queues, state snapshots, event logs, outbox artifacts, and reviewable drafts. It should stay human-inspectable and stable across local-first sync.

### Context hub and providers

Context providers collect read-only facts and derived facts from local sources such as session state, phone status, Anki state, interventions, and recovery state. They should not mutate commitments. Future context providers should carry evidence, freshness, confidence, and expiry.

### Obsidian protocol layer

Obsidian-facing modules are review surfaces and bounded protocol adapters. They may write message/action intent files and reviewable artifacts. They must not call shell commands, mutate TaskNotes directly, write live action queue entries, or silently execute proposals.

### Planner and LLM layer

Planner/LLM-facing code should produce structured proposals, summaries, questions, and drafts. It should include uncertainty and evidence where possible. It must not gain direct write access to durable commitments or broad live execution.

### Action bridge

The action bridge owns intentional live actions from `AI/inbox/actions/*.json`. It is responsible for validation, idempotency, journaling, and side effects. Its current numeric authority model is transitional and should evolve toward named capabilities.

### TaskNotes boundary

TaskNotes is the durable human commitment surface. The long-term model is:

```text
intent or proposal
  -> reviewable proposal artifact
  -> explicit human approval
  -> TaskNotes-compatible draft
  -> deterministic apply/promote gate
  -> atomic write to allowed TaskNotes target
  -> event and provenance record
```

Current status: direct TaskNotes mutation paths are removed or disabled. `action-bridge promote_task_proposal` is disabled, and `anki-bridge` direct TaskNotes mode is removed/hard-disabled.

## Runtime views

### Obsidian proposal flow

```text
Obsidian text/action intent
  -> AI/inbox/obsidian/messages/*.json
  -> ingress / intent planner
  -> proposal artifact
  -> AI/inbox/obsidian/actions/*.json approval/rejection/revision
  -> approved proposal artifact
  -> optional reviewable TaskNotes draft
```

This flow is strong because it produces reviewable artifacts and keeps live mutation out of the LLM-facing path.

### Phone/dialog question flow

```text
current question state
  -> phone/dialog surface
  -> answer or dismiss
  -> dialog-bridge queues AI/inbox/actions answer_question
  -> action-bridge processes answer_question/dismiss_question and owns lifecycle/state mutation
```

Current status: `dialog-bridge` queues canonical `answer_question` action files; `action-bridge` owns answer/dismiss lifecycle and state mutation.

### Live action flow

```text
user/UI writes action JSON
  -> AI/inbox/actions/*.json
  -> action bridge waits for stable file
  -> validate action and authority
  -> create/update journal
  -> execute explicit handler
  -> write result/state/event
  -> archive or manual-review failed/ambiguous actions
```

Live action replay must be conservative. A stale processing journal from a prior run should not be replayed automatically.

## Data and state principles

- Queue entries are commands or intents.
- State files are materialized current views.
- Outbox files are reviewable artifacts or surface-specific current displays.
- Events are evidence, not automatically authoritative audit records.
- Drafts are not commitments.
- TaskNotes entries are commitments and require the strongest boundary.

## Future target: inspectable learning kernel

The project should evolve toward this architecture:

```text
context providers
  -> evidence ledger
  -> personal model hypotheses
  -> proposal engine
  -> review/control surfaces
  -> bounded policy experiments
  -> outcome summaries
  -> revised hypotheses
```

The important design constraint is reversibility. The system may learn, but the user must be able to inspect evidence, correct wrong inferences, reduce pressure, forget patterns, and understand why a proposal was made.

## Quality attributes

| Attribute | Architectural implication |
| --- | --- |
| Local-first | Prefer local files, deterministic recovery, and sync-aware protocols. |
| Inspectable | Store reviewable JSON/Markdown artifacts with evidence and provenance. |
| Recovery-oriented | Optimize for humane next actions, not pressure or surveillance. |
| Safe mutation | Centralize mutation behind explicit gates and tests. |
| Future-proof | Separate current state, roadmap, protocols, and safety boundaries. |
| Learnable | Introduce personal model changes through evidence, feedback, and evals. |

## Philosophy alignment

The architecture should be read through [PHILOSOPHY.md](./PHILOSOPHY.md): the system exists to improve goal achievement through local-first context, inspectable memory, proposal-side intelligence, bounded agency, modular instruments, review surfaces, deterministic mutation gates, and outcome-driven learning.
