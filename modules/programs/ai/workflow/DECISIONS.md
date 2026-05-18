# Decisions

## 2026-05-18 - Keep LLM workflow files inside the AI module

Status: accepted

Decision:
Keep project-specific LLM workflow files under `modules/programs/ai`.

Why:
The repository is a NixOS/dotfiles repo, while the AI companion project is only one module inside it. Root-level workflow files would imply that the LLM workflow applies to the whole repo.

Consequences:
- `AGENTS.md` lives at `modules/programs/ai/AGENTS.md`.
- Workflow memory lives under `modules/programs/ai/workflow/`.
- LLM helper scripts live under `modules/programs/ai/dev/llm/`.
- ChatGPT bundles are generated under `modules/programs/ai/chatgpt-bundles/`.

## 2026-05-18 - Use a minimal four-chat workflow

Status: accepted

Decision:
Use four recurring ChatGPT chats:
- `00 Research and Design`
- `01 Implementation`
- `02 Verification and Debugging`
- `03 Release and Retrospective`

Why:
Eight chat types are too much process for a solo developer at day one. Four chats preserve the important boundaries without creating workflow drag.

Consequences:
- Research and architecture share one chat.
- Patch planning and patch creation share one chat.
- Verification and debugging share one chat.
- Final review, handoff, and retrospective share one chat.

## 2026-05-18 - Keep LLMs proposal-side

Status: accepted

Decision:
LLMs may plan, draft, review, and debug, but local checks and human review decide whether work is accepted.

Why:
This matches the project architecture: local-first, inspectable, bounded, and recovery-oriented.

Consequences:
- No patch is considered done until it is applied locally and verified.
- The LLM must not claim implementation success without local evidence.
- Local scripts are the judge for repeatable checks.
