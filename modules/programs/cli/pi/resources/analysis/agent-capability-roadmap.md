# Pi Agent Capability Roadmap

## Purpose

This roadmap captures what the NixOS-managed Pi setup is missing around extensions, skills, prompts, and agent orchestration. It is meant as a durable orientation file for future Pi sessions: read it before expanding the agent capability surface.

Use this together with:

- `docs/INDEX.md` and `docs/LOOKUP.json` for routing
- `docs/EXTENSIONS.md` for installed extension reference
- `docs/MEMORY.md` for Engram/Hermes ownership
- `resources/analysis/TRACKING.md` for broad implementation progress
- `resources/analysis/improvement-plan.md` for historical plan context

## Scope

This roadmap focuses on **agent capability**: extensions, skills, prompts, subagents, and
orchestration patterns. Broader Pi-infrastructure items (sandbox profiles, sync dry-run, HM
activation, architecture docs, threat model) appear here when they cross into agent behavior,
but their primary tracking lives in `resources/analysis/TRACKING.md` and
`resources/analysis/improvement-plan.md`. This file's priority labels use descriptive names
(Critical, High, Medium, Lower, Future) to avoid collision with TRACKING.md's P-level numbering.

## Big-picture sanity check

The current Pi setup is already strong at source/runtime ownership, profile routing, memory separation, and package visibility. The next improvements should not add more always-loaded instructions or more workflow surface area first. They should make the existing surface **explainable, testable, and generated where possible**.

Design thesis:

1. **Inventory before expansion** — know which extensions, prompts, skills, MCP servers, and subagents exist before adding more.
2. **Lint before orchestration** — validate prompt/skill metadata and policy/resource wiring before adding agent evals.
3. **Explain before automate** — implement profile/resource explanation before activation-time sync or hooks.
4. **Test before sandbox claims** — add permission regression tests before promoting a real sandbox or changing `pi-safe` semantics.
5. **Generate references where possible** — human docs are useful, but inventories should eventually be checked against source/runtime state.

Non-goals for this roadmap:

- Do not make `AGENTS.md` a catalog of all tools and workflows.
- Do not Nix-package every npm extension as a first response.
- Do not grant memory tools broadly to subagents without an explicit design.
- Do not rename cautious/read-only modes to imply real isolation before OS sandbox tests pass.

## Current inventory

### Installed extension layer

Package source of truth: `settings/global.json`. Human reference: `docs/EXTENSIONS.md`.

| Area | Current extension/tooling | Current role |
|------|---------------------------|--------------|
| Permission/control | `pi-permission-system` | Profile policy enforcement and cautious mode guardrails |
| Delegation | `pi-subagents` | Focused exploration, implementation, review, and SDD phase agents |
| Review/advice | `rpiv-advisor` | Stronger review before complex work, completion, or stuck points |
| Memory | `gentle-engram`, `pi-hermes-memory` | Project memory plus Pi-local behavioral/session/procedural memory |
| Code intelligence | `pi-lens`, `pi-lean-ctx` | LSP/AST diagnostics and token-efficient codebase context |
| Web/research | `pi-web-access` | Web search, code search, fetch content |
| MCP | `pi-mcp-adapter` | External MCP server access with profile-specific configs |
| Rendering/UX | `pi-markdown-preview`, `pi-powerline-footer`, `pi-themes` | Preview/export and terminal UI polish |
| Workflow | `gentle-pi`, `pi-simplify`, `pi-intercom` | SDD/Gentle AI skills, simplify review, cross-session coordination |

### Source-managed prompt layer

| Profile | Prompt | Purpose |
|---------|--------|---------|
| `nixos` | `pi-change.md` | Plan safe Pi setup changes through the wiki first |
| `nixos` | `security.md` | Explain profile safety, cautious limitations, sandbox boundaries |
| `nixos` | `setup.md` | Explain NixOS-managed Pi setup and route changes |
| `nixos` | `status.md` | Review setup status with focused checks |
| `study` | `study.md` | Start or continue a study session |
| `study` | `consolidate.md` | Consolidate learning into logs, topic notes, and memory proposals |
| `study` | `map-topic.md` | Create/update concept maps |
| `study` | `review.md` | Retrieval-practice and weak-topic review |
| `work` | `work.md` | Start a work/project session with safe context discovery |

