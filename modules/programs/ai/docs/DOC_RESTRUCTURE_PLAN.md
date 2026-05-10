# Documentation restructure plan - draft

This file records the accepted audit draft for `modules/programs/ai/docs/DOC_RESTRUCTURE_PLAN.md`.

## Goal

Make the documentation truthful, modular, reviewable, and safe for future contributors/LLMs. Do not let old TODOs or mixed README sections override code/test reality.

## Proposed target structure

```text
modules/programs/ai/
  README.md
  CURRENT_STATE.md
  MODULES.md
  ARCHITECTURE.md
  SAFETY_MODEL.md
  PROTOCOLS.md
  OPERATIONS.md
  DEVELOPMENT.md
  ROADMAP.md
  GLOSSARY.md
  AI_DOC_AUDIT_HANDOFF.md

  docs/
    REVIEW_INVENTORY.md
    MODULE_REVIEW_REGISTER.md
    ARCHITECTURE_FINDINGS.md
    REFACTOR_BACKLOG.md
    DOC_RESTRUCTURE_PLAN.md
    adr/
      0001-local-first-ai-vault.md
      0002-obsidian-review-surface.md
      0003-tasknotes-human-commitment-surface.md
      0004-llm-proposal-only-boundary.md
      0005-split-action-authority.md
      0006-tasknotes-apply-promote-gate.md
```

## Document responsibilities

| Document | Responsibility |
|---|---|
| `README.md` | Orientation only: what the project is, how to navigate docs, safest first commands. |
| `CURRENT_STATE.md` | What is actually implemented now, with disabled/default status. |
| `MODULES.md` | Module ownership/responsibilities and side-effect classification. |
| `ARCHITECTURE.md` | Explanation, arc42-style structure, major design views. |
| `SAFETY_MODEL.md` | Authority levels, side-effect boundaries, invariants, dangerous/legacy paths. |
| `PROTOCOLS.md` | Exact path/schema/queue contracts. |
| `OPERATIONS.md` | Commands, diagnostics, runbooks, safe verification. |
| `DEVELOPMENT.md` | Contribution practices, testing, coding conventions. |
| `ROADMAP.md` | Planned work only, ordered by safety/dependency. |
| `GLOSSARY.md` | Canonical terms. |
| `AI_DOC_AUDIT_HANDOFF.md` | Persistent LLM instruction set; keep but avoid using it as user docs. |
| `docs/REVIEW_INVENTORY.md` | Evidence trail of reviewed/ignored files. |
| `docs/MODULE_REVIEW_REGISTER.md` | Detailed per-module audit register. |
| `docs/ARCHITECTURE_FINDINGS.md` | Ranked findings. |
| `docs/REFACTOR_BACKLOG.md` | Implementation backlog derived from findings. |
| `docs/DOC_RESTRUCTURE_PLAN.md` | This plan. |

## First documentation batch

Create these together so future readers have canonical truth immediately:

1. `CURRENT_STATE.md`
2. `SAFETY_MODEL.md`
3. `PROTOCOLS.md`
4. `MODULES.md`
5. `ROADMAP.md`
6. `docs/REVIEW_INVENTORY.md`
7. `docs/MODULE_REVIEW_REGISTER.md`
8. `docs/ARCHITECTURE_FINDINGS.md`
9. `docs/REFACTOR_BACKLOG.md`
10. `docs/DOC_RESTRUCTURE_PLAN.md`

Then shrink `README.md` into an orientation document pointing to those files.

## Migration rules

- Do not delete old content until each invariant is captured in a canonical doc.
- Do not say “future” for implemented-disabled code; say “implemented, disabled by default.”
- Do not say “safe” for legacy/direct mutation paths; say “legacy/direct; deprecated or pending consolidation.”
- Do not mix roadmap items into current-state docs.
- Do not encode AI review lifecycle as TaskNotes execution status.
- Every queue path in code must appear in `PROTOCOLS.md`.
- Every side-effect path must appear in `SAFETY_MODEL.md`.
- Every source module must appear in `MODULES.md`.

## Recommended doc writing order

1. `CURRENT_STATE.md` - freeze ground truth.
2. `SAFETY_MODEL.md` - freeze boundaries and legacy surfaces.
3. `PROTOCOLS.md` - freeze path contracts.
4. `MODULES.md` - module register for contributors.
5. `ROADMAP.md` - planned work only.
6. `OPERATIONS.md` - commands/runbooks.
7. `GLOSSARY.md` - terms.
8. ADRs - decision records.
9. `README.md` rewrite - entry point only.

## Consistency checks to add

Add a small dev script or checklist for:

- every directory created by `vault-bridge/default.nix` exists in `PROTOCOLS.md`;
- every `atomic_write_*` or queue-move target appears in `SAFETY_MODEL.md` or `PROTOCOLS.md`;
- every `*_smoke.py` appears in `OPERATIONS.md` or test list;
- every top-level module import appears in `MODULES.md`;
- no unmarked `AI/inbox/from-obsidian` legacy references remain outside diagnostics;
- no docs say TaskNotes apply is purely future without mentioning existing legacy/direct paths.

## Transition status

This clean documentation transition has been applied in the rewritten docs tree:

- canonical top-level docs now exist;
- stale top-level TODO-style docs were removed;
- `README.md` is an orientation page rather than a sprawling reference;
- roadmap and refactor backlog are the canonical planning surfaces;
- protocol and safety claims have dedicated canonical files;
- product intelligence and evaluation material live under `docs/`.

Future edits should update the canonical owner file rather than recreating broad TODO sections.
