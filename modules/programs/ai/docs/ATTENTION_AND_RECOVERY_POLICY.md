# Attention and recovery policy
## Problem

The current system has TTLs and cooldowns. That is necessary but not enough for a humane companion.

A recovery/productivity assistant must treat attention as a scarce resource and avoid becoming another source of pressure.

## Current state

- `interaction_lifecycle.py` can expire nudges and clear them after actions or terminal recovery.
- `agent_context.py` derives facts such as active nudge, active question, active recovery, recent snooze, recent terminal recovery, Anki due, and desktop verdict.
- `session_manager.py` has intervention cooldowns per mode.

## Missing policy concepts

- quiet hours;
- daily attention budget;
- repeated-ignore backoff;
- low-energy mode;
- deep-work suppression;
- channel switching;
- explainable interruption reason;
- burden accounting;
- defer/silence as a first-class outcome;
- user-specific receptivity windows;
- escalation and de-escalation rules.

## Attention policy model

### Decision inputs

- active session and policy;
- current/recent nudges and questions;
- recent snooze/dismiss/ignore;
- recent recovery terminal state;
- current desktop/app alignment;
- time of day and quiet hours;
- user energy/capacity signals;
- goal urgency and commitment status;
- burden history for the day/week;
- channel availability.

### Decision outputs

- `show_now`
- `defer_until`
- `stay_silent`
- `ask_one_question`
- `switch_channel`
- `reduce_pressure`
- `escalate_only_if_user_requested`

### Required explanation fields

Every attention decision should be able to expose:

- `why_now` or `why_silent`
- `evidence_refs`
- `burden_estimate`
- `goal_or_commitment_ref`
- `alternative_considered`
- `cooldown_or_backoff_rule`

## Backoff rules

Initial proposed rules:

1. If the user ignores two similar nudges in a window, reduce pressure or switch strategy.
2. If the user snoozes, do not reframe the same pressure as a new nudge before the snooze expires.
3. If the user dismisses, ask no more than one clarifying question before staying quiet.
4. If a recovery attempt recently ended in possible abort/expired, suggest smaller fallback or rest, not stricter enforcement.
5. If context is stale, do not make confident claims.
6. If deep work is detected and the topic is compatible with the active goal, stay quiet.
7. If attention budget is exhausted, only critical user-requested reminders may interrupt.

## Recovery policy

Recovery should not be only productivity recovery. It should preserve capacity.

Acceptable recovery outcomes:

- started tiny task;
- clarified obstacle;
- reduced scope;
- deferred with plan;
- rest chosen intentionally;
- user corrected inference;
- assistant stayed quiet because interruption would be counterproductive.

## Implementation sequence

1. Document attention policy in `SAFETY_MODEL.md` or a product policy doc.
2. Add optional attention metadata to planner/nudge outputs.
3. Add product evals for ignored nudges, snooze, stale context, low energy, and deep work.
4. Add burden counters in read-only mode.
5. Only later use burden/receptivity for automatic adaptation.
