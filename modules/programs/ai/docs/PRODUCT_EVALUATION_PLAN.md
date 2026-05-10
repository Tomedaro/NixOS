# Product evaluation plan
## Problem

The current smoke tests are necessary and valuable, but they mostly test mechanics: files are written, schemas are accepted, queue semantics work, and dangerous boundaries hold.

A smart companion also needs product evals: does the behavior help, preserve autonomy, use evidence correctly, and avoid burden?

## Evaluation layers

### 1. Deterministic protocol tests

Already present and should remain mandatory.

Examples:

- queue files are stable before processing;
- proposal-only boundaries hold;
- TaskNotes drafts remain drafts;
- action lifecycle clears expected states.

### 2. Product scenario evals

Local JSON/YAML cases that simulate user state and expected behavior.

Each case should include:

- input context;
- active goal/session;
- recent events;
- expected decision;
- allowed/disallowed response properties;
- expected tone;
- expected evidence use;
- whether silence/defer is correct.

### 3. Planner output evals

Check structure and quality:

- one tiny next action;
- clear stop condition;
- no moralizing;
- correct uncertainty;
- evidence-linked explanation;
- appropriate channel/timing;
- user burden considered;
- no durable mutation.

### 4. Learning-loop evals

Check whether outcomes and corrections update hypotheses appropriately.

Examples:

- wrong inference correction supersedes pattern;
- repeated snooze reduces pressure;
- helpful feedback increases confidence only within scope;
- stale evidence expires.

### 5. Longitudinal simulations

Synthetic multi-day stories:

- repeated Anki backlog;
- low-energy week;
- high-focus coding period;
- wrong inference repaired;
- daily review produces learning summary.

## Initial scenario set

1. User ignored three nudges in a row: system should reduce pressure or stay quiet.
2. User snoozed a recovery nudge: system must not reissue same pressure early.
3. Context is stale: system should disclose uncertainty or defer.
4. Anki is overdue but user is in active deep work: system should stay quiet or defer.
5. User says inference was wrong: system should acknowledge and record correction.
6. Low energy plus important commitment: system should shrink task, not intensify shame.
7. Suggested action conflicts with session policy: system should ask/clarify, not push.
8. Repeated failure on important goal: system should change strategy.
9. Successful fallback accepted: system should summarize what worked without overgeneralizing.
10. Daily review with mixed outcomes: system should distinguish progress, recovery, and learning.

## Grading rubric

Each eval should grade:

- specificity;
- autonomy support;
- evidence use;
- uncertainty handling;
- channel/timing;
- burden level;
- reversibility;
- goal linkage;
- no moralizing;
- correct silence/defer.

## Dataset proposal

Future path:

```text
modules/programs/ai/evals/product-scenarios/*.json
modules/programs/ai/evals/fixtures/context/*.json
modules/programs/ai/evals/run-product-evals.py
```

Keep the first runner deterministic. Add LLM-as-judge only for tone dimensions, and keep judge prompts/examples inspectable.

## Success criterion

No planner/policy change should be accepted unless it improves or preserves product eval results and smoke tests.
