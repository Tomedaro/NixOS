# Local AI Productivity System

This module tree defines a local-first, NixOS-native executive-function support system.

The project is a modular personal AI environment for coordinating:

- desktop activity
- phone events
- Obsidian vault state
- TaskNotes
- Anki
- local LLM planning
- nudges and questions
- future proof/reflection/language-learning workflows

The system is not meant to be a generic “productivity app.” It is intended to become a local adaptive development layer:

```text
observe behavior
→ infer context and friction
→ intervene at the right intensity
→ collect response/proof/reflection
→ update session/task/policy state
→ learn recurring patterns
→ make the next correct action smaller and clearer
```

The guiding idea is that executive dysfunction is often worsened by ambiguity, task size, context switching, shame, and delayed recovery loops. This system should reduce those costs by making intent explicit, monitoring context locally, and offering timely, concrete scaffolding.

The central design rule:

> The LLM should increase agency and precision, but the system must still behave safely and usefully when the LLM fails.

---

## 1. Project status

This system is in active development.

It already has the first version of the core local loop:

```text
start session
→ compile deterministic policy
→ monitor desktop/phone/Anki context
→ classify current state
→ accept check-ins/actions
→ trigger help-now planning
→ write nudges/questions/reports
```

The current development focus is stabilizing the protocol and interaction architecture before adding more ambitious modules such as browser URL classification, proof handling, TaskNotes mutation, language learning, screenshots, or strictness experiments.

Current milestone:

```text
stable file protocol
+ canonical action bridge
+ strict phone event/action separation
+ session-centered policy
+ deterministic fallbacks
+ phone interaction protocol next
```

This README describes both the implemented state and the intended architecture.

---

## 2. Product philosophy

### 2.1 The system is an environment, not a chatbot

A chatbot waits for the user to formulate a request.

This system should eventually behave more like a supportive environment:

- it knows the current session
- it knows the current task
- it knows whether the user is on-task, off-task, idle, or unplanned
- it knows recent check-ins
- it knows Anki backlog state
- it knows whether the current app/title fits the active policy
- it can ask a small question at the right moment
- it can reduce the task when the user is overwhelmed
- it can prepare diary/reflection material from evidence
- it can propose tasks instead of forcing the user to invent them

The user should not need to repeatedly explain “what I am supposed to be doing.” The system should maintain that context locally.

### 2.2 Adaptive scaffolding, not punishment

The system should never shame, moralize, or punish.

Bad behavior is treated as a context/friction signal, not as a character flaw.

Next examples are about Anki, but it might be anything. From singing to calsulus.

Examples:

```text
If user opens YouTube during Anki recovery:
  bad response:
    “Stop procrastinating.”
  good response:
    “This block is for Anki. Return for 3 minutes, then reassess.”
```

```text
If user answers “overwhelmed”:
  bad response:
    “Push through.”
  good response:
    “Overwhelmed mode: 5 cards or 5 minutes. Stop after that.”
```

```text
If user is already on task:
  bad response:
    interrupt repeatedly
  good response:
    stay quiet
```

Strictness is not ideological. It is an adjustable intervention variable.

### 2.3 Local-first and inspectable

The system should prefer:

- local files
- local services
- local LLMs
- local logs
- local automation
- local sync through Syncthing
- plain JSON and Markdown
- declarative NixOS configuration

The user should be able to inspect the whole system with normal shell tools:

```sh
cat AI/state/desktop/now.md
jq . AI/state/session/current.json
tail -20 AI/events/actions/$(date +%F).jsonl | jq
systemctl --user status productivity-coach.service
```

This is important because the system may later monitor sensitive context. Trust requires that state and behavior remain visible.

### 2.4 Deterministic first, LLM second

The LLM is not the foundation.

The deterministic layer should always handle basic cases:

- start session
- end session
- classify obvious on-task/off-task state
- process phone events
- process actions
- write logs
- preserve previous state on failure
- generate a fallback help-now nudge

The LLM adds interpretation and nuance, but the system must not collapse if:

- the model times out
- the model returns invalid JSON
- the model returns low-quality text
- Ollama is unavailable
- the context is truncated

Example:

```text
User says: overwhelmed
Anki backlog exists
LLM times out

System should still write:
  “Overwhelmed mode: 5 Anki cards or 5 minutes. Stop after that.”
```

### 2.5 Session-centered design

The system should not treat `current-task.md` as a static manual note forever.

The core runtime object is a session:

```text
session = current intentional block of behavior
```

Examples:

- Anki Language recovery
- Work on NixOS AI module
- Write diary reflection
- Read and extract notes
- Watch learning video and produce note
- Free time / rest

A session creates a policy.

The policy tells the rest of the system what counts as useful, ambiguous, or distracting.

This matters because the same app/domain can mean different things depending on context:

```text
YouTube during free time:
  maybe okay

YouTube lecture during learning-video session:
  productive

YouTube Shorts during Anki recovery:
  distracting

Telegram during coordination task:
  allowed

Telegram during Anki recovery:
  distracting
```

### 2.6 The vault is the API

The Obsidian vault is not only notes. It is the shared protocol layer.

The NixOS services, Tasker, Syncthing, Obsidian, Anki, and future UI surfaces communicate through files such as:

```text
AI/state/session/current.json
AI/state/session/current-policy.json
AI/state/desktop/now.json
AI/state/phone/latest.json
AI/state/llm/last-output.json
AI/state/llm/last-answer.json
AI/inbox/actions/*.json
AI/inbox/from-phone/events/*.json
AI/outbox/to-phone/current-nudge.md
AI/outbox/to-phone/current-question.md
AI/events/actions/YYYY-MM-DD.jsonl
AI/events/desktop/YYYY-MM-DD.jsonl
AI/events/phone/YYYY-MM-DD.jsonl
```

This is intentionally simple and debuggable.

---

## 3. Repository layout

This directory lives at:

```text
modules/programs/ai/
```

It contains the NixOS modules and Python services for the local AI productivity system.

Current high-level tree:

