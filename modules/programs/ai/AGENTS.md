# AGENTS.md

## Scope

These instructions apply only to the AI companion project in:

`modules/programs/ai`

Do not treat them as instructions for the whole NixOS repo.

## Project purpose

This project is a local-first AI goal-achievement companion.

Its purpose is to help the user reach goals through:
- inspectable local state;
- bounded agency;
- recovery-oriented support;
- proposal-side LLM behavior;
- human-owned commitments;
- TaskNotes as the durable commitment surface;
- deterministic review and apply gates;
- modular instruments around a small safety kernel.

## Source of truth

Treat files in `modules/programs/ai` as the project source of truth.

Important top-level docs include:

- `README.md`
- `CURRENT_STATE.md`
- `PHILOSOPHY.md`
- `SAFETY_MODEL.md`
- `PROTOCOLS.md`
- `MODULES.md`
- `ARCHITECTURE.md`
- `DEVELOPMENT.md`
- `OPERATIONS.md`
- `ROADMAP.md`
- `GLOSSARY.md`
- `EXTENSION_MODEL.md`

If docs disagree, do not guess. Flag the contradiction.

## LLM boundary

The LLM may:
- research;
- explain;
- plan;
- draft patches;
- review diffs;
- debug failures;
- propose commands.

The LLM must not:
- claim changes are implemented unless the user applied them locally;
- invent file paths;
- widen authority;
- bypass TaskNotes boundaries;
- silently turn roadmap items into current state;
- treat generated prose as verified evidence;
- make broad edits outside `modules/programs/ai` unless explicitly asked.

## Patch rule

Prefer small, reviewable patches.

For nontrivial work:

1. plan first;
2. patch second;
3. verify locally;
4. update workflow notes if needed;
5. commit only after checks pass.

## Verification rule

Before a change is considered done, run relevant local checks.

Minimum checks usually include:

```bash
git diff --check
modules/programs/ai/dev/llm/check-ai-docs.sh
modules/programs/ai/dev/llm/check-llm-patch.sh
```

For staged changes:

```bash
modules/programs/ai/dev/llm/verify-staged-ai.sh
```

If checks fail, the change is not done. It is only drafted.
