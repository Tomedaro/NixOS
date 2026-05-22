# Extension Model

This project should be easy to extend.

A good future version should let the user add new functionality, instruments, context sources, planners, review surfaces, action adapters, evaluators, memory modules, and model adapters without rewriting the core system or weakening its boundaries.

The core idea is:

> New functionality should be added as explicit capability modules around a small deterministic safety kernel.

The project should become more powerful by becoming more modular, not by letting every module reach into every file.

## Bridge, guardrail, and instrument vocabulary


The extension model uses three practical roles:

- **Bridge**: an adapter between an external/user-facing surface or subsystem and AI vault protocols. A bridge translates inputs and outputs, validates protocol shape, and records inspectable evidence. A bridge should not silently create durable commitments or invent broad authority.
- **Guardrail**: a deterministic safety boundary owned by the small safety kernel. A guardrail rejects unsafe, malformed, stale, over-broad, or authority-breaking inputs before they become durable actions.
- **Instrument**: a goal-achievement module. An instrument may observe, summarize, propose, classify, or act within declared limits. It must declare reads, writes, authority, schemas, tests, and disable behavior before being treated as active.

These roles can overlap in one directory during early development, but they should not be confused. Bridges adapt protocols. Guardrails enforce deterministic safety boundaries. Instruments pursue user goals within declared authority.

## Why modularity is seminal

The user's goals will change.

New tools will appear. New local models will become practical. New LLM capabilities will become normal. New phones, apps, vault workflows, sensors, review surfaces, and personal routines will become useful. The user will imagine instruments that do not exist yet.

The architecture must expect this.

If every new idea requires editing the action bridge, planner, phone bridge, TaskNotes logic, and docs at once, the system will become fragile. If each new instrument has a clear contract, authority level, schema, state path, test, and disable switch, the project can grow for years.

The system should be designed for curiosity:

- "I want a new instrument for language learning."
- "I want a goal review assistant."
- "I want a sleep-aware planning module."
- "I want an Obsidian capture classifier."
- "I want a code-work recovery coach."
- "I want an instrument that watches for stale goals."
- "I want a local model to summarize my day."
- "I want a phone widget that shows the most useful next action."
- "I want a model that detects when a plan is too large."
- "I want a weekly strategy review."

These should be additive modules, not invasive rewrites.

## Architectural north star

The extensible architecture should look like this:

```text
context providers
-> evidence ledger
-> memory and goal model
-> planner/proposal modules
-> review surfaces
-> safety kernel
-> bounded action adapters
-> outcome evaluators
-> learning updates
```

The safety kernel should stay small.

The kernel owns:

- schema validation;
- authority checks;
- idempotency;
- queue processing rules;
- TaskNotes mutation boundaries;
- action journaling;
- protocol versioning;
- dangerous-path tests.

Everything else should plug in around it.

## Capability module types

New functionality should usually fit one of these module types.

### Context providers

A context provider reads some source and emits bounded context.

Examples:

- Anki status provider;
- ActivityWatch provider;
- Obsidian goals provider;
- TaskNotes read-only provider;
- calendar provider;
- Git/work provider;
- sleep/energy proxy provider;
- phone state provider;
- browser/session provider.

Rules:

- context providers should be read-only by default;
- outputs should be schema-bound;
- raw data should be minimized;
- every output should include provenance and freshness;
- stale data should be marked stale, not silently trusted.

### Evidence collectors

An evidence collector records events that may matter later.

Examples:

- app opened/closed;
- recovery started;
- nudge shown;
- nudge dismissed;
- proposal approved;
- task draft created;
- session completed;
- goal reviewed.

Rules:

- events should be append-only evidence, not direct truth;
- event schemas should be versioned;
- events should identify source and timestamp;
- evidence should support later outcome analysis.

### Memory modules

A memory module turns evidence into useful, inspectable state.

Examples:

- recurring blocker detector;
- successful-time-of-day detector;
- repeated-ignore detector;
- stale-goal detector;
- goal progress summarizer;
- preference hypothesis generator.

Rules:

- memory should distinguish facts, hypotheses, preferences, policies, goals, commitments, and outcomes;
- memory should include confidence, provenance, freshness, and correction paths;
- weak hypotheses should not become hard policies automatically.

### Goal modules

A goal module helps represent, inspect, decompose, or revise goals.

Examples:

- goal hierarchy builder;
- goal-to-project decomposer;
- milestone recommender;
- next-action generator;
- goal conflict detector;
- scope shrinker;
- weekly goal review module.

Rules:

- goals should not automatically become tasks;
- plans should not automatically become commitments;
- goal suggestions should remain reviewable;
- every proposed commitment should retain a goal link.

### Planner/proposal modules

A planner proposes what might help next.