```text
modules/programs/ai/
├── default.nix
├── README.md
├── python/
│   └── ai_system/
├── activitywatch/
├── action-bridge/
├── anki-bridge/
├── browser-bridge/
├── coach-daemon/
├── compat/
├── desktop-event-bridge/
├── dialog-bridge/
├── hypr-agent/
├── llm-planner/
├── notifications/
├── ollama/
├── phone-bridge/
├── screenpipe/
├── session-manager/
└── vault-bridge/
```

The root module `default.nix` composes the submodules and sets defaults.

---

## 4. Architectural layers

The system can be understood as several layers.

### 4.1 Vault/protocol layer

Implemented by:

```text
vault-bridge/
```

Responsibilities:

- create the shared AI folder structure
- create seed files
- create policy placeholders
- create outbox placeholders
- ensure predictable paths exist

This is the foundation.

If the vault structure is missing or inconsistent, all other modules become harder to debug.

### 4.2 Sensor layer

Implemented by:

```text
activitywatch/
anki-bridge/
phone-bridge/
desktop-event-bridge/
```

Responsibilities:

- observe desktop window/AFK state
- observe Anki backlog/progress
- process passive phone telemetry
- process desktop-originated events/check-ins where relevant

This layer should collect facts, not make high-level plans.

### 4.3 State and action layer

Implemented by:

```text
session-manager/
action-bridge/
```

Responsibilities:

- represent user intent as sessions
- compile deterministic session policies
- process canonical actions
- start/end sessions
- handle check-ins
- trigger help-now after relevant actions
- write normalized action events

This layer turns user commands into system state.

### 4.4 Coach layer

Implemented by:

```text
coach-daemon/
```

Responsibilities:

- read current session/policy
- read ActivityWatch
- classify current activity
- write current desktop state
- log compact desktop events
- send simple rule-based notifications

This is the fast deterministic feedback layer.

### 4.5 Planner layer

Implemented by:

```text
llm-planner/
```

Responsibilities:

- build a compact context pack
- call local Ollama model
- validate/normalize planner output
- write reports
- write nudges
- write pending questions
- provide deterministic help-now fallback

This layer should be helpful but not trusted blindly.

### 4.6 Interaction layer

Implemented currently by:

```text
dialog-bridge/
phone Tasker project generated in the vault
```

Future direction:

```text
phone JSON outbox
desktop panel
unified answer_question actions
```

Responsibilities:

- display questions/nudges to the user
- collect low-friction answers
- allow the system to adapt quickly

The long-term goal is a calm, low-friction, bidirectional interaction loop.

---

## 5. Main data flows

### 5.1 Start session

A session may be started from:

- terminal command
- Obsidian template
- Tasker action
- future TaskNotes action
- future desktop panel
- future schedule

Canonical direction:

```text
UI / Tasker / Obsidian
→ AI/inbox/actions/*.json
→ ai-action-bridge
→ ai-session start
→ AI/state/session/current.json
→ AI/state/session/current-policy.json
→ AI/control/current-task.md
→ AI/control/current-mode.md
→ AI/control/current-block.md
→ AI/events/actions/YYYY-MM-DD.jsonl
→ AI/events/desktop/YYYY-MM-DD.jsonl
```