### Source-managed skill layer

| Profile | Skill | Purpose |
|---------|-------|---------|
| `nixos` | `pi-nix-self-maintenance` | Maintain this NixOS-managed Pi setup safely |
| `study` | `learning-session` | Structured learning session workflow |
| `study` | `memory-consolidation` | Consolidate logs into reviewed notes and memory proposals |
| `study` | `spaced-review` | Retrieval-practice review planning |
| `study` | `topic-graph-maintenance` | Maintain topic graph notes |
| `work` | `work-session` | Focused project work with validation and small diffs |

### Opt-in Analyst/Worker workflow

`pi-aw` is the source-managed launcher for the validated Analyst/Worker pattern. It loads `pi-analyst-worker-orchestrator` from a Nix-pinned Git commit while preserving the normal managed parent Pi extension set and exporting the source-managed instruction pack under `resources/analyst-worker/`.

Validated role split:

| Role | Model | Purpose |
|------|-------|---------|
| Analyst | `openai-codex/gpt-5.5` | Expensive planning, review, stop conditions, and final decisions |
| Worker | `deepseek/deepseek-v4-flash` | Cheaper code execution, searches, commands, validation, and concise reports |

This is intentionally opt-in rather than globally loaded so normal `pi` stays cheap and stable. The instruction pack now covers role contracts, shared guardrails, SDD/TDD policy, stop conditions, memory hygiene, changed-files simplification before Analyst review, and handoff templates. Deterministic checkers/evals remain the next slice. See `docs/ANALYST_WORKER.md`.

## External research takeaways

Current agent ecosystems converge on a layered control stack:

1. **Rules / AGENTS files** for short always-loaded constraints.
2. **Prompts / slash commands** for explicit human-started workflows.
3. **Skills** for reusable procedures loaded on demand through clear descriptions.
4. **Subagents** for isolated responsibility, fresh context, and independent review.
5. **Hooks / deterministic gates** for lifecycle checks that should run every time.
6. **MCP/tools** for external capabilities with least privilege and inventory.
7. **Evals/telemetry** for regression testing, observability, approval history, and policy outcomes.

Best-practice implications for this setup:

- Keep `AGENTS.md` small; do not turn it into an extension or workflow catalog.
- Prefer skills over prompts when the agent should choose a reusable method dynamically.
- Prefer prompts when the human explicitly starts a workflow.
- Prefer subagents when isolation, fresh context, or adversarial review matters.
- Prefer hooks/tests when the behavior must be deterministic.
- Treat extensions and MCP servers as supply-chain and permission surfaces, not just conveniences.

## Gap analysis

### Feature-wise gaps

| Priority | Gap | Why it matters | Candidate home |
|----------|-----|----------------|----------------|
| P0 | Runtime permission regression tests | Static policy lint cannot prove real denial/allow behavior | `pi-admin policy-test` |
| Critical | Real sandbox profile | Current cautious/read-only profiles are policy layers, not OS isolation | experimental `pi-sandbox` (also in TRACKING.md P8) |
| High | Extension capability matrix | Current extension list is descriptive, not validated against installed packages and exposed tools | `docs/EXTENSIONS.md`, generated report |
| High | Skill/prompt inventory command | Future agents need one command to see available workflows by profile | `pi-admin resource-inventory` |
| High | Prompt/skill linting | Broken frontmatter, stale paths, or unclear descriptions reduce trigger reliability | `pi-source-check` or new lint script |
| High | `pi-admin explain-profile` | Profile behavior is spread across wrappers, settings, policies, MCP, and resources | `pi-admin explain-profile` (TRACKING.md P1.4) |
| High | Sync dry-run/diff | Runtime sync mutates generated files without a preview mode | `pi-admin sync --dry-run/--diff` (TRACKING.md P2.4) |
| High | Launch metadata/audit | Debugging needs profile, policy, MCP, settings hash, source hash, and Pi version per launch | wrapper launch stamp (TRACKING.md P1.5) |
| Medium | Agent eval suite | AGENTS, prompts, skills, memory routing, and policy behavior need regression checks | `pi-admin eval` or `pi-source-check` extensions |
| Medium | MCP/tool governance report | MCP security best practice requires inventory, allowlists, provenance, and logs | `pi-admin mcp-report` |
| Medium | Memory lifecycle runbooks | Engram/Hermes architecture exists, but backup/export/retention/review workflows are thin | `docs/MEMORY.md`, runbooks |
| Medium | Hooks/stop-gates | Repeated verification currently depends on agent discipline | wrapper hooks or `pi-admin check-all` |
| Lower | First-run onboarding | New profiles/projects need a guided explanation of trust, sync, and safety | prompt + `explain-profile` |

