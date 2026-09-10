# Analyst/Worker Instruction Pack

## Purpose

This source-managed pack defines the operating protocol for `pi-aw` sessions.

`pi-aw` is an opt-in launcher for large or uncertain tasks where an expensive Analyst model plans and reviews while a cheaper Worker model executes bounded stages.

Normal `pi` remains the default for ordinary work.

## Current enforcement status

The current `pi-analyst-worker-orchestrator` package has built-in role prompts. This pack is therefore a **source-managed operating contract** exposed through `pi-aw` environment variables and docs. It is not yet a deterministic stage-boundary checker.

Future slices should add schema/check scripts that enforce this pack mechanically.

## Precedence

Within `pi-aw`, follow this order:

1. Current user instruction
2. Project-specific instructions and active SDD/OpenSpec artifacts
3. This Analyst/Worker instruction pack
4. General Pi and Gentle AI instructions
5. Memory and prior session context

If these conflict, stop and ask the human or the Analyst.

## Files

- `policy.yaml` — thresholds and ownership rules
- `roles/analyst.md` — Analyst contract
- `roles/worker.md` — Worker contract
- `shared/guardrails.md` — rules both roles must follow
- `shared/stop-matrix.md` — stop/ask/escalate triggers
- `templates/analyst-plan.md` — Analyst plan shape
- `templates/worker-report.md` — Worker result shape
- `templates/analyst-review.md` — Analyst review shape
- `templates/tdd-evidence.md` — TDD evidence shape
- `templates/memory-candidate.md` — memory candidate shape

## Environment variables exported by `pi-aw`

- `PI_AW_PACK_ROOT`
- `PI_AW_POLICY`
- `PI_AW_ANALYST_INSTRUCTIONS`
- `PI_AW_WORKER_INSTRUCTIONS`
- `PI_AW_SHARED_GUARDRAILS`
- `PI_AW_STOP_MATRIX`
- `PI_AW_TEMPLATES_DIR`
- `PI_AW_SIMPLIFY_CONVENTIONS`
- `PI_ANALYST_WORKER_ARTIFACT_ROOT`
- `PI_ANALYST_WORKER_MAX_AUTONOMOUS_WORKER_STEPS`

## Runtime gates

- **Simplification:** when files change, Worker runs a changed-files-only simplification pass before returning to Analyst. Prefer `/simplify` or `pi-simplify`; if slash-command execution is unavailable, use `PI_AW_SIMPLIFY_CONVENTIONS` as a manual checklist.
- **Tool efficiency:** Worker uses `ctx_*` tools for repository reads, search, listing, and validation by default. Non-`ctx_*` exceptions must be explained in the report.
- **Artifact visibility:** review-critical artifacts need a path, short summary, and excerpt/checksum in the Worker report. Analyst should not accept final claims that depend on unseen artifact contents.
- **Memory hygiene:** Worker writes memory candidates, not durable memory. Parent session owns final durable memory writes.
- **Autonomy limit:** `pi-aw` sets the Worker step limit to one so Analyst review returns control frequently.
- **Artifact hygiene:** `pi-aw` stores run artifacts under the Pi session directory, not the repository `./tmp/`.

## First-run operator note

When using `/analyst-worker start --configure`, tell the Analyst:

```text
Use the source-managed Analyst/Worker instruction pack exposed by PI_AW_PACK_ROOT. Treat it as the operating protocol. Preserve Gentle AI discipline, SDD/TDD gates, evidence requirements, reviewer workload limits, ctx-tool efficiency, artifact visibility, parent-owned memory writes, and the changed-files simplification gate before Analyst review.
```
