# Local AI Mentor Agent TODO

## Vision

Build a local-first, Nix-managed, Obsidian-first personal mentor/agent system.

The system should help with:

- STEM study
- Anki and spaced repetition
- Obsidian notes and knowledge work
- TaskNotes task execution
- daily planning
- weekly and long-term goal progress
- calisthenics progress
- Neovim / CLI learning
- language learning
- depression / low motivation / executive dysfunction support
- general performance improvement
- recovery from stuck, overwhelmed, or distracted states

The agent should communicate through:

- Obsidian first
- existing Tasker/phone surface second
- future desktop popup / slide interface later
- future voice or richer UI later

The important design rule:

```text
surfaces are clients;
the agent core is shared.
```

## Philosophy

The project should follow these principles:

* Local-first.
* Nix-managed.
* Modular.
* Inspectable.
* Adjustable by configuration and dialog.
* Read-only observation by default.
* Explicit mutation boundaries.
* LLMs propose; gates authorize.
* User can freely change agent behavior and proactivity.
* UI should not own intelligence.
* Obsidian should be the first real interaction workbench.
* Phone/Tasker should remain a lightweight companion surface.
* Hyprland/Niri custom UI comes after the agent logic is stable.

<!-- AI-ADAPTIVE-PERSONAL-MODEL:START -->

## Product direction: adaptive personal productivity companion

This project is not just a reminder bot, a generic LLM agent, or a task writer. It is intended to become a local-first adaptive productivity companion: a supportive assistant/friend that helps the user make progress on long-term and short-term goals, recover from stuck states, and learn what actually works for this specific person over time.

The system should optimize for sustainable goal progress and quality productive hours, not raw time spent or notification volume. It may choose rest, fallback planning, smaller steps, or silence when those are more likely to improve long-term outcomes.

Research-aligned design anchors:

* Personal informatics loop: prepare, collect, integrate, reflect, act.
* Behavior-change techniques: explicit goals, action planning, prompts/cues, feedback, self-monitoring, review, and problem solving.
* Self-determination theory: preserve autonomy, competence, and supportive relatedness.
* COM-B: diagnose behavior through capability, opportunity, and motivation instead of moralizing inaction.
* Implementation intentions: prefer concrete if-then plans over vague motivation.
* Just-in-time adaptive intervention logic: adapt intervention timing, channel, intensity, and content to context.
* Recovery research: protect capacity, detachment, relaxation, mastery, and control; do not turn productivity into a guilt loop.

The system may automatically adapt from evidence, including inaction. Adaptations must remain inspectable, reversible, locally stored, and bounded by explicit goals, capacity state, safety rules, and user correction.

Hybrid goal model:

* Obsidian / TaskNotes are the human-facing surface for goals, commitments, plans, reflection, and review.
* The AI vault is the operational surface for structured goals, learned patterns, policies, interventions, outcomes, and evidence.
* Natural language is a control surface that creates immediate actions, memory updates, policy changes, or proposals depending on context and risk.

The system should distinguish:

* approved facts: explicit user-provided or user-confirmed information;
* inferred patterns: evidence-backed hypotheses about timing, friction, energy, channels, and intervention effectiveness;
* policies: behavior-changing rules for nudging, scheduling, suppression, adaptation, and review;
* goals: desired outcomes, habits, projects, recovery targets, and maintenance baselines;
* interventions: nudges, questions, plans, reviews, and fallback suggestions;
* outcomes: acted, ignored, snoozed, dismissed, quick-exit, sustained, fallback accepted, completed, or corrected.

Strong automatic adaptation is allowed for timing, tone, channel, frequency, fallback choice, planning strategy, and question style. Confirmation is still required for durable external commitments, disabling important goals, increasing pressure substantially, enabling new executors/services, or writing to external systems.

When an important goal repeatedly fails in the moment, the system should not repeat the same pressure. It should navigate: shrink the action, change timing/channel/tone, suggest a fallback, create tomorrow's plan, and learn which strategy works better.

<!-- AI-ADAPTIVE-PERSONAL-MODEL:END -->

## Core loop

```text
observe
  -> build shared context
  -> understand goals/plans/preferences
  -> generate proposal
  -> validate/gate proposal
  -> render interaction
  -> receive user response/action
  -> execute approved mutation
  -> observe outcome
  -> learn/update context
```

## Authority boundaries

### Observation only

These may read facts but must not directly command the system:

* ActivityWatch
* phone telemetry
* desktop/window state
* Obsidian readers
* Anki readers
* git/NixOS diagnostics
* calendar/time/task readers

### Context building

`agent_context.py` should become the central read-only brainstem.

It may aggregate:

* current active interactions
* recent user actions
* recent snoozes
* recent nudges
* ActivityWatch facts
* phone facts
* Obsidian facts
* TaskNotes facts
* Anki facts
* recovery state
* intervention outcomes
* long-term goal state
* user preferences
* planner mode

It must not:

* write nudges
* write tasks
* edit Obsidian
* execute shell commands
* classify recovery outcomes
* clear interactions

### Proposal generation

LLM and deterministic modules may propose:

* a nudge
* a question
* an Obsidian write
* a task creation/update
* a study session
* a recovery intervention
* a daily plan
* a weekly review
* a command/action to approve

They must output declarative proposals, not perform actions.

### Gates

`proposal_gate.py` or related gate modules must decide whether proposals are allowed.

Gate checks should include:

* active interaction already present
* recent snooze
* quiet hours
* deep focus detected
* unsafe action
* unknown target
* unsupported mutation
* autonomy level too low
* low confidence
* missing required plan/goal context
* too many nudges
* stale context

### Actions

Only explicit action bridges may mutate state.

Examples:

* action-bridge
* future obsidian-action-bridge
* future desktop-action-bridge
* future task/action executor

## Architecture target

```text
ActivityWatch
Phone telemetry
Obsidian vault
TaskNotes
Anki
NixOS/systemd
git/dev diagnostics
        |
        v
agent_context.py
        |
        v
planner / LLM / deterministic proposer
        |
        v
proposal_gate.py + nudge_policy.py + autonomy_policy.py
        |
        v
interaction renderer
        |
        +--> Obsidian interaction files
        +--> phone Tasker/WebView files
        +--> future desktop popup
        |
        v
AI/inbox/actions/*.json
        |
        v
action bridge / approved executors
        |
        v
state + events + outcomes
```

## Phase 1: Obsidian-first interaction protocol

Goal: make Obsidian the main place where you can talk to the system.

### Phase 1.5 checkpoint

Some Obsidian protocol pieces now exist in code and smoke tests. Before adding deeper TaskNotes behavior, reclassify this section into implemented, partial, open, and deferred items.

Do not treat old unchecked bullets as proof that the feature is missing. Cross-check current code, smoke tests, and live diagnostics first.

Create:

* `AI/outbox/to-obsidian/current-interaction.json`
* `AI/outbox/to-obsidian/current-interaction.md`
* `AI/outbox/to-obsidian/inbox.md`
* `AI/inbox/obsidian/messages/*.json`
* `AI/inbox/obsidian/actions/*.json`

Support:

* free text
* button-like actions
* answer question
* ack nudge
* snooze
* mark done
* request plan
* request review
* update preference
* approve draft
* reject draft

Tasks:

### 1.6-G.1 Current narrow follow-up: core/vault default consolidation

Completed as a small non-feature change. The goal was to finish the central configuration spine before adding more adaptive behavior.

* [x] Remove now-unused local `vaultRoot` / `aiDir` / `taskNotesDir` let bindings from `modules/programs/ai/default.nix`.
* [x] Make `vault-bridge` option defaults consume `config.my.ai.core.{vaultRoot,aiDir,taskNotesDir}` instead of duplicating absolute defaults.
* [x] Verify `config.my.ai.core.aiDir` and `config.my.ai.vault.aiDir` still evaluate to the same path.
* [x] Run smoke, audit, rebuild, user daemon reload, and live check before committing.
* [x] Commit as `Consolidate AI vault defaults through core config`.

* [ ] Define `obsidian_interaction.v1`.
* [ ] Define `obsidian_message.v1`.
* [ ] Define `obsidian_action.v1`.
* [ ] Add Markdown templates usable from Obsidian.
* [ ] Add Templater commands/scripts to write messages/actions.
* [ ] Add TaskNotes-compatible task creation proposal.
* [ ] Add smoke tests using a temporary vault fixture.
* [ ] Keep phone interaction files compatible.

<!-- AI-PHASE-1-6-ADAPTIVE-MODEL:START -->

## Phase 1.6: Adaptive personal model foundation

Goal: define the hybrid goal, memory, policy, and learning architecture before expanding TaskNotes-heavy Phase 2 automation.