Example action:

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "start_session",
  "task": "Anki Language recovery",
  "project": "Anki Recovery",
  "mode": "anki",
  "duration": 25,
  "strictness": 2,
  "language_level": 1,
  "timestamp_epoch": "1777840000"
}
```

### 5.2 End session

Canonical direction:

```text
UI / Tasker / Obsidian
→ AI/inbox/actions/*.json
→ ai-action-bridge
→ ai-session end
→ current session marked completed/paused/interrupted/abandoned
→ session archived
→ event logged
```

Example action:

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "end_session",
  "status": "completed",
  "reason": "Ended from Tasker",
  "timestamp_epoch": "1777840000"
}
```

### 5.3 Check in

Canonical direction:

```text
Tasker / Obsidian / desktop
→ AI/inbox/actions/*.json
→ ai-action-bridge
→ AI/state/llm/last-answer.json
→ AI/events/actions/YYYY-MM-DD.jsonl
→ llm-planner-help-now.service
→ AI/outbox/to-phone/current-nudge.md
```

Example action:

```json
{
  "schema_version": "action.v1",
  "source": "tasker",
  "device": "phone",
  "action": "check_in",
  "answer": "overwhelmed",
  "answer_label": "Overwhelmed",
  "free_text": "",
  "timestamp_epoch": "1777840000"
}
```

Expected behavior:

```text
If Anki is active and answer = overwhelmed:
  write fallback/LLM nudge:
    “Overwhelmed mode: 5 Anki cards or 5 minutes. Stop after that.”
```

### 5.4 Passive phone telemetry

Canonical direction:

```text
Tasker profile
→ AI/inbox/from-phone/events/*.json
→ phone-bridge
→ AI/events/phone/YYYY-MM-DD.jsonl
→ AI/logs/phone/YYYY-MM-DD.md
→ AI/state/phone/latest.json
```

Example event:

```json
{
  "schema_version": "event.v1",
  "source": "tasker",
  "device": "phone",
  "event": "phone_unlock",
  "message": "Phone unlocked",
  "timestamp_epoch": "1777840000"
}
```

Passive telemetry should not trigger session commands directly.

### 5.5 Desktop monitoring

Direction:

```text
ActivityWatch / awatcher
→ productivity-coach
→ AI/state/desktop/now.json
→ AI/state/desktop/now.md
→ AI/events/desktop/YYYY-MM-DD.jsonl
→ AI/logs/desktop/YYYY-MM-DD.md
```

The coach classifies the current state as:

```text
on_task
off_task
idle
unknown
no_plan
```

Example:

```text
Session: Anki Language recovery
Allowed apps: Anki, Obsidian, kitty
Current app: Anki

Verdict:
  on_task
Reason:
  Current app 'Anki' matches allowed apps.
```

Example:

```text
Session: Anki Language recovery
Distracting title keyword: YouTube
Current title: Epic DUNE Ambient Music - YouTube — Zen Browser

Verdict:
  off_task
Reason:
  Window title matches distracting keywords.
```

### 5.6 LLM help-now

Direction:

```text
check-in / answer / manual trigger
→ llm-planner-help-now.service
→ compact context
→ local model or fallback
→ AI/state/llm/last-output.*
→ AI/outbox/to-phone/current-nudge.md
→ report in AI/reports/help-now/
```

The help-now mode must stay fast and bounded.

If the local model fails or times out, deterministic fallback should write a useful nudge anyway.

---

## 6. Module descriptions

## 6.1 `default.nix`

Main composition module.

Responsibilities:

- import all AI submodules
- define common vault paths
- enable modules by default
- configure Ollama
- configure coach
- configure Anki bridge
- configure phone bridge
- configure planner
- configure dialog/action/session bridges

Important defaults:

```nix
vaultRoot = "/home/daniil/Sync/Perseverance.Gu";
aiDir = "${vaultRoot}/AI";
taskNotesDir = "${vaultRoot}/TaskNotes";
```

Design principle:

- keep global path defaults here
- keep service-specific implementation in submodules
- avoid putting large inline scripts in `default.nix`

---

## 6.2 `python/ai_system/`

Shared Python support package.

Purpose:

Avoid duplicating low-level bridge logic across modules.

Expected responsibilities:

```text
ai_system.io_utils
  atomic writes
  JSON/text helpers
  safe reads

ai_system.time_utils
  timezone helpers
  now/today formatting

ai_system.events
  normalize events
  append JSONL events

ai_system.queue
  stability checks
  unique processed/failed moves

ai_system.status
  status JSON/Markdown helpers
```

Design principle:

- bridge scripts should be small and domain-specific
- shared mechanics should live here
- no service should copy/paste queue/event/status logic unnecessarily

---

## 6.3 `vault-bridge/`

Initializes the vault protocol.

Service:

```text
ai-vault-init.service
```

Responsibilities:

- create base folders
- create seed files if missing
- create policy docs if missing
- create control files if missing
- create outbox placeholders if missing

Important behavior:

- should not overwrite user-edited files unnecessarily
- should be safe to run repeatedly
- should create missing structure only

The vault bridge defines the filesystem substrate for the system.

---

## 6.4 `activitywatch/`

Runs ActivityWatch/awatcher integration.

Responsibilities:

- run ActivityWatch server
- run window watcher
- run AFK watcher
- expose currentwindow and afkstatus buckets

The coach daemon reads this data.

Design note:

ActivityWatch persists old events. Therefore downstream services must check freshness and avoid acting on stale boot-time activity.

---

## 6.5 `coach-daemon/`

Rule-based desktop coach.

Command:

```text
productivity-coach
```

Service:

```text
productivity-coach.service
```

Responsibilities:

- read current session/policy
- query ActivityWatch
- classify current desktop state
- write current status to JSON/Markdown
- append compact events
- send notifications for off-task/no-plan states
- avoid notification spam through cooldowns
- avoid startup false positives through grace period
- treat stale AFK/window data carefully

Important outputs:

```text
AI/state/desktop/now.json
AI/state/desktop/now.md
AI/state/desktop/coach-state.json
AI/events/desktop/YYYY-MM-DD.jsonl
AI/logs/desktop/YYYY-MM-DD.md
```

Classification principles:

```text
AFK fresh and afk:
  idle

No fresh current window:
  unknown

Current app matches distracting apps:
  off_task

Current title matches distracting keywords:
  off_task

Current app matches allowed apps:
  on_task

Current title matches allowed title keywords:
  on_task

Otherwise:
  unknown
```

Future improvements:

- URL/domain awareness
- browser bridge integration
- session expiry handling
- strictness-dependent notification behavior
- better Obsidian/electron app mapping
- quiet mode while deep work is detected

---

## 6.6 `session-manager/`

Deterministic session manager and policy compiler v0.

Commands:

```text
ai-session start
ai-session status
ai-session end
ai-session modes
```

Request processor:

```text
ai-session-requests
```

Services/path:

```text
ai-session-requests.service
ai-session-requests.path
ai-session-status.service
```

Responsibilities:

- start sessions
- end sessions
- compile deterministic policy
- write current session state
- write current control files
- process legacy/session request files
- archive ended sessions
- log session events

Important outputs:

```text
AI/state/session/current.json
AI/state/session/current-policy.json
AI/state/session/current-policy.md
AI/control/current-task.md
AI/control/current-mode.md
AI/control/current-block.md
AI/state/session/archive/YYYY-MM-DD/*.json
AI/events/desktop/YYYY-MM-DD.jsonl
```

Supported modes:

```text
study
anki
coding
writing
reading
learning-video
admin
free
```

Policy compiler v0 is deterministic. Future versions may include:

- TaskNotes metadata
- long-term plans
- current deadlines
- time of day
- user patterns
- browser context
- recent avoidance loops
- LLM-suggested policy modifications
- authority levels

Design principle:

The current policy is a runtime artifact, not merely documentation.

---

## 6.7 `action-bridge/`

Unified canonical action bridge.

Expected service/path:

```text
ai-action-bridge.service
ai-action-bridge.path
```

Primary inbox:

```text
AI/inbox/actions/*.json
```

Processed/failed queues:

```text
AI/inbox/actions-processed/YYYY-MM-DD/
AI/inbox/actions-failed/YYYY-MM-DD/
```

Important outputs:

```text
AI/state/action-bridge/status.json
AI/state/action-bridge/status.md
AI/events/actions/YYYY-MM-DD.jsonl
AI/state/llm/last-answer.json
```

Responsibilities:

- process canonical user/system actions
- validate action authority
- route session actions to `ai-session`
- convert check-ins into normalized events
- trigger help-now after check-ins
- preserve raw action files in processed/failed queues

Current important actions:

```text
start_session
end_session
check_in
```

Recommended next actions:

```text
answer_question
ack_nudge
dismiss_question
submit_proof
```

Design principle:

All intentional user commands should eventually pass through this bridge.

This includes commands from:

- Tasker
- Obsidian
- desktop panel
- terminal wrapper
- future hotkeys
- future TaskNotes actions

This prevents having many parallel protocols.

---

## 6.8 `phone-bridge/`

Passive phone telemetry bridge.

Service:

```text
phone-bridge.service
```

Primary inbox:

```text
AI/inbox/from-phone/events/*.json
```

Processed/failed queues:

```text
AI/inbox/from-phone/processed/YYYY-MM-DD/
AI/inbox/from-phone/failed/YYYY-MM-DD/
```

Important outputs:

```text
AI/events/phone/YYYY-MM-DD.jsonl
AI/logs/phone/YYYY-MM-DD.md
AI/state/phone/latest.json
AI/state/phone/latest.md
```

Responsibilities:

- process passive phone events
- normalize timestamps
- write phone event JSONL
- write readable phone log
- update latest phone state
- move raw files to processed/failed
- reject misrouted action files if strict contract is enabled

Examples of passive phone events:

```text
phone_unlock
opened_ankidroid
closed_ankidroid
opened_obsidian_app
closed_obsidian_app
```

Design principle:

The phone bridge does not execute commands.

It observes phone context.

Intentional commands go to `action-bridge`.

---

## 6.9 `desktop-event-bridge/`

Bridge for desktop-originated event files.

Purpose:

- normalize desktop events written as files
- process manual check-ins from Obsidian or local UI
- trigger help-now where appropriate
- prevent stale duplicate dialog events from being reprocessed forever

This exists because not all desktop-originated signals come directly from ActivityWatch.

Long-term direction:

Most intentional desktop actions should also become canonical actions under `AI/inbox/actions`.

---

## 6.10 `dialog-bridge/`

Desktop notification bridge for LLM questions.

Service/timer:

```text
dialog-bridge.service
dialog-bridge.timer
```

Responsibilities:

- read pending question
- display desktop notification with buttons
- record answer
- archive answered/expired questions
- update current-question output
- trigger help-now after answer

Important files:

```text
AI/state/llm/pending-question.json
AI/outbox/to-phone/current-question.md
AI/state/llm/last-answer.json
AI/state/llm/questions/archive/YYYY-MM-DD/
AI/inbox/from-desktop/events/
AI/events/desktop/YYYY-MM-DD.jsonl
```

Future direction:

The dialog bridge should become a thin UI adapter.

Instead of owning question lifecycle itself, it should eventually write:

```json
{
  "schema_version": "action.v1",
  "action": "answer_question",
  "question_id": "q-...",
  "answer": "tired",
  "answer_label": "Tired"
}
```

Then `action-bridge` should own the lifecycle.

This allows desktop, phone, and future panel to answer questions consistently.

---

## 6.11 `llm-planner/`

Local LLM planner and fallback system.

Command:

```text
llm-planner --mode help-now
llm-planner --mode block-plan
llm-planner --mode daily-review
```

Services:

```text
llm-planner.service
llm-planner-help-now.service
llm-planner-daily-review.service
```

Responsibilities:

- build context pack
- include compact desktop/phone/Anki/session/task state
- call Ollama
- normalize planner result
- write reports
- write current nudge/question
- write proposed tasks
- preserve previous outputs on failure
- use deterministic fallback for help-now

Important outputs:

```text
AI/context/today.json
AI/context/today.md
AI/state/llm/planner-status.json
AI/state/llm/planner-status.md
AI/state/llm/last-output.json
AI/state/llm/last-output.md
AI/state/llm/last-error.md
AI/outbox/to-phone/current-nudge.md
AI/outbox/to-phone/current-question.md
AI/reports/help-now/*.md
AI/reports/daily/*.md
AI/proposed-tasks/YYYY-MM-DD.md
```

Planner modes:

### `help-now`

Immediate adaptation after:

- check-in
- question answer
- explicit difficulty signal
- possible acute off-task/friction event

Should be:

- fast
- small context
- concrete
- low ambiguity
- fallback-safe

Example output:

```text
Tired mode: 3 easy Anki cards or 3 minutes. Stop after that.
```

### `block-plan`

Broader planning for the next work block.

Should produce:

- situation assessment
- friction hypothesis
- recommended next action
- possible question
- proposed tasks
- nudge

### `daily-review`

Future longer mode.

Should eventually produce:

- diary draft
- summary of actual behavior
- pattern detection
- reflection questions
- tomorrow’s first block
- learning notes

### Model routing

The long-term design should support per-mode model routing:

```text
help-now:
  fastest reliable small model or fallback

block-plan:
  stronger local model

daily-review:
  slower/stronger model acceptable

vision:
  future vision model
```

The fallback must remain permanent even if model quality improves.

---

## 6.12 `anki-bridge/`

Anki status bridge.

Service:

```text
anki-bridge.service
```

Responsibilities:

- query AnkiConnect
- collect configured deck stats
- write compact status
- optionally create/update an Anki recovery TaskNote

Important outputs:

```text
AI/anki/status.json
AI/anki/status.md
TaskNotes/AI/anki-due-recovery.md
```

Tracked information:

- due count
- new count
- learning count
- review due
- reviewed today
- again today
- deck priority
- suggested recovery goal

Design principle:

For Anki, objective progress proof is better than photo proof.

Future improvements:

- session start/end Anki delta
- weak deck detection
- repeated failure detection
- card rewrite suggestions
- language vocabulary export
- Anki-based known vocabulary for mixed-language prompts

---

## 6.13 `ollama/`

Local model runtime configuration.

Responsibilities:

- enable local Ollama
- configure model preloading
- provide local model endpoint for planner

Current default model is around the planner’s existing local model configuration.

Future work:

- benchmark help-now models
- configure per-mode model options
- reduce help-now timeout
- keep memory pressure manageable
- optionally add vision model only when screenshot/vision module exists

---

## 6.14 `browser-bridge/`

Future/placeholder module.

Intended responsibilities:

- collect active browser domain/title/URL
- distinguish browser container from actual content
- classify domains relative to session policy
- detect YouTube learning-video candidates
- identify YouTube Shorts as separate from normal YouTube
- optionally support strict-mode tab actions later

Important design example:

```text
Task:
  Watch design lecture and extract ideas

Allowed:
  youtube.com current lecture
  wikipedia.org
  Obsidian

Distracting:
  youtube.com/shorts
  unrelated recommendations
  reddit.com
```

Do not treat all browser use as either good or bad.

The active session determines meaning.

---

## 6.15 `notifications/`

Notification support module.

Current/future responsibilities:

- provide notification tooling
- avoid hardcoding notification dependencies everywhere
- eventually centralize notification style/urgency
- possibly route notifications differently by strictness/mode

---

## 6.16 `hypr-agent/`

Future/optional Hyprland integration.

Possible responsibilities:

- open correct apps
- focus specific windows
- show/hide future panel
- move panel to side of screen
- collect workspace context
- support intervention levels where the system opens helpful context

Strong actions must remain opt-in and authority-controlled.

---

## 6.17 `screenpipe/`

Future/optional screen context module.

Potential responsibilities:

- screenshot capture
- OCR/vision analysis
- visual proof
- desktop context summaries

Privacy warning:

Screenshot and visual monitoring must be explicit opt-in.

Avoid capturing sensitive contexts by default.

---

## 6.18 `compat/`

Compatibility layer.

Purpose:

- smooth migration from older file layouts/protocols
- avoid breaking existing state during refactors

Long-term direction:

As the system is still in active development and old Tasker/Obsidian integrations are being removed, compatibility should be kept minimal.

Prefer clean protocol over carrying obsolete behavior.

---

## 7. Vault protocol paths

The vault path is configured as:

```text
/home/daniil/Sync/Perseverance.Gu
```

The AI protocol directory is:

```text
/home/daniil/Sync/Perseverance.Gu/AI
```

Important runtime paths:

```text
AI/control/
AI/state/
AI/events/
AI/logs/
AI/inbox/
AI/outbox/
AI/anki/
AI/policy/
AI/protocol/
AI/schemas/
AI/reports/
AI/proposed-tasks/
AI/proofs/
AI/tasker/
AI/templates/
```

### 7.1 `AI/control/`

Human-readable current control state.

Important files:

```text
current-task.md
current-mode.md
current-block.md
```

These are useful for quick Obsidian inspection.

### 7.2 `AI/state/`

Machine-readable current state.

Important folders:

```text
state/session/
state/desktop/
state/phone/
state/llm/
state/action-bridge/
```

State files answer:

```text
What is true now?
```

### 7.3 `AI/events/`

Append-only normalized event logs.

Important folders:

```text
events/desktop/
events/phone/
events/actions/
events/anki/
```

Event files answer:

```text
What happened?
```

### 7.4 `AI/inbox/`

Queue folders.

Important queues:

```text
inbox/actions/
inbox/actions-processed/
inbox/actions-failed/

inbox/from-phone/events/
inbox/from-phone/processed/
inbox/from-phone/failed/

inbox/from-desktop/events/
inbox/from-desktop/processed/
inbox/from-desktop/failed/
```

Inbox files should be transient.

Processed files are retained for debugging.

Failed files should include error text where possible.

### 7.5 `AI/outbox/`

Files intended for other surfaces.

Important current files:

```text
outbox/to-phone/current-nudge.md
outbox/to-phone/current-question.md
outbox/to-phone/current-task.md
outbox/to-phone/proof-request.md
```

Future structured files:

```text
outbox/to-phone/current-nudge.json
outbox/to-phone/current-question.json
outbox/to-phone/interaction-state.json
```

Markdown is for humans.

JSON should be for Tasker and other automation.

---

## 8. Functional requirements mapped to implementation

### FR-SESSION-001 — start session from multiple sources

Partially implemented.

Current sources:

- terminal command
- Obsidian-generated actions/session requests
- Tasker-generated canonical actions
- manual JSON action files

Future sources:

- TaskNotes action
- schedule
- desktop panel

### FR-SESSION-002 — write session state/control files

Implemented.

Files:

```text
AI/state/session/current.json
AI/state/session/current-policy.json
AI/state/session/current-policy.md
AI/control/current-task.md
AI/control/current-mode.md
AI/control/current-block.md
```

### FR-SESSION-003 — derive session policy

Implemented as deterministic v0.

Future: richer policy compiler.

### FR-MON-001 — monitor desktop active window

Implemented through ActivityWatch + coach.

### FR-MON-004 — accept phone events through Syncthing inbox

Implemented through phone-bridge.

### FR-COACH-001 — classify activity

Implemented.

Verdicts:

```text
on_task
off_task
idle
unknown
no_plan
```

### FR-COACH-002 — fresh window activity usable even if AFK stale

Implemented conceptually.

AFK stale should not automatically block window classification.

### FR-LLM-001 — help-now mode

Implemented.

Includes deterministic fallback.

### FR-LLM-002 — block-plan mode

Implemented.

May need further quality/model tuning.

### FR-LLM-003 — daily-review mode

Service exists / planned; quality and prompt behavior still future work.

### FR-DIALOG-001 — pending questions

Implemented via:

```text
AI/state/llm/pending-question.json
```

Future: canonical `answer_question` action.

### FR-PHONE-001 — phone receives current nudge

Implemented as Markdown.

Future: JSON outbox.

### FR-PHONE-004 — phone writes responses

Partially implemented through canonical actions/check-ins.

Future: explicit `answer_question`.

### FR-TASK-002 — create proposed tasks first

Implemented through planner output.

Real TaskNotes mutation still future/authority-gated.

### FR-PROOF-001 — support context-aware proof

Not implemented yet.

### FR-EXP-001 — track intervention effectiveness

Not implemented yet.

---

## 9. Software requirements mapped to components

### Component: `vault-bridge`

Status: implemented.

Owns:

- base folder structure
- seed files

### Component: `activitywatch`

Status: implemented.

Owns:

- ActivityWatch server/watcher integration

### Component: `coach-daemon`

Status: implemented.

Owns:

- desktop classification
- immediate rule-based notifications

### Component: `anki-bridge`

Status: implemented.

Owns:

- Anki status collection

### Component: `phone-bridge`

Status: implemented.

Owns:

- passive phone telemetry only

### Component: `action-bridge`

Status: implemented / still expanding.

Owns:

- canonical intentional actions

### Component: `llm-planner`

Status: implemented / still improving.

Owns:

- local model planning
- help-now fallback
- nudges/questions/reports

### Component: `dialog-bridge`

Status: implemented but should become thinner.

Owns currently:

- desktop question UI

Future:

- delegate lifecycle to action bridge

### Component: `session-manager`

Status: implemented v0.

Owns:

- session object
- deterministic policy compiler

### Component: `browser-bridge`

Status: future/placeholder.

### Component: `language-bridge`

Status: future.

### Component: `proof-bridge`

Status: future.

### Component: `reflection-bridge`

Status: future.

### Component: `desktop-panel`

Status: future.

---

## 10. Non-functional requirements

### NFR-001 — Local-first

The system should remain useful without cloud services.

Implemented direction:

- local files
- local Python services
- local Ollama
- Syncthing-compatible file protocol

### NFR-002 — Inspectability

Every important state should be visible as JSON/Markdown.

Implemented direction:

- `AI/state/**/*.json`
- `AI/state/**/*.md`
- JSONL event logs
- processed/failed queues

### NFR-003 — Safe degradation

If LLM fails, deterministic fallback should still help.

Implemented for help-now.

### NFR-004 — Modularity

Each module should have narrow responsibility.

Improving.

Recent direction:

- extracted bridge scripts from inline Nix where possible
- shared `ai_system` utilities
- strict action/event separation

### NFR-005 — Privacy

Sensitive monitoring should be opt-in.

Current system avoids global keylogging/screenshots.

Future modules must treat these as high-risk:

- screenshots
- keystrokes
- browser content
- private messages
- sensitive apps

### NFR-006 — Latency

Targets:

```text
coach-daemon:
  seconds

