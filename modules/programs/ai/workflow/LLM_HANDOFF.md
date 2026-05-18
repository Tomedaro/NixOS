# LLM Handoff

## Current status

Status: project-local LLM workflow scaffolding committed.

Current workflow scaffold commit: see latest Git history.

The ChatGPT Project and four working chats have been created.

Local workflow files now live under:

`modules/programs/ai`

## Current objective

Use the minimal safe development workflow for the AI companion project.

The scaffolding now supports:
- project-local LLM instructions;
- durable handoff state in the repo;
- ChatGPT bundle creation;
- Markdown link checks;
- typo and workflow-drift checks;
- LLM patch checks;
- staged AI verification;
- existing AI smoke-test integration.

## Current constraints

- The AI companion project lives under `modules/programs/ai`.
- The whole repo is a NixOS/dotfiles repo, so workflow files must not imply control over the whole repo.
- The LLM is proposal-side only.
- Local scripts and human review decide whether work is accepted.
- Current state, roadmap, safety, protocols, architecture, and operations must remain distinct.
- TaskNotes remains the durable human commitment surface.

## Active working set

Workflow files:

- `modules/programs/ai/AGENTS.md`
- `modules/programs/ai/workflow/LLM_HANDOFF.md`
- `modules/programs/ai/workflow/DECISIONS.md`
- `modules/programs/ai/workflow/VERIFICATION_LOG.md`
- `modules/programs/ai/workflow/OPEN_QUESTIONS.md`

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

- `modules/programs/ai/dev/llm/verify-staged-ai.sh` passed before commit.
- Existing AI smoke tests passed.
- Live checks were not run.
- Generated bundle creation works.
- The generated bundle is ignored by Git.
- A likely pre-existing typo appeared in smoke output: `writtento`.

## Known blockers

None for the workflow scaffold.

## Next best action

1. Regenerate the ChatGPT bundle after this handoff update.
2. Upload the newest bundle to the ChatGPT Project.
3. Use `00 Research and Design` to pick the first real project task.
4. Keep the first real task small and verification-focused.
