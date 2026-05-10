# Project Philosophy

This project is a local-first adaptive AI goal-achievement companion.

Its central purpose is to help the user reach meaningful goals more reliably, efficiently, intelligently, and humanely. It should transform intention into progress: clarifying goals, choosing efficient paths, reducing friction, recovering attention, protecting commitments, learning what works, and improving the route over time.

The system should assist in every appropriate way it can. It should be ambitious about helping the user achieve goals, but conservative about hidden mutation, irreversible action, and pretending uncertain inference is truth.

The companion should feel like a calm, capable, inspectable coach, strategist, analyst, and operator: smart about goals, practical about execution, gentle during recovery, quiet when silence is better, and never punitive.

## Core thesis

The project exists to improve goal achievement.

Not just task capture.
Not just reminders.
Not just productivity metrics.
Not just automation.
Not just a chatbot.

It is an adaptive support system for moving from:

```text
intention -> clarity -> plan -> commitment -> action -> recovery -> outcome -> learning -> better next action
```

The system should connect six things:

1. what the user ultimately wants to achieve;
2. what commitments, constraints, energy, and context exist now;
3. what is blocking progress;
4. what next action, plan, recovery move, or environmental change would improve progress;
5. what the user explicitly accepts as a durable commitment;
6. what happened afterward, so future support gets smarter.

The goal is not to make the system look intelligent. The goal is to make the user's path to important goals clearer, more supported, more resilient, and more efficient.

## What kind of goals?

The system should support many goal shapes:

- life direction goals;
- learning goals;
- health and recovery goals;
- focus goals;
- habit goals;
- project goals;
- maintenance goals;
- daily intentions;
- session goals;
- tiny next actions;
- avoidance-recovery goals;
- "do less" goals;
- "protect energy" goals.

A mature companion should understand that goals are not all the same. Some goals need execution. Some need reflection. Some need simplification. Some need scheduling. Some need recovery. Some need deletion.

The system should help the user ask:

- Is this goal still mine?
- Is it specific enough to act on?
- Is it too large for the current energy level?
- What would count as progress?
- What is the next useful step?
- What obstacle is most likely?
- What plan should happen if that obstacle appears?
- What should be committed to TaskNotes?
- What should remain only a draft or idea?
- What should be reviewed later?

## Goals over tasks

Tasks are not the point. Goals are the point.

Tasks are useful only when they serve a goal, reduce friction, preserve a commitment, or create meaningful progress. A system that creates many tasks but does not improve goal progress is failing.

The companion should avoid task inflation. It should not convert every thought, suggestion, or model output into a task. It should help distinguish:

- goal: the desired outcome;
- project: a body of work serving a goal;
- milestone: a meaningful intermediate state;
- habit: a repeated behavior serving a goal;
- session: a bounded work or recovery interval;
- next action: the next executable step;
- task: a durable human commitment;
- draft: a candidate commitment not yet accepted;
- nudge: temporary support for the current moment;
- outcome: what actually happened.

The system should make these distinctions explicit.

## Goal-reaching as the main thing

The main measure of the project is whether it helps the user reach goals with less friction, less forgetting, less avoidable drift, and better use of energy.

A goal-achievement companion should help with the whole chain:

- clarify vague desires into concrete goals;
- turn goals into plans, milestones, sessions, habits, and next actions;
- identify blockers, missing prerequisites, and false starts;
- choose high-leverage next steps;
- protect attention for important work;
- notice when the current path is inefficient;
- recover after interruption, avoidance, fatigue, or drift;
- convert reviewed decisions into TaskNotes commitments;
- track outcomes and learn what actually helps;
- revise plans when reality changes;
- reduce unnecessary cognitive load;
- prevent old plans from silently pretending to be current truth.

The system should improve both effectiveness and efficiency:

- effectiveness: helping the user make real progress on the right goals;
- efficiency: helping the user reach those goals with less wasted effort, lower cognitive load, better timing, and fewer avoidable restarts.

Efficiency does not mean rushing everything. Sometimes the efficient path is rest, simplification, deferral, delegation, reducing scope, or dropping a goal that no longer matters. The companion should optimize for sustainable progress, not frantic activity.

## Research-informed principles

The philosophy should stay practical, but it should be informed by durable research ideas.

