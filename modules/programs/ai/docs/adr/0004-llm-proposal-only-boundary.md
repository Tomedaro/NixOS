# ADR 0004 - LLM proposal-only boundary

## Status

Accepted

## Context

The project is a local-first adaptive AI goal-achievement companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

LLM-facing paths may propose and draft but not execute or mutate durable state.

## Consequences

Reduces hidden agency and keeps authority explicit.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
