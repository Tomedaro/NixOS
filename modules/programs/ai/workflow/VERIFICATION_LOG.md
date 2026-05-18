# Verification Log

This file records local verification evidence for AI companion project changes.

## Rules

- Do not write "passed" unless the command was actually run locally.
- Record exact commands, not vague summaries.
- Record failures even if they were later fixed.
- If something was not checked, say so explicitly.

## Entry template

```md
## YYYY-MM-DD HH:MM - Task name

- Change:
- Commands run:
  - `command`
- Result:
- Failures:
- Follow-up:
- Human notes:
```

## Entries

No verification entries yet.

## 2026-05-18 15:53 - Add project-local LLM workflow scaffolding

- Change:
  - Added project-local `AGENTS.md`.
  - Added minimal workflow memory files.
  - Added ChatGPT bundle helper.
  - Added docs, patch, typo/drift, and staged verification helper scripts.
- Commands run:
  - `modules/programs/ai/dev/llm/make-docs-tar.sh`
  - `modules/programs/ai/dev/llm/check-markdown-links.sh`
  - `modules/programs/ai/dev/llm/grep-known-typos.sh`
  - `modules/programs/ai/dev/llm/check-ai-docs.sh`
  - `modules/programs/ai/dev/llm/check-llm-patch.sh`
  - `modules/programs/ai/dev/llm/verify-staged-ai.sh`
- Result:
  - Staged AI verification passed.
  - Smoke tests passed.
- Failures:
  - First staged verification failed because `check-llm-patch.sh` used an awk form not accepted by the local awk implementation.
  - Fixed by replacing the awk expression with a portable single-line assignment.
- Follow-up:
  - Existing smoke output includes probable typo `writtento`; leave for a future focused cleanup.
  - Live checks were not run.
- Human notes:
  - Generated ChatGPT bundle is intentionally ignored.

## 2026-05-18 20:15 - Add ChatGPT workflow routing guide

- Change:
  - Added `workflow/CHATGPT_WORKFLOW.md`.
  - Updated `AGENTS.md` to point assistants to the workflow routing guide.
  - Updated `make-docs-tar.sh` so future bundles include the workflow guide.
- Commands run:
  - `modules/programs/ai/dev/llm/check-ai-docs.sh`
  - `modules/programs/ai/dev/llm/check-llm-patch.sh`
  - `modules/programs/ai/dev/llm/verify-staged-ai.sh`
- Result:
  - Docs checks passed.
  - Patch checks passed.
  - Staged AI verification passed.
  - Smoke tests passed.
- Failures:
  - None for this change.
- Follow-up:
  - Existing smoke output still contains pre-existing typo `writtento`; leave for a separate focused task.
  - Live checks were not run.
- Human notes:
  - ChatGPT Project settings were also manually updated with the workflow routing requirement.
