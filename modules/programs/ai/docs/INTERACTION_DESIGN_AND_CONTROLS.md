# Interaction design and controls
## Goal

Give the user simple controls that steer the system and produce structured learning evidence.

## Current state

The project already supports actions such as acking/snoozing nudges, answering/dismissing questions, and Obsidian action/message files. The Obsidian interaction contract tells clients to write messages to `AI/inbox/obsidian/messages/*.json` and button/action responses to `AI/inbox/obsidian/actions/*.json`.

This is a good foundation, but it does not yet define the feedback vocabulary needed for a learning companion.

## Required controls

### Immediate nudge controls

- `acknowledge`
- `start`
- `snooze`
- `dismiss`
- `not_now`
- `too_much`
- `less_like_this`
- `this_helped`
- `wrong_inference`
- `show_evidence`

### Question controls

- choose option;
- free-text answer;
- dismiss;
- ask why;
- correct premise;
- do not ask this again.

### Pattern/policy controls

- accept pattern;
- reject pattern;
- edit pattern;
- expire pattern;
- make temporary;
- make permanent;
- show evidence;
- supersede with user statement.

### Task/commitment controls

- draft only;
- promote/apply after review;
- reject draft;
- link to goal;
- mark unrelated;
- reduce scope;
- schedule later;
- do not create TaskNotes from this kind of proposal.

## Event mapping

Suggested future event types:

```text
feedback_helpful
feedback_not_helpful
feedback_wrong_inference
feedback_less_like_this
feedback_more_like_this
feedback_felt_pressuring
feedback_show_evidence_requested
feedback_not_now
feedback_never_for_pattern
pattern_accepted
pattern_rejected
pattern_superseded
policy_experiment_accepted
policy_experiment_rejected
```

## Design rules

1. Every feedback control should be low-friction.
2. Feedback should be reversible or supersedable.
3. Free-text correction should be preserved but summarized into structured fields later.
4. The user should never need to inspect JSON to understand why the system acted.
5. Controls must be consistent across phone, Obsidian, and desktop surfaces where feasible.
6. The system must distinguish `not now`, `never`, `wrong`, and `too much`; these are different meanings.

## Implementation sequence

1. Document controls and event semantics.
2. Add no-op/record-only feedback actions to the action bridge.
3. Add product evals that require correct behavior after feedback.
4. Surface explanations and evidence refs in Obsidian first.
5. Add phone UI controls after semantics are stable.