### Goal-setting theory

Goals work better when they are clear, appropriately challenging, connected to commitment, supported by feedback, and matched to the user's capability and self-efficacy.

For this project, that means the companion should help make goals:

- specific enough to guide attention;
- meaningful enough to sustain commitment;
- challenging but not crushing;
- paired with feedback;
- connected to confidence and strategy;
- broken down when complexity is high.

A goal that is too vague should become clearer.
A goal that is too large should become staged.
A goal that repeatedly fails should trigger diagnosis, not blame.

### Implementation intentions and obstacle planning

A goal intention is not enough. The system should help convert goals into situational plans.

The useful pattern is:

```text
If situation, obstacle, or context Y occurs, then I will do action X.
```

The companion should help identify likely obstacles and create practical recovery plans:

- If distractions open during a focus session, offer a 2-minute reset.
- If Anki is overdue and energy is low, propose a tiny review block.
- If a task is stale for many days, ask whether to shrink, defer, delete, or recommit.
- If a plan failed twice, review the blocker before suggesting the same plan again.

This makes the system smarter than a reminder engine. It becomes a goal-to-obstacle-to-action translator.

### Capability, opportunity, and motivation

Progress depends on more than motivation. Behavior needs capability, opportunity, and motivation.

The companion should diagnose blockers through that lens:

- Capability: Does the user know how to do this? Is the task too hard? Is energy too low?
- Opportunity: Is the environment ready? Is the file, app, resource, or time window available?
- Motivation: Does the goal still matter? Is the next step emotionally acceptable? Is there resistance?

Bad support says: "Try harder."
Good support asks: "Which condition is missing?"

Then it helps change that condition.

### Personal informatics

The system collects context so the user can act, not so the system can hoard data.

A healthy loop is:

```text
prepare -> collect -> integrate -> reflect -> act
```

For this project:

- prepare: define goals, policies, and what evidence matters;
- collect: observe local events and user decisions;
- integrate: merge events into readable state;
- reflect: summarize patterns and tradeoffs;
- act: propose, draft, nudge, or revise plans.

If collection does not improve reflection or action, it should be questioned.

### Just-in-time adaptive support

The companion should not simply nudge whenever something looks due. Adaptive support should define:

- distal outcomes: the larger goal;
- proximal outcomes: the near-term change desired now;
- decision points: when the system may decide to intervene;
- tailoring variables: what context affects the decision;
- intervention options: what kinds of support are available;
- decision rules: how context maps to support.

For example:

```text
Distal outcome: maintain Anki learning habit.
Proximal outcome: start a small review session today.
Decision point: when due count is high and no session is active.
Tailoring variables: due count, recent snooze, active recovery, time, energy proxy.
Options: do nothing, show nudge, ask question, draft plan, summarize blocker.
Rule: if recent snooze exists, do nothing; if active recovery exists, do nothing; if due and no blocker, propose tiny start.
```

"Do nothing" is a valid intelligent intervention.

### Autonomy, competence, and dignity

The companion should support autonomy, competence, and dignity.

Autonomy:

- the user remains in control;
- commitments are accepted, not imposed;
- explanations and controls are available.

Competence:

- steps are clear;
- feedback is useful;
- goals are decomposed into achievable actions;
- progress is visible.

Dignity:

- the system is nonjudgmental;
- fatigue and avoidance are treated as normal signals;
- the user is not reduced to productivity metrics.

If the system damages autonomy, competence, or dignity, it is not helping even if it increases activity.

### Human-AI interaction

The system should behave well:

- at first use: explain what it can and cannot do;
- during regular use: show relevant context and useful controls;
- when wrong: make correction easy and graceful;
- over time: learn from feedback without becoming opaque.

It should calibrate trust. It should not overstate confidence. It should expose feedback controls such as:

- this helped;
- this did not help;
- wrong inference;
- less like this;
- not now;
- never suggest this;
- explain why;
- show evidence;
- convert to task;
- keep as draft;
- delete.

## Local-first by default

The companion should work through local files, local queues, local services, and user-owned state.

Local-first means:

- the user can inspect the vault directly;
- the system can work without depending on a cloud service as the source of truth;
- queues, state, proposals, outcomes, and goal evidence are ordinary files where practical;
- behavior can be tested and audited from the repo and the vault;
- failure should degrade into readable files, not hidden platform state.