help-now fallback:
  under 1 minute

help-now LLM:
  ideally under 45 seconds

block-plan:
  under 4 minutes

daily-review:
  slower acceptable
```

### NFR-007 — Reproducibility

Services and options should be declared through Nix.

Implemented direction:

- NixOS module per component
- systemd user services
- package paths fixed through Nix

### NFR-008 — Recoverability

Bad output should not erase useful state.

Implemented direction:

- preserve previous planner outputs on failure
- write last-error
- use processed/failed queues
- atomic writes

### NFR-009 — User override

Future requirement.

The user must be able to override/disable interventions.

### NFR-010 — Low friction

Current direction:

- Tasker actions
- Obsidian templates
- current nudge
- one-tap check-ins

Future:

- phone notification buttons
- desktop side panel
- structured outbox JSON

---

## 11. Current best next milestone

The next recommended milestone is:

```text
Outbound Phone Interaction Protocol v1
```

Reason:

The input side is mostly in place:

```text
phone / Obsidian / desktop
→ actions/events
→ bridges
→ session/planner/coach state
```

The missing half is structured output and response:

```text
planner / coach
→ current nudge/question JSON
→ phone notification/widget
→ one-tap answer
→ action-bridge answer_question
→ help-now adapts
```

Concrete next implementation:

```text
1. Planner writes:
   AI/outbox/to-phone/current-nudge.json
   AI/outbox/to-phone/current-question.json

