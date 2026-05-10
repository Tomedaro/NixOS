# Goals and commitments
## Problem

The project distinguishes goals, TaskNotes, sessions, interventions, and outcomes, but there is not yet a canonical goal/commitment model.

Without this, the assistant can make locally useful suggestions while failing to answer deeper questions:

- Which goal is this serving?
- Is this a real human commitment or only an AI suggestion?
- Did this intervention advance the goal, reduce load, or merely create noise?
- Is the system preserving long-term priorities or optimizing short-term reactivity?

## Principle

TaskNotes remains the durable human commitment surface. The AI vault may represent goals and learning state, but it must not silently convert inferred goals into commitments.

## Proposed hierarchy

```text
values / life areas
-> goals
-> projects / habits / maintenance baselines
-> commitments / TaskNotes
-> sessions
-> interventions
-> outcomes
-> learning summaries
```

## Entity distinctions

### Goal

A desired outcome or direction. Goals may be explicit, inferred, or proposed, but only explicit/reviewed goals should guide durable commitments.

Suggested fields:

- `goal_id`
- `title`
- `area`
- `status`
- `source: user|tasknotes|obsidian|inferred_candidate`
- `confidence`
- `review_status`
- `evidence_refs`
- `tasknote_refs`
- `policy_refs`

### Commitment

A human-facing durable commitment, normally represented in TaskNotes. The AI may draft or propose, but not silently create commitment state.

Suggested fields/provenance:

- `task_id`
- `source_proposal_id`
- `source_intent_id`
- `goal_id`
- `ai_created`
- `reviewed_by_user`

### Session

A bounded current work/recovery context that compiles a temporary policy.

Current session-manager already provides a strong seed: mode, task, project, duration, allowed/distracting apps/domains, proof type, reflection questions, intervention level, and cooldown.

### Intervention

A nudge, question, plan, draft, review, fallback suggestion, or silence/defer decision linked to a goal/commitment when possible.

### Outcome

Evidence about what happened after an intervention. Outcome should not be confused with goal progress unless linked to a goal and evaluated.

## Key rule

Every proposed task, nudge, or recovery action should be classified as one of:

- `linked_to_goal`
- `linked_to_commitment`
- `maintenance_or_recovery`
- `clarification_needed`
- `unlinked`

Unlinked interventions should be low pressure and should often ask for clarification rather than escalate.

## Implementation sequence

1. Add docs and glossary definitions.
2. Add optional `goal_id`, `commitment_ref`, and `link_quality` to planner and intervention schemas.
3. Add evals for goal mismatch and unlinked nudges.
4. Add read-only goal context provider.
5. Add reviewable goal candidate proposals.
6. Only later add policy learning over goals.
