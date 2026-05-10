# ADR 0007 - Inspectable learning kernel

## Status

Proposed

## Context

The project is a local-first adaptive AI productivity companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

Model adaptation as evidence, hypotheses, proposals, feedback, outcomes, and revisions.

## Consequences

Prevents opaque personalization and keeps user correction central.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