This phase should make the project direction explicit: automatic learning is allowed and desired, but it must be explainable, reversible, local-first, and bounded by deterministic safety rules.

### 1.6-A. Define the personal model layer

Create contracts for:

* `approved_fact.v1` — explicit user-provided or confirmed facts.
* `inferred_pattern.v1` — evidence-backed, confidence-scored behavior patterns.
* `preference_memory.v1` — tone, channel, timing, and interaction preferences.
* `capacity_state.v1` — high-focus, normal, low-energy, overloaded, recovery-needed, shutdown.
* `relationship_preference.v1` — how the assistant should interact: supportive, attentive, honest, non-moralizing, gently persistent.

Initial planned paths:

```text
AI/state/profile/approved-facts.json
AI/state/profile/inferred-patterns.json
AI/state/profile/preference-memory.json
AI/state/profile/capacity-state.json
```

Rules:

* Store behavior patterns, not identity judgments.
* Inferred patterns should have confidence, evidence counts, last-updated time, decay behavior, and correction state.
* User corrections should append events and mark old inferences inactive or superseded; avoid hard deletion by default.

### 1.6-B. Define operational goal and policy layers

Use the hybrid model:

* Obsidian / TaskNotes: human-facing goals, commitments, planning notes, reflection.
* AI vault: machine-readable operational goal state, policies, patterns, and outcomes.

Create contracts for:

* `goal.v1`
* `goal_link.v1` between AI state and Obsidian/TaskNotes notes
* `nudge_policy.v1`
* `scheduling_policy.v1`
* `suppression_rule.v1`
* `adaptation_policy.v1`
* `experiment_policy.v1`

Policies should be scoped globally and per goal. Global patterns can affect capacity/tone; per-goal policies should control timing, channel, intensity, fallback, and review cadence.

### 1.6-C. Define feedback and outcome vocabulary

The system must learn from both action and lack of action.

Initial outcome vocabulary:

* acted
* started
* sustained
* completed
* fallback_accepted
* snoozed
* dismissed
* ignored
* quick_exit
* no_response
* negative_feedback
* positive_feedback
* corrected_inference

Inaction should count as evidence, but with lower confidence unless repeated or confirmed. Ignored nudges are ambiguous: they may mean bad timing, missed notification, low capacity, unclear next step, avoidance, or goal drift.

### 1.6-D. Define natural-language control classes

Natural language should classify into one or more of these:

* immediate ephemeral action: snooze, hide today, ask later;
* approved memory update: explicit fact or preference;
* automatic policy adjustment: less often, gentler, earlier, stop this type today;
* proposal-required durable change: recurring task, new goal, schedule change, stronger nudge policy;
* reflective dialogue: help me understand why I avoid this;
* unsafe/unsupported request: arbitrary execution, bypassing gates, deleting audit history.

Ambiguous requests such as "regularly do that" should produce proposals with options: TaskNotes recurring task, AI policy, goal rule, calendar/reminder, or review cadence.

### 1.6-E. Define explanation and review surfaces

Obsidian should be the primary review surface. The system must be able to generate reviews for any requested period, not only weekly.

Planned review surfaces:

```text
AI/outbox/to-obsidian/personal-model-review.md
AI/outbox/to-obsidian/goal-review.md
AI/outbox/to-obsidian/policy-review.md
AI/outbox/to-obsidian/learning-review.md
```

Required questions the system should answer:

* Why did you nudge me now?
* What did you learn from this period?
* What changed in your policy recently?
* What evidence supports this pattern?
* What goals are stale, blocked, or overloaded?
* Undo or weaken this adaptation.

### 1.6-F. First narrow learning loop

Do not build the whole personal model at once. Start with one small loop, probably Anki/recovery nudges:

1. Track nudge shown / acted / snoozed / dismissed / ignored by time window and channel.
2. Infer weak timing and friction patterns.
3. Adapt timing/frequency/fallback strategy within conservative bounds.
4. Write a reviewable explanation of what changed.
5. Accept correction through buttons or natural language.

This loop should validate the full pattern: evidence -> inference -> policy adjustment -> intervention -> outcome -> review -> correction.

<!-- AI-PHASE-1-6-ADAPTIVE-MODEL:END -->

<!-- AI-PHASE-1-6-CONFIG:START -->

## Phase 1.6-G: Centralized configuration and futureproofing

Goal: make the system easy to adjust from one place before adding more adaptive behavior.

