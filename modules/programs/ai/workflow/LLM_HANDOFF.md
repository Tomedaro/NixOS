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
- the repository contains distributed kernel components but no canonical general orchestrator;
- the implemented planner is Ollama-specific while API-hosted models are the intended user direction;
- older planner proposals and newer Obsidian proposals coexist without a settled ownership decision.

## Current objective

Resolve the architecture questions in `workflow/OPEN_QUESTIONS.md` before broad behavior expansion.

The next design work should establish:

- canonical runtime lifecycle ownership;
- provider-neutral model/API boundary and the future role of Ollama;
- canonical proposal ownership;
- the first complete product loop;
- whether real TaskNotes apply is needed for that loop.

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