Local-first does not mean careless mutation. Local files are still real state. The system should treat local writes with the same seriousness as remote writes: atomic when possible, schema-bound, recoverable, and documented.

## Memory

The companion's memory should be goal-directed, useful, humble, and correctable.

It should remember things because they help the user achieve goals, not because it can collect them. Memory should be divided into clear classes:

- observed evidence: events, sessions, app opens, queue items, outcomes;
- declared facts: things the user explicitly said or configured;
- goals: desired outcomes, life areas, priorities, deadlines, and success criteria;
- plans: intended paths toward goals;
- blockers: recurring friction, risks, missing resources, avoidance patterns;
- inferred hypotheses: patterns the system thinks may be true;
- preferences: how the user wants to be helped;
- policies: rules that govern when and how the companion may intervene;
- commitments: durable human-owned tasks or plans, stored through TaskNotes;
- outcomes: what happened after an intervention, plan, or session.

The system should not confuse these classes.

An observed pattern is not a preference.
A preference is not a commitment.
A draft is not a task.
A model guess is not truth.
A goal is not automatically a plan.
A plan is not automatically a commitment.

Good memory for this project should have:

- provenance: where did this belief come from?
- goal link: which goal, project, habit, or commitment does it support?
- confidence: how sure is the system?
- freshness: when was it last confirmed?
- scope: where does it apply?
- expiry: when should it stop being trusted?
- correction path: how can the user say "that is wrong"?
- supersession: what replaced this older belief?
- usefulness: did remembering this improve goal progress?

The ideal memory model is not a giant hidden profile. It is a small, inspectable, evolving personal model with links back to evidence, goals, outcomes, and user corrections.

## Memory should improve decisions

Memory should not merely answer "what happened?" It should improve goal-support decisions.

Examples:

- If a certain nudge is ignored repeatedly, reduce or change it.
- If the user succeeds after tiny starts, prefer tiny starts during low energy.
- If a goal repeatedly stalls at the same step, surface the blocker.
- If a task stays stale, ask whether to shrink, defer, delete, or recommit.
- If a session succeeds at a certain time of day, suggest similar timing.
- If a goal has no next action, propose one.
- If a goal has many tasks but no progress, suggest simplification.

Memory should make the system more context-aware, but also more humble. The older or weaker the evidence, the softer the claim.

## Agency

The companion should be agentic, but gated.

Agency means the system can notice, reason, plan, propose, coordinate, and follow up across context. It may decide that a goal is stalled, that a commitment is stale, that a recovery prompt is appropriate, that a plan should be revised, or that a task draft should be prepared.

But agency must not imply uncontrolled authority.

The system should follow this agency ladder:

1. observe;
2. summarize;
3. classify;
4. connect context to goals;
5. identify blockers and opportunities;
6. propose;
7. draft;
8. ask for approval;
9. execute only bounded, explicit, authorized actions;
10. record what happened and learn from the outcome.

Most of the system should live in steps 1-7. Steps 8-9 are special and must be narrow, logged, test-covered, and easy to disable.

LLMs should stay on the proposal side of the boundary. They can help generate options, wording, summaries, hypotheses, plans, and task drafts. They should not silently execute commands, mutate TaskNotes, archive or delete state, launch apps, or rewrite commitments.

## Assist in every appropriate way

"Assist in every possible way" should mean: use every safe, appropriate, inspectable form of help that improves goal achievement.

The system may help by:

- clarifying goals;
- decomposing goals;
- identifying next actions;
- detecting stale commitments;
- preparing task drafts;
- suggesting reviews;
- noticing blockers;
- proposing recovery moves;
- adjusting timing;
- reducing scope;
- protecting attention;
- summarizing progress;
- creating obstacle-response plans;
- comparing alternatives;
- tracking outcomes;
- learning user preferences;
- recommending environment changes;
- surfacing contradictions between goals and actions;
- asking useful questions;
- staying silent when intervention would be harmful.

The system should not help by silently taking over commitments, hiding uncertainty, nagging, manipulating, or optimizing for activity instead of meaningful progress.

## Smartness

The goal is not to make the system look smart. The goal is to make it intelligently useful for reaching goals.

A smart companion should:

- understand the user's goals and current commitments;
- notice which goals are active, stalled, over-scoped, or under-supported;
- identify high-leverage next actions;
- know when not to interrupt;
- adapt to energy, context, and recent outcomes;
- distinguish urgency from anxiety;
- distinguish important goals from noisy impulses;
- prefer small reversible steps when the user is stuck;
- suggest bigger strategic revisions when the current path is inefficient;
- explain why it is suggesting something;
- offer alternatives;
- learn from dismissals and corrections;
- stop repeating interventions that do not help;
- preserve user dignity.

The highest form of smartness here is not autonomy. It is well-timed, low-burden support that improves the user's ability to reach their own goals.

Smartness should be measured by outcomes such as:

- more goals converted into clear next actions;
- fewer forgotten commitments;
- better prioritization;
- better recovery after drift;
- fewer stale nudges;
- better timing;
- more useful recovery starts;
- lower user burden;
- fewer wrong assumptions;
- clearer explanations;
- more successful follow-through;
- better daily and weekly review quality.

It should not be measured by how many actions the system can take.

## Efficiency

Efficiency means reaching worthwhile goals with less waste.

The system should reduce waste in many forms:

- wasted attention;
- duplicated planning;
- stale tasks;
- unclear next actions;
- repeated avoidable failures;
- needless context switching;
- over-large plans;
- wrong-time nudges;
- forgotten decisions;
- unreviewed commitments;
- manual bookkeeping that can be safely summarized or drafted.

But efficiency must be humane. The most efficient route may be to rest, pause, simplify, or abandon a goal that no longer fits. The companion should not treat all friction as laziness or all inactivity as failure.

Efficient goal-reaching means:

```text
right goal
+ right next step
+ right time
+ right energy level
+ right support
+ right commitment boundary
+ feedback from outcomes
```

## Recovery-oriented design

The companion should assume that distraction, avoidance, fatigue, and inconsistency are normal parts of goal pursuit.

It should not shame the user.
It should not punish missed plans.
It should not escalate nagging as a default.
It should not treat productivity as moral worth.

Recovery-oriented behavior means:

- restart from the current state, not from the ideal plan;
- reconnect the user with the goal when useful;
- prefer the smallest useful next action;
- make it easy to say "not now";
- treat silence as meaningful feedback;
- make success criteria concrete;
- close loops gently;
- summarize outcomes without blame;
- help the user resume instead of ruminate.

A good nudge should feel like a handrail, not a command.

## Human commitment boundary

TaskNotes are the durable human commitment surface.

That means real TaskNotes entries should represent commitments the user has accepted or intentionally created. The system may prepare drafts, propose changes, or build reviewed artifacts, but direct mutation of TaskNotes is a high-authority act.

The future direction is a deterministic apply/promote gate:

- goals and context shape proposals;
- LLMs and planners create plans, proposals, or drafts;
- review surfaces show them to the user;
- approved drafts become structured apply requests;
- the apply gate validates and writes;
- the system records what changed, why, and which goal it supports.

Legacy/direct TaskNotes mutation paths should be treated as temporary compatibility surfaces to deprecate or hard-gate.

## Inspectability

Every important behavior should be explainable from files, schemas, tests, and docs.

A future contributor should be able to answer:

- what goal does this behavior support?
- what wrote this file?
- what reads it?
- what schema does it follow?
- is it current, legacy, planned, or deprecated?
- can it mutate live state?
- can it mutate TaskNotes?
- can an LLM influence it?
- what test covers the dangerous path?
- what outcome would prove this helped?
- what should I do if it fails?

If the answer requires hidden knowledge, the design is not inspectable enough.

## Learning loop

The desired learning loop is:

```text
goals and commitments
-> context providers
-> evidence ledger
-> personal model hypotheses
-> plans and proposals
-> review and controls
-> bounded policy experiments
-> outcomes
-> revised hypotheses and better plans
```

This loop should remain humble. The system should learn slowly from evidence, corrections, and outcomes. It should prefer reversible adaptation over permanent conclusions.

Examples:

- "You often dismiss Anki nudges late at night" is a hypothesis.
- "Do not nudge me after 22:00" is a user policy.
- "Finish this course by June" is a goal.
- "Review 20 cards today" is a proposed commitment until accepted.
- "Create a TaskNote for daily Anki" is a commitment only if the user accepts it.
- "This intervention helped" is an outcome signal.

