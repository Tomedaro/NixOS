# AI documentation details

This directory contains current architecture assessment, schema/module inventories, product-design notes, ADRs, and historical audit records.

Start with the top-level canonical docs:

- [Current state](../CURRENT_STATE.md)
- [Safety model](../SAFETY_MODEL.md)
- [Architecture](../ARCHITECTURE.md)
- [Protocols](../PROTOCOLS.md)
- [Modules](../MODULES.md)
- [Operations](../OPERATIONS.md)
- [Roadmap](../ROADMAP.md)
- [Extension model](../EXTENSION_MODEL.md)

## Current review and inventory documents

- [Architecture findings](./ARCHITECTURE_FINDINGS.md)
- [Review inventory](./REVIEW_INVENTORY.md)
- [Module review register](./MODULE_REVIEW_REGISTER.md)
- [Schema registry](./SCHEMA_REGISTRY.md)
- [Refactor backlog](./REFACTOR_BACKLOG.md)

## Product intelligence and design notes

- [Product intelligence findings](./PRODUCT_INTELLIGENCE_FINDINGS.md)
- [Personal model and learning loop](./PERSONAL_MODEL_AND_LEARNING_LOOP.md)
- [Goals and commitments](./GOALS_AND_COMMITMENTS.md)
- [Attention and recovery policy](./ATTENTION_AND_RECOVERY_POLICY.md)
- [Interaction design and controls](./INTERACTION_DESIGN_AND_CONTROLS.md)
- [Product evaluation plan](./PRODUCT_EVALUATION_PLAN.md)
- [Quality scenarios](./QUALITY_SCENARIOS.md)
- [Research to requirements matrix](./RESEARCH_TO_REQUIREMENTS_MATRIX.md)
- [User journeys](./USER_JOURNEYS.md)
- [Voice and relationship model](./VOICE_AND_RELATIONSHIP_MODEL.md)
- [Policy and configuration lifecycle](./POLICY_AND_CONFIGURATION_LIFECYCLE.md)
- [Future capabilities and modularity](./FUTURE_CAPABILITIES_AND_MODULARITY.md)

## Historical transition records

These explain how the current documentation set was created. They are not current implementation plans:

- [Documentation restructure plan](./DOC_RESTRUCTURE_PLAN.md)
- [Docs transition manifest](./DOCS_TRANSITION_MANIFEST.md)

## Decisions

ADRs live in [adr/](./adr/). The current first-loop direction is [ADR 0008 - Laptop-first task-initiation kernel](./adr/0008-laptop-task-initiation-kernel.md). Remaining non-blocking implementation selections live in [workflow/OPEN_QUESTIONS.md](../workflow/OPEN_QUESTIONS.md) and should become ADRs or durable decisions only when they materially change architecture or safety.
