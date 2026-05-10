# Documentation transition manifest

## Intent

Replace sprawling and stale documentation with a canonical, safer documentation set. This transition is docs-only: no Python, Nix, service, or runtime behavior changes are included.

## Deleted top-level docs

- `TODO.md` - replaced by `ROADMAP.md` and `docs/REFACTOR_BACKLOG.md`.
- `AI_DEBUG_REFACTORING_TODO.md` - replaced by `docs/ARCHITECTURE_FINDINGS.md`, `docs/REFACTOR_BACKLOG.md`, and product-intelligence docs.

## Rewritten top-level docs

- `README.md`
- `AI_DOC_AUDIT_HANDOFF.md`
- `ARCHITECTURE.md`
- `DEVELOPMENT.md`

## Added canonical docs

- `CURRENT_STATE.md`
- `MODULES.md`
- `SAFETY_MODEL.md`
- `PROTOCOLS.md`
- `OPERATIONS.md`
- `ROADMAP.md`
- `GLOSSARY.md`
- `docs/README.md`
- audit, backlog, ADR, and product-intelligence docs under `docs/`.

## Safety properties preserved

- No code files changed.
- No Nix module files changed.
- No runtime queue/state/event files changed.
- Legacy/direct mutation paths are documented rather than removed in this docs-only patch.
- Future behavior changes remain gated behind review, tests, and verification.