### Logic/design gaps

1. **Extension inventory is not generated.** `docs/EXTENSIONS.md` can drift from `settings/global.json` and runtime installed packages.
2. **Prompt and skill discoverability is filesystem-based.** There is no generated manifest or linted registry for profile resources.
3. **No explicit layer decision guide.** Future maintainers need a rule for AGENTS vs docs vs prompt vs skill vs subagent vs hook.
4. **Profile behavior is distributed.** Wrappers, settings overlays, policies, MCP configs, docs, and resources each hold part of the truth.
5. **Policy is not a sandbox.** The setup documents this well, but a real `pi-sandbox` is still missing.
6. **Quality gates are mostly manual.** `advisor`, review subagents, and validation commands exist, but no deterministic stop-hook equivalent enforces them.
7. **Supply-chain visibility is better than provenance.** npm-check and compat exist, but signature/provenance and lifecycle gating remain future work.

## Layer decision guide

| Need | Put it in |
|------|-----------|
| Must affect every normal Pi session | `resources/global/AGENTS.md` |
| Profile-specific always-on behavior | profile `AGENTS.md` |
| Detailed reference or architecture | `docs/*.md` |
| Human explicitly starts a workflow | prompt/slash command |
| Agent should load reusable method on demand | skill (`SKILL.md`) |
| Work needs fresh context or independent review | subagent |
| Behavior must always run at a lifecycle point | hook/check script |
| External system access | MCP/tool extension with profile policy and audit |
| Long-term project decision/root cause | Engram memory |
| User preference/local quirk/procedure | Hermes memory or skill |

## Roadmap

### P0 — Safety and correctness

- [ ] Add `pi-admin policy-test` runtime permission regression tests.
  - Cover cautious, nixos, trusted, work, study, and raw modes.
  - Include symlink escape, secret path, write outside scope, denied shell, and MCP exposure tests.
  - Validate with `pi-admin policy-lint`, `pi-admin mcp-check`, and `pi-admin drift`.
- [ ] Add a `pi-admin check-all` read-only aggregate.
  - Include source-check, compat, mcp-check, npm-check, policy-lint, markdown sanity, and JSON validation.
- [ ] Design `pi-sandbox` as an explicit experimental profile only after permission tests exist.
  - Use bubblewrap or equivalent OS isolation.
  - Include network-off mode and symlink regression tests.
  - Do not alias `pi-safe` to it until tests pass.

### P1 — Capability discovery and profile explainability

- [ ] Implement `pi-admin explain-profile`.
  - Show selected profile, selection reason, policy, MCP config, settings overlay, resource roots, caveats, and sync/drift state.
  - Add `--json` for machine-readable output.
- [ ] Implement `pi-admin resource-inventory`.
  - List prompts, skills, AGENTS files, managed/seed ownership, and profile mapping.
  - Flag missing descriptions, duplicate names, and stale references.
- [ ] Generate or validate `docs/EXTENSIONS.md` from `settings/global.json` plus runtime inspection.
  - Include package version, tool names, risk class, lifecycle scripts, and accepted warnings.
- [ ] Add prompt/skill linting.
  - Validate frontmatter, `description`, `argument-hint`, relative paths, and SKILL.md section shape.

### P2 — Orchestration, evals, and observability

- [ ] Add an agent capability matrix.
  - Rows: extension, skill, prompt, subagent, MCP server.
  - Columns: profile, trigger, tools, risk level, validation command.
- [ ] Add regression evals for agent behavior.
  - AGENTS routing, memory routing, prompt/skill selection, and review delegation.
  - Store fixtures under `resources/analysis/evals/` or a dedicated test directory.
- [ ] Add launch metadata stamping.
  - Record profile, cwd, policy, MCP config, source hash, settings hash, Pi version, and wrapper.
