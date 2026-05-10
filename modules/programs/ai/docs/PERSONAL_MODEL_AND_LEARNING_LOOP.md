# Personal model and learning loop
## Goal

Define how the local AI companion learns safely and usefully from evidence without becoming opaque or overbearing.

## Current state from code

The current context provider result has:

- `schema_version`
- `name`
- `available`
- `freshness`
- `facts`
- `signals`
- `warnings`
- `source_paths`

This is good plumbing, but it is not a personal model. It lacks confidence, evidence count, correction links, expiry, user-confirmation status, contradiction state, and policy/actionability metadata.

The intervention outcome summarizer classifies outcomes from append-only evidence and explicitly does not mutate policy. This is a good boundary. It should become the input to learning proposals, not an automatic policy writer.

## Target learning loop

```text
observation
-> normalized evidence
-> inferred hypothesis
-> proposal or question
-> user feedback/correction
-> bounded policy experiment
-> outcome summary
-> hypothesis revision or supersession
```

## Core entities

### approved_fact

A user-confirmed or explicitly provided fact.

Required fields:

- `fact_id`
- `statement`
- `source`
- `confirmed_by_user: true`
- `created_at`
- `last_reviewed_at`
- `expiry: optional`
- `superseded_by: optional`

Examples:

- User says Anki should stay low-pressure on Sundays.
- User confirms morning language review works better than evening.

### inferred_pattern

A hypothesis derived from observed evidence.

Required fields:

- `pattern_id`
- `hypothesis`
- `confidence`
- `evidence_refs`
- `negative_evidence_refs`
- `scope`
- `created_at`
- `expires_at`
- `review_status: proposed|accepted|rejected|superseded`
- `correction_refs`

Example:

- The user often snoozes Anki nudges after 21:00.

### policy

A behavior-changing rule. Policies should be reviewable and reversible.

Required fields:

- `policy_id`
- `scope`
- `rule`
- `authority: suggested|manual|automatic_low_risk`
- `source_evidence_refs`
- `created_at`
- `expires_at`
- `rollback_plan`

Example:

- Do not show Anki recovery nudges after 21:00 unless user explicitly asks.

### experiment

A bounded test of a policy or intervention strategy.

Required fields:

- `experiment_id`
- `hypothesis_ref`
- `policy_ref`
- `start_at`
- `end_at`
- `decision_points`
- `intervention_options`
- `success_metrics`
- `burden_metrics`
- `stop_rules`

### correction

A user-provided change to model belief or behavior.

Required fields:

- `correction_id`
- `target_ref`
- `correction_type`
- `user_text`
- `effect`
- `created_at`

Correction types:

- `wrong_inference`
- `less_like_this`
- `more_like_this`
- `not_now`
- `never`
- `felt_pressuring`
- `helpful`
- `showed_stale_context`

## Learning invariants

1. No inferred pattern becomes a durable policy without explicit rules.
2. Every adaptive policy has evidence refs and an expiry/review date.
3. Every user correction supersedes lower-confidence inferred patterns.
4. Silence/defer can be a successful intervention.
5. The system must be able to explain why it interrupted or stayed quiet.
6. Learning should start as summaries and proposals, not automatic mutation.

## Proposed files later

Do not create these immediately unless the docs patch is accepted. Proposed future vault paths:

```text
AI/model/approved-facts/*.json
AI/model/inferred-patterns/*.json
AI/model/policies/*.json
AI/model/experiments/*.json
AI/model/corrections/*.json
AI/model/reviews/YYYY-MM-DD.md
```

## Implementation sequence

1. Document schemas only.
2. Add read-only reporting from existing events into candidate hypotheses.
3. Add controls that create correction events.
4. Add product evals for inference and correction.
5. Add optional planner metadata fields.
6. Allow low-risk, expiring policy proposals.
7. Only later allow automatic low-risk adaptation.