`modules/programs/ai/default.nix` should be the human-editable profile layer. Submodules should expose typed options and consume `config.my.ai.*`; Python scripts should receive resolved paths and policy knobs through environment variables or explicit CLI flags.

Tasks:

* [ ] Replace remaining hardcoded AI vault paths in active Nix config with `config.my.ai.vault.aiDir` or local `aiDir`.
* [x] Add a shared timezone option instead of hardcoding `Europe/Paris` in each service. Core timezone now exists; runtime fallbacks prefer service-specific env, then `AI_TIMEZONE`, then `Europe/Paris`.
* [ ] Inventory canonical relative paths and decide whether to add a `my.ai.paths` option family.
* [ ] Keep canonical relative protocol paths stable in code: `inbox/actions`, `inbox/from-phone/events`, `inbox/obsidian/messages`, `inbox/obsidian/actions`, `outbox/to-phone`, `outbox/to-obsidian`.
* [ ] Ensure new Python CLIs accept `--ai-dir` or read `AI_DIR`.
* [ ] Ensure new behavior knobs are Nix options before they become hardcoded constants.
* [ ] Keep docs examples clearly separated from actual configuration authority.
* [ ] Avoid broad rewrites; migrate one option family at a time with smoke coverage.

### 1.6-G.2 Current narrow follow-up: runtime fallback cleanup

Completed as a small compatibility cleanup. Direct-run Python tools now honor the new generic core timezone environment where possible, without breaking legacy service-specific env vars or tests.

* [x] Read `ai_system/time_utils.py` before changing timezone behavior.
* [x] Classify remaining `Europe/Paris` and `/home/daniil/...` literals as canonical core defaults, docs/examples, tests, dev helpers, or runtime fallbacks.
* [x] Keep `modules/programs/ai/core/default.nix` literals as the canonical Nix defaults.
* [x] Leave docs/examples/tests unchanged unless doing a dedicated docs/test cleanup.
* [x] Update runtime Python timezone fallbacks to prefer service-specific env var, then `AI_TIMEZONE`, then `Europe/Paris`.
* [x] Consider only narrow direct-run fallback cleanup for `AI_DIR` / `TASKNOTES_DIR`; do not introduce Nix eval into Python runtime.
* [x] Reword or check off the older TODO item about adding a shared timezone option.
* [x] Run smoke, audit, rebuild, user daemon reload, and live check before committing.
* [x] Commit as `Honor AI core timezone in runtime fallbacks`.


<!-- AI-PHASE-1-6-CONFIG:END -->

## Phase 2: TaskNotes integration

Goal: make tasks concrete, inspectable Markdown objects.

TaskNotes should be used as the action/task substrate because each task can be a note with structured YAML metadata.

Tasks:

* [ ] Decide task folder layout.
* [ ] Define frontmatter fields:

  * [ ] `goal_id`
  * [ ] `project_id`
  * [ ] `area`
  * [ ] `status`
  * [ ] `priority`
  * [ ] `energy`
  * [ ] `estimated_minutes`
  * [ ] `due`
  * [ ] `scheduled`
  * [ ] `source`
  * [ ] `agent_created`
  * [ ] `agent_reason`
* [ ] Create `obsidian_task_context.py`.
* [ ] Create proposal type `create_task_note`.
* [ ] Create proposal type `update_task_note`.
* [ ] Create proposal type `suggest_next_task`.
* [ ] Allow direct task creation only inside allowed folders and schemas.
* [ ] Add approval gate for destructive edits.
* [ ] Add smoke tests.

## Phase 3: Goal model

Goal: make long-term goals easy to add through dialog.

Create `goal.v1`.

Fields:

* `goal_id`
* `title`
* `area`
* `why`
* `desired_outcome`
* `horizon`
* `current_level`
* `next_milestone`
* `next_action`
* `review_cadence`
* `active`
* `last_reviewed`
* `confidence`
* `notes`

Initial goal areas:

* STEM study
* calisthenics
* Neovim/CLI
* language learning
* NixOS / local AI project
* mental health / recovery
* admin/life maintenance

Tasks:

* [ ] Decide if goals live in Obsidian, AI state, or both.
* [ ] Add goal reader.
* [ ] Add goal writer proposal.
* [ ] Add “add goal through dialog” flow.
* [ ] Add weekly goal review interaction.
* [ ] Add stale goal detection.
* [ ] Add too-many-active-goals warning.
* [ ] Add tests.

