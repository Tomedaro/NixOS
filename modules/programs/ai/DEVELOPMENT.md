# Development guide

## First rule

Before changing behavior, read:

1. `CURRENT_STATE.md`
2. `SAFETY_MODEL.md`
3. `PROTOCOLS.md`
4. `MODULES.md`
5. `docs/ARCHITECTURE_FINDINGS.md`
6. `docs/REFACTOR_BACKLOG.md`

Do not use deleted or historical TODO material as authority.

## Change classes

### Documentation-only changes

Allowed when they clarify current behavior, roadmap, protocols, safety boundaries, operations, or audit findings. Documentation may be rewritten aggressively if it improves truth and reduces stale ambiguity.

### Protocol changes

Require updates to:

- `PROTOCOLS.md`;
- tests or smoke checks;
- module docs for every writer/reader;
- safety notes if side effects are involved.

### Behavior changes

Require a small patch, explicit verification, and no hidden expansion of authority. Behavior changes that affect TaskNotes, live actions, or question/session lifecycle require tests.

### Dangerous changes

Treat these as high-risk:

- adding direct TaskNotes writes;
- broadening action authority;
- allowing LLM/planner code to write live action queue entries;
- executing shell commands from Obsidian/Templater surfaces;
- replaying stale action files automatically;
- making adaptive learning automatic without controls and evidence.

## Boundary rules

### LLM/planner paths

LLM-facing code may read, classify, summarize, propose, and draft. It must not silently create, edit, archive, delete, launch, execute, or mutate durable commitments.

### Obsidian paths

Obsidian surfaces are review clients. They may write bounded message/action decisions to the Obsidian protocol paths. They must not call shell commands, approval bridges, live action bridges, or TaskNotes apply/promote code directly.

### Action bridge

Live actions belong in `AI/inbox/actions/*.json`. The action bridge owns validation, idempotency, journaling, and side effects.

### TaskNotes

TaskNotes is the durable human commitment surface. New code should produce reviewable drafts unless a deterministic reviewed apply gate exists. Existing direct writers are legacy/direct and should not be copied.

## Required verification before behavior patches

Run from the repository root on the target machine:

```bash
cd /home/daniil/NixOS
git diff --check
modules/programs/ai/dev/run-smoke.sh
modules/programs/ai/dev/check-ai-live.sh
modules/programs/ai/dev/audit-ai-project.sh --verbose
git status --short --branch
stale_typo='They''do'
stale_repo='$''REPO/'
stale_obsidian='AI/inbox/from-'"obsidian"
grep -RIn --color=never "$stale_typo\|$stale_repo\|$stale_obsidian" modules/programs/ai || true
```

For docs-only patches, at minimum run `git diff --check` and the grep consistency check. The grep check may report explicitly marked legacy/diagnostic references; unmarked dependencies are the concern. Run smoke tests when docs change protocol names, commands, paths, or safety claims.

## Documentation rules

- `CURRENT_STATE.md` contains implementation truth.
- `ROADMAP.md` contains planned work.
- `docs/REFACTOR_BACKLOG.md` contains actionable refactors and risks.
- `PROTOCOLS.md` contains path/schema contracts.
- `SAFETY_MODEL.md` contains authority and side-effect boundaries.
- ADRs record decisions that should survive future refactors.

Do not duplicate stale claims across many files. Link to the canonical source instead.

## Product intelligence rules

Adaptive behavior must be introduced slowly:

1. document the learning loop;
2. add explicit feedback controls;
3. add scenario evals;
4. add optional planner metadata;
5. only then make policy adaptation automatic.

Silence, deferral, and smaller steps are valid successful outputs.

## Commit style

Prefer small commits:

1. docs truth surfaces;
2. tests for current dangerous paths;
3. behavior hardening;
4. new capability model;
5. product evals;
6. adaptive features.

Each commit should be reviewable without requiring the reviewer to infer hidden authority changes.
