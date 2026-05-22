# LLM Handoff

## Current status

Status: active AI companion development workflow.

The project-local LLM workflow is established under:

`modules/programs/ai`

Current implementation state:

- Direct TaskNotes mutation cleanup is complete.
- `anki-bridge` direct TaskNotes mode is removed/hard-disabled.
- `action-bridge promote_task_proposal` is disabled.
- Legacy TaskNotes promotion compatibility option/env wiring was removed.
- Reviewable proposal/draft paths are preserved.
- Deterministic TaskNotes apply/promote remains future work.
- `action-bridge` authority is moving from broad numeric authority toward named capability inventory and gates.
- ChatGPT docs bundle generation now includes all active Markdown docs under `modules/programs/ai` while excluding generated/archive/cache paths.

## Current objective

Use the minimal safe development workflow for the AI companion project.

Current research direction:

- keep direct TaskNotes mutation disabled/removed;
- preserve reviewable proposal/draft paths;
- continue tightening `action-bridge` capability coverage and default-authority semantics before adding new modules or more autonomous behavior;
- prefer invariant and regression coverage before behavior changes.

## Current constraints

- The AI companion project lives under `modules/programs/ai`.
- The whole repo is a NixOS/dotfiles repo, so workflow files must not imply control over the whole repo.
- The LLM is proposal-side only.
- Local scripts and human review decide whether work is accepted.
- Current state, roadmap, safety, protocols, architecture, and operations must remain distinct.
- TaskNotes remains the durable human commitment surface.
- Real TaskNotes writes must wait for a deterministic reviewed apply/promote gate.
- Do not reintroduce direct TaskNotes mutation paths.

## Active working set

Workflow files:

- `modules/programs/ai/AGENTS.md`
- `modules/programs/ai/workflow/LLM_HANDOFF.md`
- `modules/programs/ai/workflow/DECISIONS.md`
- `modules/programs/ai/workflow/VERIFICATION_LOG.md`
- `modules/programs/ai/workflow/OPEN_QUESTIONS.md`
- `modules/programs/ai/workflow/CHATGPT_WORKFLOW.md`

Helper scripts:

- `modules/programs/ai/dev/llm/make-docs-tar.sh`
- `modules/programs/ai/dev/llm/check-markdown-links.sh`
- `modules/programs/ai/dev/llm/grep-known-typos.sh`
- `modules/programs/ai/dev/llm/check-ai-docs.sh`
- `modules/programs/ai/dev/llm/check-llm-patch.sh`
- `modules/programs/ai/dev/llm/verify-staged-ai.sh`

Generated ChatGPT bundles live under:

- `modules/programs/ai/chatgpt-bundles/`

The generated `.tar.gz` bundles are intentionally ignored by Git.

## Latest verified facts

- Direct TaskNotes mutation paths are removed or disabled.
- Reviewable proposal/draft paths remain available.
- Named `action-bridge` gates exist for:
  - `proof.submit`
  - `recovery.target.start`
  - `session.check_in`
- `ACTION_CAPABILITY_POLICY` exists as a source-level capability inventory.
- Alias, metadata, default-authority, and enforcement-classification invariant coverage exists for action capability policy.
- ChatGPT bundle generation includes all active Markdown docs under `modules/programs/ai`.
- Bundle generation excludes:
  - `chatgpt-bundles/`
  - `workflow/archive/`
  - `__pycache__/`
  - `*.pyc`

## Known blockers

No blocker for the workflow handoff itself.

Remaining design work:

- continue reviewing `action-bridge` capability coverage and default-authority semantics;
- decide whether to add more named gates or first refine the registry/policy model;
- design deterministic TaskNotes apply/promote separately before any real TaskNotes write path returns.

## Next best action

1. Keep the next task in `00 Research and Design`.
2. Audit the next smallest `action-bridge` capability or policy invariant.
3. Prefer a plan-only research step before behavior changes.
4. Do not add new modules, direct TaskNotes writes, or autonomous behavior before capability semantics are clearer.