## Phase 4: Shared context brainstem

Goal: make every planner see the same facts.

Extend `agent_context.py`.

Inputs:

* Obsidian goals
* Obsidian tasks
* TaskNotes tasks
* recent notes
* Anki status
* ActivityWatch state
* phone state
* active interactions
* recovery state
* outcomes
* preferences
* recent user messages

Outputs:

* `AI/state/agent-context/latest.json`
* `AI/state/agent-context/latest.md`

Tasks:

* [ ] Add source freshness metadata.
* [ ] Add confidence metadata.
* [ ] Add bounded event tails.
* [ ] Add “missing source” handling.
* [ ] Add fake fixture tests.
* [ ] Add diagnostics in audit/live check.

## Phase 5: ActivityWatch context

Goal: use activity observation intelligently, without making ActivityWatch authoritative.

ActivityWatch should answer:

* what app/window is active?
* how long has current focus lasted?
* is the user AFK?
* is there a distraction loop?
* is there deep work?
* was there a study/work session?
* what happened today?

Tasks:

* [ ] Add `activitywatch_context.py`.
* [ ] Read buckets/events from ActivityWatch API.
* [ ] Summarize only recent bounded windows.
* [ ] Materialize:

  * [ ] `AI/state/activitywatch/latest.json`
  * [ ] `AI/state/activitywatch/latest.md`
* [ ] Feed facts into `agent_context.py`.
* [ ] Add policies:

  * [ ] avoid interrupting deep work
  * [ ] detect distraction loops
  * [ ] detect study sessions
  * [ ] detect computer idle periods
* [ ] Add tests with fake ActivityWatch data.

## Phase 6: Preferences and adjustable behavior

Goal: the agent can become more or less proactive by request.

Create `preferences.v1`.

Fields:

* `proactivity_level`
* `coach_style`
* `max_nudges_per_hour`
* `quiet_hours`
* `preferred_surfaces`
* `allowed_direct_writes`
* `allowed_approval_actions`
* `study_mode`
* `recovery_mode`
* `planning_cadence`
* `goal_review_cadence`
* `strictness`
* `mental_health_sensitivity`

Modes:

* strict coach
* gentle companion
* operator assistant
* study mentor
* recovery helper
* planning assistant

Tasks:

* [ ] Add preference reader.
* [ ] Add preference update actions.
* [ ] Add dialog command: “be more proactive”.
* [ ] Add dialog command: “stop nudging”.
* [ ] Add dialog command: “be stricter”.
* [ ] Add dialog command: “be gentler”.
* [ ] Add smoke tests.

## Phase 7: Nudge policy

Goal: helpful, not annoying.

Create `nudge_policy.py`.

Inputs:

* proposal
* context
* preferences
* recent outcomes
* current surface availability

Outputs:

* allow / deny
* surface
* urgency
* cooldown
* reason
* wording style

Rules:

* never spam
* respect snooze
* respect quiet hours
* avoid interrupting deep focus
* prefer questions when uncertain
* prefer tiny action when overwhelmed
* prefer planning/review when calm
* adapt based on outcomes

Tasks:

* [ ] Move anti-spam out of individual components.
* [ ] Add policy smoke tests.
* [ ] Add outcome-driven ranking.
* [ ] Add diagnostics explaining why a nudge was or was not shown.

## Phase 8: LLM proposal discipline

Goal: LLM becomes powerful but bounded.

Define `agent_proposal.v1`.

Fields:

* `proposal_id`
* `source`
* `planner_mode`
* `context_id`
* `decision`
* `confidence`
* `reason_codes`
* `target`
* `interaction`
* `proposed_actions`
* `required_autonomy_level`
* `requires_approval`
* `expiration`
* `facts_used`

Planner modes:

* `help-now`
* `study`
* `plan-day`
* `review-goals`
* `recovery`
* `obsidian-assistant`
* `diagnostic`
* `conversation`

Tasks:

* [ ] Force LLM output into proposal JSON.
* [ ] Reject direct shell/action instructions.
* [ ] Store raw LLM output.
* [ ] Store parsed proposal.
* [ ] Store gate result.
* [ ] Add replay tests.

## Phase 9: Durable agent runs

Goal: every important agent decision is inspectable.

Create:

* `AI/state/agent-runs/<run_id>/context.json`
* `AI/state/agent-runs/<run_id>/prompt.md`
* `AI/state/agent-runs/<run_id>/raw-output.txt`
* `AI/state/agent-runs/<run_id>/proposal.json`
* `AI/state/agent-runs/<run_id>/gate-result.json`
* `AI/events/agent-runs/YYYY-MM-DD.jsonl`

Tasks:

* [ ] Add run ids.
* [ ] Add idempotency by proposal id.
* [ ] Add diagnostics:

  * [ ] last successful run
  * [ ] last rejected proposal
  * [ ] last parse failure
  * [ ] last action produced

## Phase 10: Obsidian mentor dialog

Goal: make it feel like a mentor you can talk to.

Support phrases like:

* “plan my day”
* “what should I do now?”
* “I feel stuck”
* “make me a study plan”
* “review my goals”
* “add calisthenics progression”
* “be stricter this week”
* “stop being proactive today”
* “turn this note into tasks”
* “what did I avoid today?”
* “help me recover”

Tasks:

* [ ] Add intent classifier for text messages.
* [ ] Map intents to proposal types.
* [ ] Add Obsidian templates/buttons.
* [ ] Add TaskNotes task generation.
* [ ] Add daily planning workflow.
* [ ] Add weekly review workflow.
* [ ] Add study session workflow.
* [ ] Add recovery workflow.

## Phase 11: Phone surface

Goal: keep Tasker phone useful but not central.

Phone should support:

* current nudge
* current question
* quick buttons
* free-text answer if practical
* start recovery
* done
* snooze
* maybe “talk to agent” later

Tasks:

* [ ] Keep existing phone state stable.
* [ ] Do not depend on Obsidian mobile automation.
* [ ] Route phone actions through same action bridge.
* [ ] Add phone text later only if it fits cleanly.

## Phase 12: Desktop surface later

Goal: build the Disco-Elysium-like UI after logic works.

Do not start here.

Future surfaces:

* Hyprland popup
* Niri popup
* slide-in panel
* local webview
* TUI
* notification buttons

Tasks:

* [ ] Define desktop interaction output.
* [ ] Create simple terminal/rofi prototype first.
* [ ] Later design custom UI.
* [ ] Keep UI dumb: render interactions, send actions/messages.
* [ ] Do not duplicate agent logic in UI.

## Phase 13: Autonomy ladder

Goal: safe path toward powerful automation.

Levels:

* L0 observe only
* L1 diagnose only
* L2 suggest
* L3 write safe drafts/tasks
* L4 execute approved actions
* L5 execute pre-approved low-risk actions
* L6 high-risk actions require explicit confirmation every time

Tasks:

* [ ] Add `max_autonomy_level`.
* [ ] Assign autonomy level to every proposal.
* [ ] Gate by autonomy.
* [ ] Allow per-area autonomy settings.
* [ ] Add diagnostics.

## Phase 14: Approved action expansion

Eventually support approved actions:

* open app
* create Obsidian note
* create TaskNotes task
* edit task
* schedule reminder
* start timer
* run diagnostics
* commit code
* start study session
* create plan
* review goal
* update preference

Tasks:

* [ ] Add actions one by one.
* [ ] Start with low-risk Obsidian/TaskNotes writes.
* [ ] Add destructive-action confirmation.
* [ ] Add event logs for every action.

## Phase 15: Replay and evaluation

Goal: improve without breaking behavior.

Create fixtures:

* distracted day
* focused coding day
* Anki success day
* low-motivation day
* goal review day
* too many active goals
* stale task pile
* Obsidian planning day

Tasks:

* [ ] Add replay command.
* [ ] Feed fixture context into proposer.
* [ ] Assert expected gate outcomes.
* [ ] Assert expected interaction type.
* [ ] Use replay before changing policy.

## Immediate implementation order

1. Commit current architecture doc update.
2. Create this TODO.
3. Implement Obsidian inbox/outbox protocol.
4. Add minimal Templater scripts for:

   * send text message
   * send button action
   * request plan
   * request next action
5. Add Obsidian message bridge.
6. Add Obsidian context reader.
7. Add TaskNotes task reader/writer proposal.
8. Extend `agent_context.py` with Obsidian + TaskNotes facts.
9. Define `agent_proposal.v1`.
10. Add `nudge_policy.py`.
11. Add `preferences.v1`.
12. Add ActivityWatch read-only context.
13. Add daily planning workflow.
14. Add goal review workflow.
15. Add durable agent run logs.
16. Add richer LLM planner.
17. Only then build the desktop popup UI.