2. Action bridge supports:
   answer_question
   ack_nudge
   dismiss_question

3. Question lifecycle becomes protocol-level:
   state/llm/pending-question.json
   outbox/to-phone/current-question.json
   answer_question action
   archive answered question
   trigger help-now

4. Tasker v4 reads JSON outbox files.
```

This should happen before:

- browser bridge
- screenshots
- proof bridge
- TaskNotes mutation
- language learning
- strictness experiments

Because all of those become more useful after the system can reliably ask and receive answers on the phone.

---

## 12. Example future workflows

### 12.1 Anki recovery session

User taps phone widget:

```text
AI Action Start Anki Recovery
```

Tasker writes:

```text
AI/inbox/actions/<timestamp>_action-start-anki-recovery.json
```

Action bridge starts session:

```text
task: Anki Language recovery
mode: anki
duration: 25
strictness: 2
```

Session manager writes policy:

```text
allowed apps:
  Anki
  Obsidian
  kitty

distracting apps:
  zen-beta
  org.telegram.desktop
  steam

distracting titles:
  YouTube
  Reddit
  Telegram
  TikTok
```

Coach monitors.

If user opens Anki:

```text
verdict: on_task
no interruption
```

If user opens YouTube:

```text
verdict: off_task
notification:
  “Off task? Return to: Anki Language recovery”
