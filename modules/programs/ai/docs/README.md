# AI docs index

This directory contains audit detail, design review material, ADRs, and implementation backlogs for `modules/programs/ai`.

## Audit and restructuring

- `REVIEW_INVENTORY.md` - files, modules, tests, docs, paths, and ignored/generated material reviewed during the audit.
- `MODULE_REVIEW_REGISTER.md` - module-by-module review with purpose, inputs, outputs, side effects, tests, and issues.
- `ARCHITECTURE_FINDINGS.md` - architecture and logic findings with severity.
- `REFACTOR_BACKLOG.md` - implementation backlog ordered by safety and dependency.
- `DOC_RESTRUCTURE_PLAN.md` - documentation structure and ownership.

## Product intelligence

- `PRODUCT_INTELLIGENCE_FINDINGS.md` - gaps in adaptation, learning, attention, and controls.
- `PERSONAL_MODEL_AND_LEARNING_LOOP.md` - target learning loop and personal model shape.
- `GOALS_AND_COMMITMENTS.md` - goal hierarchy and commitment semantics.
- `ATTENTION_AND_RECOVERY_POLICY.md` - humane attention policy beyond TTL/cooldowns.
- `INTERACTION_DESIGN_AND_CONTROLS.md` - controls that let the user correct and steer the system.
- `PRODUCT_EVALUATION_PLAN.md` - eval layers and initial product scenarios.
- `QUALITY_SCENARIOS.md` - testable quality scenarios.
- `VOICE_AND_RELATIONSHIP_MODEL.md` - tone, relationship, and anti-pressure model.
- `POLICY_AND_CONFIGURATION_LIFECYCLE.md` - configuration precedence and policy evolution.
- `USER_JOURNEYS.md` - representative user journeys.
- `RESEARCH_TO_REQUIREMENTS_MATRIX.md` - research anchors translated into project requirements.

## Decisions

ADRs live in `docs/adr/`. They record decisions that should not be lost during refactors.

## Future capabilities and modularity

For future LLM/neural capabilities and modular extension design, read [FUTURE_CAPABILITIES_AND_MODULARITY.md](./FUTURE_CAPABILITIES_AND_MODULARITY.md) and [../EXTENSION_MODEL.md](../EXTENSION_MODEL.md).
