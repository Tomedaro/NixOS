# ADR 0002 - Obsidian as review surface

## Status

Accepted

## Context

The project is a local-first adaptive AI productivity companion. It must be inspectable, recovery-oriented, explicit about authority, and careful with durable state and TaskNotes.

## Decision

Use Obsidian as the human review and interaction surface.

## Consequences

Keeps human review visible and avoids hidden execution.

## Alternatives considered

- Allow broader hidden automation. Rejected because it weakens user control and inspectability.
- Keep the behavior only in informal README/TODO prose. Rejected because future contributors and LLMs need canonical decision records.

## Follow-up tasks

- Ensure `CURRENT_STATE.md`, `SAFETY_MODEL.md`, `PROTOCOLS.md`, and `ROADMAP.md` reflect this decision.
- Add tests before behavior changes that rely on this decision.
