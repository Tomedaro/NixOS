# Future Capabilities and Modularity

This note records forward-looking research for what modern LLMs, neural networks, and agent frameworks make possible for this project.

It is not an implementation plan by itself. It is a design horizon: what the architecture should be ready to absorb without losing clarity, safety, or user control.

## Main conclusion

The project should not be a fixed bundle of bridges.

It should become a modular local-first goal-achievement operating layer.

Modern LLMs and neural systems make it possible to build:

- semantic memory;
- structured proposal generation;
- multimodal context understanding;
- tool-using agents;
- specialized small classifiers;
- goal and blocker detection;
- plan decomposition;
- adaptive interventions;
- voice and image capture;
- evaluators and model-based graders;
- local/private model adapters;
- integration servers for future tools.

The architecture should make these additive.

The right design is not:

```text
one giant autonomous agent
```

The right design is:

```text
small deterministic kernel
+ typed capability modules
+ proposal-side model intelligence
+ review surfaces
+ bounded action adapters
+ outcome evaluators
```

## Modern capabilities now relevant

### Structured outputs

LLMs can now produce schema-bound outputs much more reliably than older free-text prompting patterns.

Use this for:

- goal extraction;
- blocker classification;
- next-action proposals;
- task draft candidates;
- daily review summaries;
- intervention decisions;
- user preference updates;
- outcome summaries.

Design rule:

> Every model output that influences software behavior should cross a schema boundary.

Free text is fine for explanation. Structured output is needed for downstream action.

### Function calling and tools

LLMs can call tools with structured arguments.

Use this carefully for:

- read-only context lookup;
- semantic memory retrieval;
- local search;
- proposal drafting;
- explanation generation;
- evaluation helpers.

Do not expose dangerous tools directly.

Bad:

```text
LLM -> write TaskNotes
```

Better:

```text
LLM -> propose TaskNotes draft -> user review -> deterministic apply gate
```

### MCP-style integrations

Model Context Protocol points toward a future where external capabilities are exposed through standard tool/context/resource servers.

This matters because the user's future instruments may come from many places:

- local scripts;
- Obsidian;
- TaskNotes;
- Anki;
- ActivityWatch;
- calendar;
- browser;
- code workspace;
- phone;
- local databases;
- future custom tools.

The project should keep its boundaries compatible with this style:

- tools are explicit;
- resources are explicit;
- prompts/templates are explicit;
- capabilities are discoverable;
- authority is not implicit.

### Embeddings and semantic search

Embeddings make local semantic memory practical.

Use cases:

- find related goals;
- find similar past blockers;
- retrieve previous successful recovery patterns;
- cluster stale tasks;
- detect duplicate ideas;
- recommend next actions from similar contexts;
- group notes into themes;
- classify messages by similarity to known intents.

Design rule:

> Semantic search retrieves candidates; it does not decide truth.

Every retrieved memory should carry provenance, age, and relevance score where possible.

### Multimodal models

Modern models can understand images, screenshots, diagrams, UI state, audio transcripts, and scanned text.

Possible instruments:

- screenshot context summarizer;
- proof-of-work image classifier;
- voice capture to goal/task draft;
- handwritten note parser;
- browser/page summarizer;
- whiteboard/diagram interpreter;
- desktop state summarizer.

Design rule:

> Multimodal capture should be opt-in, minimized, and summarized into inspectable evidence.

### Local and specialized models

The project can use different models for different roles:

- local LLM for private low-risk summaries;
- stronger remote model for hard planning if explicitly enabled;
- embedding model for retrieval;
- small classifier for intent routing;
- reranker for memory retrieval;
- speech-to-text for voice capture;
- vision model for screenshots/proofs.

Design rule:

> The architecture should depend on task contracts, not one model provider.

A model should be swappable if it satisfies the module's input/output contract.

### Durable agent workflows

Longer workflows can pause for review, resume later, and record progress.

Relevant use cases:

- weekly goal review;
- multi-step planning;
- inbox triage;
- project decomposition;
- large note summarization;
- plan repair after failed execution;
- multi-day goal tracking.

Design rule:

> Long-running agentic work must be durable, idempotent, and resumable.

A workflow that may pause for user review should record state explicitly and avoid repeating side effects on resume.

### Handoffs and specialists

Instead of one agent doing everything, specialist modules can own different roles:

- goal strategist;
- next-action planner;
- recovery coach;
- TaskNotes draft normalizer;
- evidence summarizer;
- outcome evaluator;
- attention policy advisor;
- reflection assistant;
- code/work context summarizer.

Design rule:

> Specialist modules should communicate through schemas, not shared hidden prompt state.

### Model-based evaluation

LLMs can help evaluate outputs, but evaluation must be explicit.

Use cases:

- score whether a proposed next action is concrete;
- detect whether a nudge is judgmental;
- classify whether a plan is too large;
- check whether a proposal includes evidence;
- compare two possible interventions;
- evaluate daily review quality.

Design rule:

> Model graders are helpers, not unquestioned judges.

Pair model-based evals with deterministic checks and scenario examples.

### Prompt/program optimization

Frameworks such as DSPy point toward programming language-model pipelines instead of hand-maintaining brittle prompts.

This project can borrow the principle even without adopting the framework immediately:

- define signatures;
- define examples;
- define metrics;
- optimize against outcomes;
- keep prompts out of core logic;
- test model behavior as a module.

Design rule:

> Important LLM behavior should become a testable module with examples and metrics, not an invisible prompt blob.

## New functionality should be cheap to add

A future feature idea should usually require:

1. one new module directory;
2. one schema;
3. one small Nix option block if it has a service;
4. one test file;
5. one protocol entry;
6. one safety entry if it mutates anything;
7. one docs entry;
8. one evaluation scenario if it uses LLM behavior.