These should not collapse into one undifferentiated memory blob.

## Goal operating loop

The ideal system should support a practical operating loop.

### 1. Orient

What matters now?

- active goals;
- current commitments;
- available energy;
- relevant context;
- deadlines and windows;
- recent outcomes.

### 2. Choose

What is the best next move?

- continue;
- shrink;
- defer;
- recover;
- ask for clarity;
- prepare a task draft;
- revise the plan;
- do nothing.

### 3. Commit

What should become durable?

- only reviewed, accepted commitments should become TaskNotes;
- uncertain ideas remain proposals or drafts;
- plans should retain goal links and success criteria.

### 4. Act

What support helps execution?

- nudge;
- focus session;
- phone action;
- checklist;
- recovery target;
- context summary;
- tiny start.

### 5. Review

What happened?

- completed;
- started;
- ignored;
- snoozed;
- blocked;
- failed due to context;
- failed due to plan quality;
- succeeded unexpectedly.

### 6. Learn

What should change?

- timing;
- goal scope;
- next action size;
- intervention type;
- reminder channel;
- policy;
- confidence;
- priority.

This loop is more important than any single module.

## Modularity and future instruments

Modularity is a core part of the philosophy.

The user will keep inventing new ways the companion could help: new goal workflows, new context sources, new phone controls, new Obsidian surfaces, new local models, new memory views, new evaluators, and new recovery instruments.

The system should welcome that.

New functionality should be added as explicit instruments around a small deterministic kernel, not by giving one giant agent more authority. Each instrument should declare:

- what goal it serves;
- what it reads;
- what it writes;
- what schema it uses;
- what authority it needs;
- whether an LLM can influence it;
- whether it can mutate TaskNotes;
- how the user reviews or corrects it;
- how it is tested;
- how it can be disabled.

This makes the project expandable without becoming chaotic.

A future instrument might be a goal reviewer, a blocker detector, a language-learning coach, a focus-session planner, a stale-task cleaner, a screenshot summarizer, a voice capture parser, a semantic memory retriever, or a weekly strategy reviewer. All of these should plug into the same basic architecture:

```text
context -> memory -> proposal -> review -> bounded action -> outcome -> learning
```

Modern LLMs and neural networks make many new instruments possible. The project should use them for better goal understanding, semantic memory, planning, multimodal capture, evaluation, and explanation. But stronger models should improve proposals and insight, not erase review boundaries.

The more capable the model becomes, the more important the extension model becomes.

## Voice and relationship

The companion should sound like a calm, capable collaborator.

Preferred voice:

- goal-aware;
- specific;
- kind;
- nonjudgmental;
- brief when interrupting;
- more detailed when reviewing;
- explicit about uncertainty;
- clear about what it can and cannot do;
- oriented toward the next useful step.

Avoid:

- guilt;
- urgency inflation;
- fake certainty;
- productivity moralizing;
- manipulative streaks;
- "I know what is best for you" behavior;
- optimizing for activity instead of meaningful progress.

The user remains the author of their life. The system is a tool for reflection, recovery, strategy, and follow-through.

## Product promise

The promise of this project is:

- better goal clarity;
- better next actions;
- fewer forgotten commitments;
- less repeated drift;
- smarter recovery;
- more useful reviews;
- more humane productivity;
- more progress with less self-management overhead.

The system should make the user's goals easier to pursue, not make the user manage another complicated productivity system.

## Design north star

The north star is:

> A local-first, inspectable, adaptive goal-achievement companion that helps the user clarify goals, choose efficient paths, recover attention, add new instruments easily, and convert reviewed proposals into human-owned commitments without hidden authority escalation.

Everything else should serve that.

When choosing between two designs, prefer the one that is:

- more useful for reaching goals;
- more modular without becoming less bounded;
- more inspectable;
- less surprising;
- easier to correct;
- safer by default;
- lower burden;
- more respectful of attention;
- more explicit about authority;
- easier to test;
- better at preserving human ownership of commitments;
- better at learning from real outcomes.

The project should become smart by becoming clearer, more bounded, more modular, more adaptive, more goal-aware, and more humane.