Examples:

- recovery planner;
- daily planning module;
- weekly review module;
- Anki habit planner;
- code-focus planner;
- backlog triage planner;
- energy-aware next-action planner.

Rules:

- planners propose; they do not mutate durable state directly;
- outputs should be structured;
- proposals should include goal link, reason, confidence, expiry, burden, and alternatives;
- planners should say why they are not proposing anything.

### Review surfaces

A review surface presents proposals and collects user decisions.

Examples:

- Obsidian review note;
- phone card;
- desktop notification;
- terminal summary;
- daily review page;
- local web dashboard.

Rules:

- review surfaces should make approval, rejection, revision, snooze, and "wrong inference" easy;
- they should show enough evidence to calibrate trust;
- they should not hide the difference between proposal, draft, and commitment.

### Action adapters

An action adapter performs a bounded side effect.

Examples:

- start recovery target;
- acknowledge nudge;
- snooze nudge;
- answer question;
- launch app through phone;
- write reviewed TaskNotes draft;
- eventually apply approved TaskNotes changes.

Rules:

- action adapters are authority surfaces;
- each adapter should declare required capability;
- dangerous adapters should default off;
- side effects should be idempotent where possible;
- all effects should be journaled.

### Evaluators

An evaluator decides whether an intervention, plan, or module helped.

Examples:

- intervention outcome reporter;
- goal progress evaluator;
- stale nudge evaluator;
- daily plan quality evaluator;
- user-burden evaluator;
- planner regression evaluator.

Rules:

- evaluators should use scenario tests and real outcomes;
- success should be measured against goals, not activity volume;
- wrong or annoying behavior should become negative training/evaluation signal.

### Model adapters

A model adapter connects to an LLM, local model, embedding model, classifier, speech model, or vision model.

Examples:

- local Ollama model adapter;
- remote LLM adapter, when explicitly enabled;
- embedding adapter;
- reranker adapter;
- speech-to-text adapter;
- vision/screenshot summarizer;
- small classifier adapter.

Rules:

- model adapters should be replaceable;
- callers should depend on task contracts, not model names;
- outputs should be structured when used by downstream code;
- model-specific prompts should not leak into core protocols.

## Module contract registry

The project should eventually have a lightweight module contract registry.

This is separate from `ACTION_CAPABILITY_POLICY`. `ACTION_CAPABILITY_POLICY` is the runtime action capability policy used by `action-bridge` when processing live actions. The module contract registry is a Markdown planning/docs artifact for modules, context providers, instruments, review surfaces, and adapters. It may reference `ACTION_CAPABILITY_POLICY` only when a module dispatches or requires live actions; read-only context providers should normally declare no required action capabilities.

Each module should declare:

```json
{
  "id": "goal.next_action_planner",
  "kind": "planner",
  "status": "current",
  "reads": [
    "AI/state/context/current.json",
    "TaskNotes read-only context"
  ],
  "writes": [
    "AI/outbox/to-obsidian/proposals/*.json"
  ],
  "authority": "proposal_only",
  "required_action_capabilities": [],
  "may_mutate_tasknotes": false,
  "schemas": [
    "goal_next_action_proposal.v1"
  ],
  "tests": [
    "tests/goal_next_action_planner_smoke.py"
  ],
  "docs": [
    "MODULES.md",
    "PROTOCOLS.md",
    "SAFETY_MODEL.md"
  ]
}
```

This module contract registry does not need to be complex at first. A Markdown table is enough for the first pressure test; do not add a JSON/YAML manifest or checker until the contract shape proves useful. The important thing is that every new module is explicit about what it reads, writes, may mutate, may influence, and which live action capabilities it requires, if any.

## Capability names instead of broad authority

The project should move away from one broad numeric authority level.

Prefer named capabilities:

```text
interaction.ack_nudge
interaction.snooze_nudge
interaction.answer_question
recovery.start_target
session.start
session.end
tasknotes.draft
tasknotes.apply_reviewed
tasknotes.promote_legacy
phone.launch_app
obsidian.write_review_artifact
memory.write_hypothesis
policy.update_user_rule
```

This makes it possible to add new instruments without giving them broad power.

A module should get exactly the capabilities it needs and no more.

## First pressure test: TaskNotes read-only context

Before implementing first-class read-only TaskNotes context, add a Markdown-only module contract for `tasknotes.read_context`. This pressure test should prove the registry shape without adding a JSON/YAML manifest, checker, or runtime provider.

Minimum planned contract:

- type: context provider;
- reads: bounded configured TaskNotes source paths and only the metadata needed for planning context;
- writes: bounded AI context output/artifacts only;
- authority: observe/read-only;
- `may_mutate_tasknotes`: false;
- `required_action_capabilities`: none;
- output requirements: provenance, freshness timestamp, source limits, truncation/omission markers, and stale/disabled status;
- tests: prove no TaskNotes writes, bounded output, provenance/freshness fields, limit handling, and safe-off/disabled behavior;
- non-goal: deterministic TaskNotes apply/promote remains separate planned work.

Because this provider does not dispatch live actions, its module contract should not reference `ACTION_CAPABILITY_POLICY` beyond stating that no action-bridge runtime action capability is required.

## Instrument contract

Every new instrument should answer these questions before implementation:

1. What user goal does it serve?
2. What type of module is it?
3. What context does it read?
4. What state or queue does it write?
5. Can it mutate live state?
6. Can it mutate TaskNotes?
7. Can an LLM influence it?
8. What schema does it output?
9. What is the review path?
10. What is the user control/correction path?
11. What proves it helped?
12. What test protects the dangerous behavior?
13. How can it be disabled?
14. What happens when it fails?

If these cannot be answered, the idea should remain a design note, not a live module.

## Plugin boundary

The project should favor a plugin-like boundary:

```text
module package
  default.nix
  README.md
  module.py or adapter.py
  schemas/
  tests/
  docs entry
```

A plugin should be able to register:

- context providers;
- proposal producers;
- action adapters;
- review surfaces;
- evaluation hooks;
- memory summarizers;
- state paths;
- service/timer units if needed.

At first, registration can be simple and manual. The long-term goal is predictable extension, not dynamic magic.

## Tool and instrument distinction

A tool is something a model can request.

An instrument is a project module that supports goal achievement.

Some instruments expose tools to an LLM. Many should not.

Examples:

- "read goal context" can be a tool;
- "summarize blockers" can be a model-backed instrument;
- "write TaskNotes" should not be a raw LLM tool;
- "prepare TaskNotes draft" can be a proposal instrument;
- "apply reviewed TaskNotes draft" should be a deterministic action adapter.

This distinction matters because LLM tool access is authority.

## Modern LLM capability map

The architecture should be ready to use modern neural capabilities in bounded ways.

### Structured extraction

Use LLMs to convert messy text into typed proposals, goals, blockers, and summaries.

Boundary:

- structured output is not truth;
- validators decide whether it is acceptable;
- review surfaces decide whether it becomes a commitment.

### Semantic memory

Use embeddings or local semantic indexes to find related goals, tasks, notes, blockers, and past outcomes.

Boundary:

- semantic similarity is a retrieval signal, not proof;
- retrieved memories need provenance;
- old memories need freshness and expiry.

### Multimodal understanding

Use vision, OCR, audio, and screen context when useful.

Possible instruments:

- screenshot summarizer;
- proof image classifier;
- handwritten-note extractor;
- voice capture transcriber;
- UI-state recognizer.

Boundary:

- multimodal outputs can be wrong;
- sensitive raw data should be minimized;
- summaries should link back to evidence when possible.

### Planning and decomposition

Use LLMs to decompose goals into projects, milestones, sessions, and next actions.

Boundary:

- plans are proposals;
- accepted commitments go through TaskNotes;
- repeated plan failure should trigger diagnosis, not repetition.

### Reflection and coaching

Use LLMs to summarize patterns and ask useful questions.

Boundary:

- coaching should be nonjudgmental;
- questions should be sparse and useful;
- user corrections should update hypotheses.

### Tool orchestration

Use agent patterns for multi-step work only when the workflow has clear state, handoffs, guardrails, and review.

Boundary:

- long-running workflows need durable state;
- side effects must be idempotent;
- risky steps need human review.

### Model specialization

Use different models for different roles:

- small local classifiers for cheap routing;
- embedding models for retrieval;
- stronger LLMs for complex planning when explicitly enabled;
- local LLMs for private summaries;
- speech/vision models for capture;
- deterministic code for final state mutation.

Boundary:

- the contract should outlive the model;
- modules should depend on schemas and capabilities, not one provider.

## Future instruments worth designing for

The system should make these easy to add later.

### Goal intelligence

- goal hierarchy map;
- goal conflict detector;
- goal progress summarizer;
- goal recommitment review;
- abandoned-goal detector;
- "is this still worth it?" reviewer.

### Planning intelligence

- next-action generator;
- milestone planner;
- implementation-intention planner;
- plan shrinker;
- blocker diagnosis module;
- energy-aware planner;
- time-window planner.

### Memory intelligence

- personal pattern detector;
- preference hypothesis tracker;
- recurring blocker register;
- "what worked before?" retriever;
- stale memory decay;
- user correction inbox.

### Attention intelligence

- interruption budget;
- quiet hours;
- deep-work detector;
- repeated-ignore backoff;
- channel selection;
- notification fatigue detector;
- "silence is best" policy.