```

If user taps:

```text
AI Action Check In Overwhelmed
```

Planner help-now writes:

```text
Overwhelmed mode: 5 Anki cards or 5 minutes. Stop after that.
```

### 12.2 Learning video session

User starts:

```text
mode: learning-video
task: Watch learning video and write reflection
```

Policy allows:

```text
youtube.com
youtu.be
Obsidian
```

But still flags:

```text
youtube.com/shorts
music video
lyrics
unrelated recommendations
```

Future browser bridge detects:

```text
watched meaningful video for 18 minutes
```

System asks:

```text
Want to turn this into a note?
[Yes] [Later] [No]
```

If yes, future reflection bridge creates note prompt:

```text
What was the main idea?
What can I apply?
What should I research next?
```

### 12.3 Diary assistant

At daily review time, the system has evidence:

- sessions started
- sessions ended
- Anki due/reviewed
- phone unlocks
- check-ins
- off-task moments
- learning videos
- proof submissions
- notes created

Future daily-review generates:

```markdown
# Daily diary draft

## What happened

- Started Anki recovery.
- Answered “overwhelmed” during evening session.
- Returned to Anki after a YouTube distraction.
- Completed at least one small recovery block.

## Possible pattern

You recovered better when the task was reduced to 5 cards / 5 minutes.

## Questions

- What made Anki feel overwhelming?
- Did the reduced block help?
- What should tomorrow’s first block be?
```

The diary assistant must not fabricate.

Use phrases like:

```text
possible pattern
seems likely
evidence suggests
unknown
```

when uncertain.

### 12.4 TaskNotes proposal and promotion

Future planner sees:

```text
Anki backlog high
several overwhelmed check-ins
no completed recovery block today
```

It creates proposed task:

```markdown
# Proposed Tasks - 2026-05-04

## Tiny Anki recovery block

Priority: high
Estimate: 5 min
Project: Anki Recovery