- [ ] Add MCP/tool governance report.
  - Inventory every MCP server/tool per profile, directTools, command provenance, network/runtime fetches, and excluded tools.

### P3 — UX and documentation

- [ ] Add `docs/ARCHITECTURE.md` with a diagram of source, runtime, wrappers, profiles, MCP, npm prefix, memory, prompts, and skills.
- [ ] Add `docs/THREAT_MODEL.md` covering malicious repos, prompt injection, tool poisoning, npm compromise, MCP abuse, symlink escape, runtime drift, and memory leakage.
- [ ] Add runbooks:
  - `docs/runbooks/runtime-drift.md`
  - `docs/runbooks/profile-mcp-mismatch.md`
  - `docs/runbooks/memory-health.md`
  - `docs/runbooks/package-update.md`
  - `docs/runbooks/untrusted-repo.md`
- [ ] Add first-run onboarding prompt for new project/profile contexts.

### P4 — Maintainability and source/runtime convergence

- [ ] Add `pi-admin sync --dry-run` and `pi-admin sync --diff`.
- [ ] Add Home Manager activation drift warning.
- [ ] Add optional `programs.pi.syncGlobalOnActivation`.
- [ ] Split `scripts.nix` into domain modules only after P0/P1 tests exist.
- [ ] Add shell/static checks for generated scripts and wrappers.

## TODO backlog by resource type

### Extensions

- [ ] Add generated extension manifest with versions from `settings/global.json`.
- [ ] Cross-check manifest against runtime `~/.pi/agent/npm` installed packages.
- [ ] Add risk labels: control, memory, MCP, web/network, code-exec, UI-only.
- [ ] Track lifecycle scripts and peer warnings in the manifest.
- [ ] Add extension update checklist links per package class.

### Skills

- [ ] Add skill inventory grouped by profile.
- [ ] Validate every `SKILL.md` has a clear description and section structure.
- [ ] Add examples or references one level deep for complex skills.
- [ ] Detect duplicate or overlapping skills.
- [ ] Add tests/fixtures for skills that change files or memory.

### Prompts

- [ ] Add prompt inventory grouped by profile.
- [ ] Validate prompt frontmatter and argument hints.
- [ ] Check prompts route to current docs/skills paths.
- [ ] Split prompts that contain reusable procedure into skills.
- [ ] Keep prompts as explicit user-started entrypoints, not hidden policy.

### Subagents and SDD

- [ ] Keep parent-owned memory orchestration unless explicitly redesigned.
- [ ] Add a reviewer checklist for subagent outputs.
- [ ] Add evals for delegation triggers and review workload guardrails.
- [ ] Track SDD artifact store choices and status-contract compatibility.

### Memory

- [ ] Add memory backup/export/restore runbook.
- [ ] Add memory consolidation/review cadence.
- [ ] Add stale/contradictory memory review workflow.
- [ ] Add memory write audit expectations for significant changes.

## Orientation guide for future Pi sessions

When asked to expand Pi agent capabilities:

1. Read `docs/INDEX.md` and `docs/LOOKUP.json`.
2. Read this file: `resources/analysis/agent-capability-roadmap.md`.
3. Check `resources/analysis/TRACKING.md` for implementation status.
4. Identify the layer being changed: extension, prompt, skill, subagent, MCP, memory, wrapper, policy, or docs.
5. Use the layer decision guide above before adding always-loaded instructions.
6. Prefer source-managed changes under `modules/programs/cli/pi/**`.
7. Validate docs-only changes with JSON/Markdown sanity and `git diff --check`.
8. Validate behavior changes with the relevant `pi-admin` checks.
9. Sync runtime only through `pi-admin sync ...` or the documented profile init commands.
10. Save durable discoveries to Engram after significant decisions.

## Immediate next slice recommendation

Start with **P1 resource discovery** because it supports every later extension/skill/prompt improvement without changing security behavior:

1. `pi-admin resource-inventory --json`
2. prompt/skill linting
3. generated extension manifest validation
4. route this roadmap and inventory commands through `docs/LOOKUP.json`

Then move to **P1 explain-profile** and **P0 policy-test**. Defer `pi-sandbox` until permission tests are real and repeatable.
