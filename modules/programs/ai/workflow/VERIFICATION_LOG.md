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

## 2026-07-22 - Refresh documentation against current archive

- Change:
  - Updated canonical current-state, architecture, protocols, modules, roadmap, open questions, audit findings, inventory, backlog, and handoff documents.
  - Added `docs/SCHEMA_REGISTRY.md`.
  - Marked the documentation restructure plan as historical.
  - Changed no non-Markdown source/configuration files.
- Commands run in a reconstructed repository layout:
  - `diff -qr ai_original ai_docs_update`
  - `modules/programs/ai/dev/llm/check-ai-docs.sh`
  - attempted sequential execution of `tests/*_smoke.py`
- Result:
  - Diff confirmed only Markdown documentation files changed.
  - Documentation whitespace, link, and typo/drift checks passed.
  - The smoke rerun showed no failure in the first 14 scripts before the external command timeout; the complete suite was not rerun because source code was unchanged.
- Failures:
  - First documentation check found one extra blank line at EOF in `docs/MODULE_REVIEW_REGISTER.md`; it was corrected and the check then passed.
  - Full sequential smoke rerun was interrupted by the review-environment timeout.
- Follow-up:
  - Run the normal full smoke and target-machine checks when applying the documentation patch locally if required by the local contribution policy.
  - Nix evaluation, live services, Tasker, live vault state, model inference, and API integration were not checked.

## 2026-07-22 - Pre-apply documentation patch sanity check

- Change:
  - Reconstructed the expected repository layout from the archived source.
  - Applied the documentation patch in a clean Git worktree.
  - Added this verification record only; no source, test, Nix, or runtime configuration was changed.
- Commands run:
  - `git apply --check /mnt/data/ai-docs-update.patch`
  - `git apply /mnt/data/ai-docs-update.patch`
  - `diff -qr modules/programs/ai /mnt/data/verify_ai_docs/updated`
  - `modules/programs/ai/dev/llm/check-ai-docs.sh`
  - `modules/programs/ai/dev/llm/check-llm-patch.sh`
  - `python3 -m py_compile <all Python files under modules/programs/ai>`
  - all 30 files listed by `modules/programs/ai/dev/run-smoke.sh`, executed with the repository Python path
  - a source-to-registry comparison of all `*.vN` protocol identifiers against `docs/SCHEMA_REGISTRY.md`
- Result:
  - Patch application check passed from the repository root.
  - The patched module tree matched the supplied updated archive exactly before this verification-log entry was added.
  - Only Markdown files differ from the archived source.
  - Documentation whitespace, local-link, typo/drift, dangerous-shell-pattern, and workflow-boundary checks passed.
  - All Python files compiled.
  - All 30 smoke-test files passed. The first aggregate command reached its external timeout after 22 passing files; the remaining eight were then run individually and all passed.
  - The schema registry contains exactly the 44 versioned protocol identifiers found in non-test source, with no missing or extra entries.
- Failures:
  - Applying the patch from inside `modules/programs/ai` fails because patch paths are rooted at `modules/programs/ai/`. It must be applied from the repository root.
  - No source or documentation correctness failure was found.
- Follow-up:
  - Before applying in the real repository, run `git apply --check /path/to/ai-docs-update-v2.patch` from the repository root because local changes after the archived snapshot may create conflicts.
  - Nix evaluation, NixOS rebuild, live services, Tasker, live vault state, Ollama inference, and remote API integration remain unverified.
