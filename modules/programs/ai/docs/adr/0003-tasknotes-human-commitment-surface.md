# ADR 0003 - TaskNotes as human commitment surface

## Status

Accepted

## Context

The project is a local-first adaptive AI productivity companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

Treat TaskNotes as durable human commitments, not an AI scratchpad.

## Consequences

AI must not silently mutate commitments; drafts/proposals are separate.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
