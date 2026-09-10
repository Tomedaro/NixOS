# Analyst/Worker Workflow

## Purpose

`pi-aw` starts an opt-in Analyst/Worker Pi session for tasks that benefit from a smart planning/review model supervising a cheaper execution model. It is intended for trusted workspaces where normal managed Pi extensions should remain available.

Validated smoke-test role split:

| Role | Model | Thinking | Responsibility |
|------|-------|----------|----------------|
| Analyst | `openai-codex/gpt-5.5` | high | Plan one bounded stage, review Worker output, decide continue/done/ask/abort |
| Worker | `deepseek/deepseek-v4-flash` | high | Search, edit, run commands/tests, save artifacts, report concise results |

Keep normal `pi` cheap and stable. Use `pi-aw` only when the Analyst/Worker loop is worth the extra model cost.

## Command

```bash
pi-aw
```

Inside Pi:

```text
/analyst-worker start --configure
```

Recommended first configuration:

```text
Analyst: openai-codex/gpt-5.5
Analyst thinking: high
Worker: deepseek/deepseek-v4-flash
Worker thinking: high
```

## How `pi-aw` works

`pi-aw` runs a managed parent Pi session with the normal profile, policy, context, and extension set. This preserves productivity tools such as:

- `ctx_*` and `lean_ctx`
- `pi-lens` diagnostics/navigation/ast-grep
- `todo`
- Engram `mem_*`
- Hermes `memory`, `session_search`, and `skill`
- `pi-subagents`
- `advisor()`
- `pi-intercom`
- `web_search` / `code_search` / `fetch_content`

The analyst-worker package internally launches child `pi --no-extensions --no-tools` probes for model validation and external OpenAI/Codex-style Analyst turns. Managed Pi wrappers reject `--no-extensions` because normal profiles depend on `pi-permission-system`.

To keep the parent productive while making those child probes work, `pi-aw` creates a temporary PATH shim named `pi` that redirects only child `pi` calls to `pi-raw`. The parent session remains managed Pi and still loads normal extensions.

`pi-aw` stores workflow artifacts under the Pi session directory instead of the repository `./tmp`, and sets the autonomous Worker step limit to one by default so the Analyst returns control more often.

## Package pin

`pi-aw` loads the extension from a Nix-pinned GitHub source at commit:

```text
0229ddc80b965e4ca11377a9730e46d0bd7701ac
```

This is the commit behind the validated `v0.1.1` smoke test. The wrapper passes the store-path extension entrypoint to Pi instead of fetching the Git source at every launch.

The package is intentionally not added to `settings/global.json` yet. Loading it globally would expose `/analyst-worker` in normal `pi` sessions without the child-probe compatibility shim.

## Instruction pack

`pi-aw` exposes a source-managed Analyst/Worker operating pack under:

```text
modules/programs/cli/pi/resources/analyst-worker/
```

Runtime `pi-aw` exports these paths:

```text
PI_AW_PACK_ROOT
PI_AW_POLICY
PI_AW_ANALYST_INSTRUCTIONS
PI_AW_WORKER_INSTRUCTIONS
PI_AW_SHARED_GUARDRAILS
PI_AW_STOP_MATRIX
PI_AW_TEMPLATES_DIR
PI_AW_SIMPLIFY_CONVENTIONS
PI_ANALYST_WORKER_ARTIFACT_ROOT
PI_ANALYST_WORKER_MAX_AUTONOMOUS_WORKER_STEPS
```

The pack contains role contracts, shared guardrails, stop conditions, reviewer-budget policy, SDD/TDD expectations, ctx-tool efficiency rules, artifact visibility rules, parent-owned memory policy, changed-files simplification policy, and handoff templates.

Current enforcement status: the upstream orchestrator has built-in role prompts, so this pack is a source-managed operating contract and reference exposed to the session. Local wrapper patches also enforce the artifact root and configured autonomous-worker safety stop. Full schema-based stage-boundary enforcement remains a future slice.

When starting a serious run, include this operator note:

```text
Use the source-managed Analyst/Worker instruction pack exposed by PI_AW_PACK_ROOT. Treat it as the operating protocol. Preserve Gentle AI discipline, SDD/TDD gates, evidence requirements, reviewer workload limits, ctx-tool efficiency, artifact visibility, parent-owned memory writes, and the changed-files simplification gate before Analyst review.
```

## Validated smoke test

Date: 2026-06-19

The artifact paths below are historical smoke-test paths. Current `pi-aw` runs default to `PI_ANALYST_WORKER_ARTIFACT_ROOT` under the Pi session directory.
Workspace: `/tmp/pi-aw-smoke`

Pipeline:

```text
Analyst plan → Worker execute → Analyst review
```

Result: passed.

Artifacts were preserved under:

```text
/tmp/pi-aw-smoke/tmp/aw_20260619_154244_analyst_worker_smoke_test/
```

Observed output:

- `state.md`
- `ledger.json`
- `steps/0001_analyst_plan.md`
- `steps/0002_worker_result.md`
- `steps/0003_analyst_review.md`
- `scratch_step0002.md`
- `/tmp/pi-aw-smoke/tmp/aw-smoke-note.md`

Approximate cost/time:

| Stage | Wall time | Cost |
|-------|-----------|------|
| Analyst plan | ~18.8s | ~$0.0315 |
| Worker execute | ~18.1s | ~$0.0089 |
| Analyst review | ~21.1s | ~$0.0483 |
| Total | ~58s | ~$0.09 |

## Operating protocol

Use the instruction pack as the detailed protocol:

- Analyst contract: `resources/analyst-worker/roles/analyst.md`
- Worker contract: `resources/analyst-worker/roles/worker.md`
- Shared guardrails: `resources/analyst-worker/shared/guardrails.md`
- Stop conditions: `resources/analyst-worker/shared/stop-matrix.md`
- Handoff templates: `resources/analyst-worker/templates/`

The short rule: Analyst plans and reviews one bounded stage; Worker executes only that stage; Analyst accepts, asks, aborts, or plans the next bounded stage based on evidence.

A good Worker stage is one logical slice, usually one subsystem or 1-3 files, one validation target, and not a mixed feature/refactor/cleanup bundle unless explicitly approved.

When files change, Worker should run a changed-files-only simplification pass before Analyst review. Prefer `/simplify` or `pi-simplify`; if unavailable, use `PI_AW_SIMPLIFY_CONVENTIONS` as a manual checklist and report the result.

For repository work, Worker should prefer `ctx_*` tools and explain exceptions. Review-critical artifacts must be summarized or excerpted in the Worker report so the external Analyst can verify them without separate tool access.

## Integration with existing tools

- Use `todo` in the parent for high-level phases only; do not mirror every Analyst/Worker step.
- Save durable decisions and final handoffs to Engram with `mem_save`.
- Save user preferences, local quirks, and reusable procedures to Hermes when appropriate.
- Use `advisor()` only for risky gates, package pinning decisions, or final review of complex work.
- Use `pi-subagents` as supporting scouts/reviewers, not as a competing orchestrator during an analyst-worker run.
- Use `pi-intercom` when a Worker needs a blocking decision instead of guessing.
- Use `pi-lens` diagnostics and `git diff --check` at review gates.

## Profile limitations

`pi-aw` is not supported in cautious/read-only profiles because it intentionally loads an additional workflow extension and expects the Worker to use normal productivity tools. Use one of these modes from a trusted workspace:

```bash
PI_PROFILE=research pi-aw
PI_PROFILE=work pi-aw
PI_PROFILE=nixos pi-aw
```

## Avoid initially

Do not use these during early real tasks unless intentionally reviewed:

```text
/analyst-worker archive --commit
/analyst-worker archive --delete-tmp
```

Prefer:

```text
/analyst-worker archive --keep-tmp
```

## Future improvements

Preferred upstream/package improvement:

- Add a package option such as `PI_ANALYST_WORKER_CHILD_PI=pi-raw` so `pi-aw` can set a variable instead of using a PATH shim.

Potential future local checks:

- `pi-admin analyst-worker-check`
- include analyst-worker state in a future `pi-admin resource-inventory`
- include `pi-aw` in `pi-admin status`
