# ADR 0006 - Deterministic TaskNotes apply/promote gate

## Status

Proposed

## Context

The project is a local-first adaptive AI productivity companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

Introduce a deterministic, explicit, idempotent gate for turning reviewed drafts/proposals into real TaskNotes.

## Consequences

Consolidates legacy/direct mutation paths behind a safer protocol.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