If a feature requires editing many unrelated modules, the extension boundary is wrong.

## Proposed module categories

### Context instruments

Read the world and summarize it.

Examples:

- ActivityWatch context;
- calendar context;
- TaskNotes read-only context;
- git work context;
- phone state;
- browser state;
- current focus/session state.

### Intelligence instruments

Think about the context and produce proposals.

Examples:

- goal decomposer;
- blocker detector;
- next-action generator;
- plan shrinker;
- recovery strategy selector;
- daily review summarizer.

### Memory instruments

Maintain inspectable personal model state.

Examples:

- recurring blocker memory;
- goal progress memory;
- preference hypotheses;
- intervention effectiveness memory;
- stale commitment memory.

### Action instruments

Perform bounded state changes.

Examples:

- ack nudge;
- snooze nudge;
- start recovery target;
- end session;
- write reviewed task draft;
- apply approved TaskNotes change.

### Interface instruments

Present and collect decisions.

Examples:

- Obsidian review;
- phone card;
- desktop notification;
- local web UI;
- terminal UI;
- voice capture.

### Evaluation instruments

Measure usefulness.

Examples:

- intervention outcome reporter;
- nudge fatigue report;
- stale goal report;
- next-action quality eval;
- review quality eval.

## Instrument manifest

Every instrument should eventually have a manifest.

Example:

```json
{
  "id": "attention.deep_work_guard",
  "kind": "attention_policy",
  "status": "planned",
  "goal": "Protect important focus sessions from unnecessary interruption.",
  "reads": [
    "AI/state/session/current.json",
    "AI/state/context/current.json"
  ],
  "writes": [
    "AI/state/attention/current.json"
  ],
  "may_mutate_tasknotes": false,
  "may_launch_apps": false,
  "llm_influence": "none",
  "authority": "state_summary",
  "schemas": [
    "attention_state.v1"
  ],
  "disable_switch": "my.ai.attention.deepWorkGuard.enable",
  "tests": [
    "tests/attention_deep_work_guard_smoke.py"
  ]
}
```

The manifest is the core modularity primitive.

## Capability composition

New functions should compose capabilities rather than inherit broad power.

Example composition:

```text
goal.weekly_review
  reads:
    - goal memory
    - TaskNotes read-only context
    - recent outcomes
  uses:
    - semantic retrieval
    - LLM summary
    - proposal normalizer
  writes:
    - Obsidian review proposal
  cannot:
    - mutate TaskNotes
    - launch apps
    - process live actions
```

Then a separate apply path handles accepted changes.

## Future-proofing against AI capability growth

Models will get better.

They will reason over longer contexts. They will use tools more reliably. They will see screens and hear audio more naturally. They will run longer workflows. They will become cheaper and more local. They will generate better code. They will personalize more.

The project should not respond by removing boundaries.

Better model capability should mean:

- better proposals;
- better explanations;
- better retrieval;
- better plans;
- better summaries;
- better evals;
- better detection of when not to act.

It should not mean:

- silent commitment mutation;
- hidden memory growth;
- broad tool authority;
- unreviewed automation;
- one giant agent running everything.

The more capable the model, the more valuable the boundaries become.

## Design patterns to adopt

### Ports and adapters

The core should define ports:

- read context;
- write proposal;
- request action;
- record outcome;
- retrieve memory;
- update policy.

Adapters connect those ports to files, Obsidian, phone, TaskNotes, models, or future tools.

### Evented architecture

Prefer explicit queue/event/state files over hidden calls.

This makes it easier to:

- inspect behavior;
- replay scenarios;
- test modules;
- add new consumers;
- debug failures.

### Schema-first interfaces

Every boundary should have a schema or documented shape.

This enables:

- model swapping;
- tests;
- validators;
- UI generation;
- review surfaces;
- migrations.

### Capability-based authority

A module should receive specific capabilities, not general trust.

### Human-in-the-loop by default for commitments

Anything that changes durable commitments should pass through review and deterministic apply.

### Evaluation-first LLM features

No new major LLM behavior should land without scenarios that define good and bad outputs.

## Research anchors

This design direction is informed by:

- Model Context Protocol: standard context/tool integration and composable workflows.
- Agent frameworks: agents, tools, orchestration, handoffs, guardrails, human review, state, and tracing.
- Structured outputs and function calling: typed model boundaries.
- Embeddings: semantic search, clustering, recommendations, and classification.
- Durable workflow systems: resumable, human-in-the-loop, idempotent workflows.
- DSPy-style modular AI programs: signatures, metrics, examples, and optimization instead of brittle prompt blobs.
- Human-AI interaction guidance: user control, behavior over time, graceful correction, mental models, and feedback.
- Evaluation guidance: continuous evaluation for variable generative systems.

## Practical next additions to docs/code

Suggested next documentation additions:

1. Add a capability registry document or JSON file.
2. Add an instrument template.
3. Add a module manifest template.
4. Add a new-instrument checklist to `DEVELOPMENT.md`.
5. Add planned capability names to `SAFETY_MODEL.md`.
6. Add extension lifecycle to `ROADMAP.md`.

Suggested next code additions after docs:

1. Define a simple instrument manifest schema.
2. Add a registry check script.
3. Add a smoke test that every module with side effects appears in the registry.
4. Add capability names to action bridge before adding new functionality.
5. Add a read-only TaskNotes context provider.
6. Add one small new instrument as a reference implementation.

## Strong opinion

The future should not be more automation for its own sake.

The future should be:

> More instruments, clearer contracts, better goal intelligence, stronger evaluation, and narrower authority.

That is how the project can become both smarter and more extensible.
