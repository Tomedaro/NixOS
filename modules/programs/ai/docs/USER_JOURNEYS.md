# User journeys
## Journey 1: I am stuck

1. User opens phone/Obsidian and says they are stuck, or system detects recovery context.
2. Context hub builds current facts.
3. Planner proposes one tiny next action or one clarifying question.
4. User can start, snooze, say too much, say wrong inference, or ask why.
5. Outcome is recorded.
6. Daily review summarizes what helped and what did not.
7. Learning proposal may adjust timing/tone/scope, but not durable commitments.

Quality checks:

- no shame;
- one small action;
- correction control visible;
- outcome captured;
- no silent TaskNotes mutation.

## Journey 2: Start a focus session

1. User starts session with task/mode/duration.
2. Session manager compiles policy.
3. Context providers expose current session and policy.
4. Nudge logic suppresses irrelevant interruptions.
5. If distracting context appears, system chooses between silence, gentle reminder, or question based on attention policy.
6. Session ends with reflection prompt.

Quality checks:

- policy explains allowed/disallowed context;
- deep-work alignment suppresses interruptions;
- reflection links to learning.

## Journey 3: AI asks a question and user answers

1. Planner writes a bounded question.
2. Phone/Obsidian renders answer options and free-text affordance.
3. User answers.
4. Canonical action lifecycle records answer.
5. Planner/context uses answer in next proposal.
6. If the answer is a correction, it supersedes weaker inference.

Quality checks:

- answer semantics are preserved;
- not now vs never vs wrong are distinct;
- no duplicate lifecycle owner.

## Journey 4: AI proposes a TaskNotes draft

1. Obsidian intent enters inbox.
2. LLM/proposal contract creates reviewable proposal only.
3. User approves a proposal action.
4. Task draft bridge creates TaskNotes-compatible draft in AI outbox/state.
5. Obsidian/Templater or a future deterministic apply gate applies only after explicit review.
6. Provenance links proposal, intent, and goal.

Quality checks:

- draft is not a commitment;
- provenance is visible;
- direct TaskNotes mutation remains legacy/deprecated.

## Journey 5: User corrects a wrong inference

1. User chooses wrong inference or writes a correction.
2. System records correction event.
3. Affected inferred pattern is marked rejected/superseded.
4. Future proposals avoid that inference.
5. Review summary shows correction was applied.

Quality checks:

- user does not need to edit JSON;
- correction beats inferred pattern;
- system repairs tone gracefully.

## Journey 6: Daily review turns outcomes into learning

1. System summarizes sessions, interventions, and outcomes.
2. It distinguishes progress, recovery, burden, and silence/defer decisions.
3. It proposes at most a few learning hypotheses.
4. User accepts/rejects/edits hypotheses.
5. Accepted hypotheses can become time-bounded policy experiments.

Quality checks:

- no automatic overgeneralization;
- learning has evidence and expiry;
- review remains low-burden.

## Journey 7: Low-energy fallback instead of pressure

1. Context or user response indicates low energy.
2. Planner reduces scope and tone intensity.
3. It offers rest, defer-with-plan, or tiny action.
4. Outcome distinguishes rest/defer from failure.
5. Future nudging considers this capacity signal.

Quality checks:

- no guilt loop;
- rest can be valid;
- one tiny next action max;
- no escalation from inaction alone.