Reason:
Repeated overwhelm suggests tomorrow should start with a smaller recovery block.
```

Later, user promotes it to real TaskNote.

Authority level increases only after trust is established.

### 12.5 Language-aware prompting

Future language bridge reads known vocabulary from Anki.

If user is stable/reflective:

```text
Réponds en français: qu’est-ce qui bloque maintenant?
```

If user is overwhelmed:

```text
What is blocking you now?
[Overwhelmed] [Tired] [Unclear]
```

Language learning must not increase friction during dysfunction states.

---

## 13. Authority model

The system should have explicit authority levels.

Recommended model:

```text
0 read only
1 proposed tasks only
2 create low-risk tasks
3 reschedule existing tasks
4 modify task details
5 delete/archive tasks
```

Deletion should be extremely conservative.

Strong interventions should also be authority-gated:

```text
A notify/suggest
B open helpful app/note
C close distracting webpage after warning
D block distracting domains during study
E trigger phone restrictions through Tasker
F modify TaskNotes/schedule directly
```

Current system should stay mostly at:

```text
A notify/suggest
B maybe open helpful surfaces later
```

No blocking/closing/deleting until the protocol is mature and opt-in.

---

## 14. Privacy model

The project may eventually support sensitive monitoring, but should start from safer sources.

Preferred safe sources:

- explicit actions/check-ins
- ActivityWatch app/title
- Anki status
- Obsidian files
- TaskNotes files
- browser domain/title only
- proof files explicitly submitted by user
- compiler/linter errors
- explicit clipboard/manual capture

High-risk sources:

- global keylogging
- screenshots
- OCR of screen
- browser page content
- chat messages
- password fields
- private messages
- banking/medical/legal pages

High-risk modules should require:

```text
explicit opt-in
visible state files
sensitive app exclusion list
short raw retention
summary extraction
raw deletion after analysis
manual override
```

---

## 15. Development principles

### 15.1 Prefer explicit protocols over magic

Do not rely on hidden behavior.

A file should make clear:

- who wrote it
- what schema it uses
- what event/action it represents
- when it was created
- which session it relates to, if any

### 15.2 Prefer append-only logs for history

Current state belongs in `state/`.

History belongs in `events/`.

Raw queue files belong in `inbox/*-processed` or `inbox/*-failed`.

### 15.3 Prefer atomic writes

State files should be written atomically where possible:

```text
write tmp
replace final
```

This matters because Syncthing, Tasker, and services may read concurrently.

### 15.4 Prefer stable queues

Bridge services should not process files while they may still be syncing/writing.

Use stability delays for inbox files.

### 15.5 Do not silently discard bad input

Bad input should go to failed queues with error messages.

Silent failure destroys trust.

### 15.6 Avoid pycache in git

Python bytecode and `__pycache__` should not be tracked.

### 15.7 Keep Nix wrappers thin

Prefer:

```nix
pkgs.writeShellScriptBin "service-name" ''
  export PYTHONPATH="..."
  exec ${pkgs.python3}/bin/python3 ${./script.py} "$@"
''
```

Avoid embedding large Python scripts inline in Nix unless there is a strong reason.

### 15.8 Keep bridge scripts domain-specific

Shared mechanics belong in `python/ai_system/`.

Bridge scripts should say what they do, not reimplement queue/event helpers.

---

## 16. Debugging commands

From the vault:

```sh
cd /home/daniil/Sync/Perseverance.Gu
```

### Current session

```sh
jq . AI/state/session/current.json
jq . AI/state/session/current-policy.json
cat AI/state/session/current-policy.md
```

### Desktop state

```sh
cat AI/state/desktop/now.md
jq . AI/state/desktop/now.json
tail -20 AI/events/desktop/$(date +%F).jsonl | jq
```

### Phone telemetry

```sh
cat AI/state/phone/latest.md
jq . AI/state/phone/latest.json
tail -20 AI/events/phone/$(date +%F).jsonl | jq
find AI/inbox/from-phone/events -maxdepth 1 -type f
find AI/inbox/from-phone/failed -type f | sort | tail
```

### Actions

```sh
cat AI/state/action-bridge/status.md
tail -20 AI/events/actions/$(date +%F).jsonl | jq
find AI/inbox/actions -maxdepth 1 -type f
find AI/inbox/actions-processed -type f | sort | tail
find AI/inbox/actions-failed -type f | sort | tail
```

### Planner

```sh
cat AI/state/llm/planner-status.md
cat AI/state/llm/last-output.md
cat AI/state/llm/last-error.md
cat AI/outbox/to-phone/current-nudge.md
cat AI/outbox/to-phone/current-question.md
```

### Anki

```sh
cat AI/anki/status.md
jq . AI/anki/status.json
```

From the NixOS repo:

```sh
cd /home/daniil/NixOS
```

### Compile all Python

```sh
nix run nixpkgs#python3 -- -m py_compile \
  $(find modules/programs/ai -name '*.py' -not -path '*/__pycache__/*' | sort)
```

### Build system

```sh
nix --extra-experimental-features "nix-command flakes" build \
  /home/daniil/NixOS#nixosConfigurations.Default.config.system.build.toplevel \
  --no-link
```

### Service health

```sh
systemctl --user status productivity-coach.service --no-pager
systemctl --user status phone-bridge.service --no-pager
systemctl --user status anki-bridge.service --no-pager
systemctl --user status ai-action-bridge.path --no-pager
systemctl --user status ai-action-bridge.service --no-pager
systemctl --user status llm-planner-help-now.service --no-pager
```

---

## 17. Common failure modes

### 17.1 Action appears in phone latest as `unknown`

Likely cause:

An action file was written to:

```text
AI/inbox/from-phone/events/
```

instead of:

```text
AI/inbox/actions/
```

Correct contract:

```text
AI Action ... -> AI/inbox/actions/
AI Event ...  -> AI/inbox/from-phone/events/
```

### 17.2 Path unit start-limit hit

Symptom:

```text
start of the service was attempted too often
```

Fix:

```sh
systemctl --user reset-failed ai-action-bridge.service ai-action-bridge.path
systemctl --user start ai-action-bridge.service
```

Design mitigation:

- process all pending actions in one service run
- raise StartLimitBurst for path-triggered oneshot services
- avoid many rapid partial writes

### 17.3 Help-now uses fallback

Symptom:

```text
Status: completed_fallback
```

This is acceptable.

It means the LLM failed or timed out, but deterministic help-now still wrote a nudge.

### 17.4 Coach says `unknown` for Obsidian/electron

Likely cause:

ActivityWatch reports Obsidian as `electron`, and title/policy did not match.

Fix options:

- add `electron` carefully where appropriate
- improve app normalization
- match Obsidian title keywords
- future: window class mapping

### 17.5 Browser is misclassified

Expected for now.

Until browser bridge exists, classification is based on app/title only.

### 17.6 Stale AFK

Symptom:

```text
AFK event stale: True
```

This is not always fatal.

Fresh window activity can still be useful.

---

## 18. Roadmap

### Phase 0 — Foundation

Mostly implemented.

- vault protocol
- ActivityWatch integration
- coach daemon
- Anki bridge
- phone bridge
- LLM planner
- dialog bridge
- session manager
- deterministic help-now fallback
- action bridge
- Tasker action/event direction

### Phase 1 — Stabilize protocols

Current/near-term.

- strict phone action/event contract
- shared Python utilities
- JSON schemas/examples
- robust processed/failed queues
- action bridge burst robustness
- remove obsolete compatibility behavior
- update README/protocol docs

### Phase 2 — Outbound phone interaction

Recommended next milestone.

- `current-nudge.json`
- `current-question.json`
- `interaction-state.json`
- `answer_question` action
- `ack_nudge` action
- Tasker reads structured outbox
- phone notification buttons answer active question

### Phase 3 — Model routing and planner reliability

- per-mode model config
- benchmark help-now models
- smaller/faster help-now model
- preserve fallback
- improve context packing
- improve planner quality checks

### Phase 4 — Browser/media bridge

- active URL/domain/title
- YouTube learning vs distraction
- Shorts detection
- learning video candidate logs
- “turn this into a note?” prompt
- transcript support later

### Phase 5 — TaskNotes proposal/promote pipeline

- read long-term plans
- generate proposed tasks
- promote proposed tasks manually
- audit trail
- authority levels

### Phase 6 — Reflection and diary assistant

- daily diary draft
- evidence-based summaries
- pattern detection
- learning reflection questions
- tomorrow first-block recommendation

### Phase 7 — Proof bridge

- proof request JSON
- phone proof submission
- proof artifact storage
- proof-task/session linking
- proof-aware daily review

### Phase 8 — Language learning integration

- known vocabulary export from Anki
- French/Chinese/elevated English prompt modes
- adaptive difficulty based on state
- mistake extraction from safe sources

### Phase 9 — Experiment engine

- intervention effectiveness metrics
- strictness experiments
- stress/avoidance tracking
- reversible visible experiments

### Phase 10 — Desktop panel

- right-side Disco Elysium style panel
- current nudge/question
- answer input
- recent events
- reasoning/context display
- command input
- calm hidden state

---

## 19. Design north star

The system should eventually make this workflow feel natural:

```text
I start a session from phone or Obsidian.

The system knows what I intend to do.

It watches enough context to notice obvious drift.

It does not nag when I am doing the right thing.

If I get stuck, I can answer one button:
  overwhelmed / tired / unclear / doing ok

The system adapts immediately:
  smaller task
  lower friction
  clearer next action

At the end of the day, it can summarize what actually happened.

Over weeks, it learns:
  what works
  what fails
  when strictness helps
  when strictness backfires
  which tasks need smaller starts
  which learning material should become notes/cards
```

The goal is not to maximize raw productivity.

The goal is to build an inspectable, local, adaptive scaffold for agency, recovery, learning, and long-term development.

---

<!-- AI-DOCS-CURRENT-STATE:START -->

## Current protocol state: phone interaction and recovery targets

The current near-term architecture is:

```text
desktop / planner / recovery logic
→ structured phone outbox JSON
→ Tasker/WebView phone UI
→ canonical action JSON
→ action-bridge lifecycle update
→ inspectable state/events
```

Important docs:

```text
PHONE_INTERACTION_PROTOCOL.md
RECOVERY_TARGET_LOOP.md
action-bridge/README.md
llm-planner/DESIGN_NOTES.md
```

### Implemented phone interaction protocol

The system now uses structured phone outbox files:

```text
AI/outbox/to-phone/current-nudge.json
AI/outbox/to-phone/current-question.json
AI/outbox/to-phone/interaction-state.json
```

Markdown mirrors remain useful for human reading, but JSON is the canonical phone protocol.

Current canonical response actions include:

```text
ack_nudge
snooze_nudge
answer_question
dismiss_question
start_recovery_target
```

The phone/Tasker side should remain a UI adapter. It reads outbox JSON, renders the interaction, writes action JSON, and optionally launches Android apps through small Tasker tasks.

### Recovery target loop

The Anki flow is now treated as the first instance of a generic recovery target loop, not as a special Anki-only architecture.

Current loop:

```text
recovery nudge
→ Start Anki
→ start_recovery_target action
→ AnkiDroid launch
→ AI/state/recovery/current.json
→ active nudge consumed
```

The goal is to support a reusable pattern:

```text
stuck / no-plan / off-task
→ offer tiny recovery action
→ one tap opens the right tool
→ observe follow-through
→ adapt future intervention
```

Future recovery targets may include coding, writing, reading, admin, language practice, exercise, and TaskNotes cleanup.

### Current implementation status

Implemented:

```text
canonical action bridge
strict action/event inbox separation
structured phone outbox JSON
Tasker/WebView phone card
ack/snooze/answer/dismiss question lifecycle
start_recovery_target
initial recovery state
stale completed-session filtering in action/planner context
deterministic help-now fallback
```

Pending before automatic nudges:

```text
recovery lifecycle end states
rapid-exit detection
possible_success / possible_abort / expired classification
automatic deterministic recovery nudge trigger
multi-target recovery policy
```

Design rule:

```text
Before target app:
  help start

Inside target app:
  stay quiet

After rapid exit or failure:
  ask what made it hard

After plausible success:
  record evidence and leave user alone
```

<!-- AI-DOCS-CURRENT-STATE:END -->

