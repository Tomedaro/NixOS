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

Create:

* `AI/outbox/to-obsidian/current-interaction.json`
* `AI/outbox/to-obsidian/current-interaction.md`
* `AI/outbox/to-obsidian/inbox.md`
* `AI/inbox/from-obsidian/messages/*.json`
* `AI/inbox/from-obsidian/actions/*.json`

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

* [ ] Define `obsidian_interaction.v1`.
* [ ] Define `obsidian_message.v1`.
* [ ] Define `obsidian_action.v1`.
* [ ] Add Markdown templates usable from Obsidian.
* [ ] Add Templater commands/scripts to write messages/actions.
* [ ] Add TaskNotes-compatible task creation proposal.
* [ ] Add smoke tests using a temporary vault fixture.
* [ ] Keep phone interaction files compatible.

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

