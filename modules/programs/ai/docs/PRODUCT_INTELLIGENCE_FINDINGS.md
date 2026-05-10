# Product intelligence findings
## Verdict

The project has a strong architectural identity: local-first, inspectable, recovery-oriented, proposal-first, and bounded by explicit protocols. The earlier audit captured this reasonably well.

The under-covered dimension is product intelligence: how the system becomes better for this specific user without becoming noisy, opaque, controlling, or over-authoritative.

## What is already strong

1. The README states a mature product philosophy: the system should optimize sustainable goal progress and quality productive hours, and may choose rest, fallback planning, smaller steps, or silence.
2. The Obsidian/LLM proposal chain is well aligned with reviewable artifacts rather than silent execution.
3. The context hub and agent context already create a useful read-only substrate for future learning.
4. The intervention outcomes module already summarizes evidence conservatively and does not change policy itself.
5. The session manager provides deterministic policy seeds: allowed/disallowed apps, domains, proof types, reflection prompts, language level, and intervention cooldowns.

## What is not yet adequate

### 1. The adaptation story is aspirational, not designed end-to-end

The project talks about approved facts, inferred patterns, policies, goals, interventions, and outcomes. The implementation currently has providers, facts, derived facts, cooldowns, nudge/question state, and outcome summaries. It does not yet have a canonical learning loop with hypotheses, confidence, correction, expiry, experiments, or supersession.

### 2. The system measures response, not helpfulness

Current outcomes such as acknowledged, snoozed, started, shown_no_response, and possible_success are valuable, but they do not answer: did this help, was it burdensome, was it well-timed, did it preserve agency, did it make the next action clearer?

### 3. Goals are present as references, not as an operational hierarchy

Goal IDs can flow through Obsidian intents and TaskNotes drafts, but there is no documented hierarchy from values/life areas to goals, projects, commitments, sessions, interventions, and outcomes.

### 4. The attention model is too small

TTL and cooldowns are good mechanics, but they do not define quiet hours, deep-work suppression, attention budget, repeated-ignore backoff, channel switching, or low-energy behavior.

### 5. Controls are not expressive enough for learning

The system needs controls that produce structured feedback: wrong inference, less like this, more like this, this helped, felt pressuring, not now, never, explain why, show evidence, forget/supersede pattern.

### 6. Product evals are missing

Smoke tests validate mechanics. They do not validate humane behavior, timing, tone, evidence use, silence/defer choices, or learning from correction.

## Best treatment

Add a product intelligence layer to the documentation before implementation:

- define the learning loop;
- define personal model entities;
- define goal/commitment semantics;
- define attention policy;
- define controls and feedback events;
- define planner vNext metadata;
- define product eval scenarios;
- define the voice/relationship model.

This should be documentation and tests first, implementation second.

## Priority recommendations

1. Add product-quality maturity levels to the module review register: concept, scaffolded, mechanically implemented, tested, user-operational, adaptive/learning, deprecated.
2. Create `PERSONAL_MODEL_AND_LEARNING_LOOP.md` before adding new adaptive code.
3. Add optional planner metadata fields before requiring them.
4. Add eval scenarios before changing planner behavior.
5. Add feedback/control events before making adaptation automatic.
6. Treat silence as a first-class intervention.
7. Make all learning reversible and explainable.