### Execution support

- session starter;
- recovery target launcher;
- focus checklist;
- context packet builder;
- pre-work setup checker;
- task draft generator;
- post-session summarizer.

### Review and evaluation

- daily review;
- weekly strategy review;
- intervention usefulness review;
- goal progress dashboard;
- plan quality evals;
- stale task cleanup review.

### Interfaces

- Obsidian notes;
- phone card;
- desktop panel;
- terminal command;
- local web dashboard;
- voice capture;
- email/calendar adapters if explicitly enabled.

## Open integration standards

The project should watch standards like Model Context Protocol.

MCP's core idea is valuable here: separate hosts, clients, and servers; expose context and tools through a standard protocol; make integrations composable. This project does not need to become MCP-first immediately, but its module boundaries should be compatible with that world.

A future instrument should be able to become:

- an internal provider;
- a command-line tool;
- a local service;
- an MCP server;
- a model tool;
- an Obsidian workflow;
- a phone action.

Do not hardwire the first interface as the only interface.

## Evaluation as an extension boundary

Every new instrument should come with an evaluation plan.

For deterministic code:

- smoke test;
- invalid input test;
- idempotency test;
- path/schema test.

For LLM behavior:

- scenario eval;
- structured-output validation;
- regression cases;
- "wrong inference" cases;
- user-burden cases;
- goal-progress cases.

The system should not become more AI-powered without becoming more evaluated.

## Modularity rules

Use these rules when adding functionality:

1. Add a module, not a tangle.
2. Declare reads and writes.
3. Declare authority.
4. Use schemas at boundaries.
5. Keep LLMs proposal-side unless explicitly gated.
6. Keep TaskNotes mutation behind deterministic gates.
7. Make failure visible in files.
8. Add tests before relying on behavior.
9. Add docs before future contributors depend on it.
10. Make the module easy to disable.
11. Prefer composition over global state.
12. Prefer small instruments over one giant agent.
13. Prefer explicit queues over hidden callbacks.
14. Prefer stable contracts over provider-specific features.
15. Prefer "do nothing" over bad intervention.

## What should not happen

The project should avoid:

- one mega-agent with all authority;
- every module writing every path;
- LLM prompts as the only protocol;
- hidden memory updates;
- TaskNotes mutation from raw model output;
- untested side effects;
- stale docs pretending to be truth;
- hardcoded assumptions that make new instruments expensive;
- provider lock-in at the architecture level;
- adding automation faster than adding evaluation.

## Good extension example

A new "goal stale review" instrument should work like this:

1. A TaskNotes read-only provider emits current tasks and goal links.
2. A goal memory module identifies stale goals and old commitments.
3. A planner proposes a review note:
   - keep;
   - shrink;
   - defer;
   - delete;
   - recommit.
4. Obsidian shows the proposal.
5. The user approves a draft.
6. A deterministic apply gate writes only approved changes.
7. Outcomes are recorded.
8. The evaluator checks whether stale commitments decreased.

No raw LLM writes TaskNotes.
No broad authority is added.
The instrument is useful, bounded, and inspectable.

## Design north star

The system should become a modular goal-achievement platform:

> A local-first system where new instruments can be added as explicit, typed, testable capability modules that help the user reach goals while preserving inspectability, review, and human-owned commitments.

## Minimum module / instrument manifest


Before adding or enabling a new module/instrument, document:

- purpose and non-goals;
- owner surface: bridge, guardrail, instrument, or a clearly bounded combination;
- input paths and schemas read;
- output paths and schemas written;
- authority level and named action capability, if any; use `required_action_capabilities: none` for read-only providers that do not dispatch live actions;
- whether it can mutate local state, live queues, external apps, or durable commitments;
- reviewable proposal/draft behavior;
- disable switch or safe-off behavior;
- failure behavior and where errors are written;
- smoke/regression tests;
- observability: status files, events, or logs;
- current limitations and known unsafe paths.

A module that touches TaskNotes must remain reviewable-only unless a deterministic reviewed apply/promote gate exists.

## Removal and deprecation checklist


Before removing, disabling, or deprecating a module/instrument:

- identify all input and output paths it owns;
- identify services, timers, path units, templates, and generated files;
- preserve or migrate reviewable artifacts that humans may still need;
- update docs that describe current behavior;
- mark historical audit findings as resolved or superseded instead of deleting useful context;
- add or update regression coverage proving unsafe behavior stays disabled;
- remove or hard-disable authority wiring before removing explanatory docs;
- confirm generated bundles and handoff docs no longer advertise stale behavior.

Historical direct mutation paths should remain removed or disabled; new durable writes should use deterministic reviewed apply/promote.
