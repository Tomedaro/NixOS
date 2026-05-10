# ADR 0005 - Split action authority

## Status

Proposed

## Context

The project is a local-first adaptive AI productivity companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

Replace or supplement coarse numeric authority with named capabilities.

## Consequences

Allows routine interaction actions without granting TaskNotes mutation authority.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
