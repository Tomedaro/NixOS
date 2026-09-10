# LLM handoff

Snapshot date: 2026-07-22.

## Current status

The project-local LLM workflow is active under `modules/programs/ai`.

Current implementation headline:

- direct TaskNotes mutation is removed or disabled;
- reviewed proposal and TaskNotes-draft paths are preserved;
- deterministic TaskNotes dry-run apply validation exists;
- the real TaskNotes writer/apply journal does not exist;
- named action capability metadata and gates exist alongside transitional numeric authority;
- the repository contains distributed kernel components but no implemented canonical general orchestrator;
- ADR 0008 accepts a deterministic laptop-side kernel for the first product loop;
- the implemented planner remains Ollama-specific while ADR 0008 selects one API provider behind a narrow adapter;
- older planner proposals and newer Obsidian proposals coexist in code, with the newer chain selected for future durable proposals.

## Current objective

Implement the dependency-ordered first-loop sequence in `ROADMAP.md` under ADR 0008 without broad behavior expansion.

The next work should establish:

- first-loop schemas and ownership;
- restart-safe laptop kernel skeleton;
- Tasker transport and offline queue;
- one-provider API boundary and allowlisted context packet;
- action-card responses and outcome linkage;
- bounded real-use evaluation.

Real TaskNotes apply, general prioritization, multi-provider routing, and autonomous harnesses are outside the first sequence.

## Constraints

- The AI companion project lives under `modules/programs/ai`.
- LLM/model work remains proposal-side.
- Local deterministic checks and human review decide acceptance and side effects.
- TaskNotes remains the durable human commitment surface.
- A validation result is not an apply result.
- Do not add a third proposal surface or a parallel action brain.
- Do not claim target-machine behavior from archive-only verification.
- API context must be selected/minimized locally; a remote model must not roam the vault.

## Canonical working set

- `CURRENT_STATE.md`
- `SAFETY_MODEL.md`
- `ARCHITECTURE.md`
- `PROTOCOLS.md`
- `docs/SCHEMA_REGISTRY.md`
- `MODULES.md`
- `workflow/OPEN_QUESTIONS.md`
- `ROADMAP.md`
- `docs/ARCHITECTURE_FINDINGS.md`
- `docs/REFACTOR_BACKLOG.md`

## Latest verified repository facts

- 30 smoke-test files exist and passed in the prior reconstructed archive review.
- Documentation checks pass after the 2026-07-22 truth refresh.
- Only Markdown documentation files changed in that refresh.
- Nix evaluation, live services, Tasker, live vault state, model inference, and API integration remain unverified in the archive environment.

## Workflow guidance

- Research/decision work belongs in `00 Research and Design`.
- Implementation begins only after an explicit decision/acceptance condition exists.
- Verification must distinguish docs checks, mechanical smoke tests, target-machine checks, and product-usefulness evaluation.
- Keep changes small enough that authority and protocol ownership remain reviewable.
