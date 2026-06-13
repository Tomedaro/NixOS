# Improvement Plan — Progress Tracking
**Started:** 2026-06-08
**Last updated:** 2026-06-12
**Full plan:** `improvement-plan.md`

Status legend:
- ❌ Not started
- 🔄 In progress
- ✅ Done
- ⏸️ Skipped / deferred

## Phase 0 — Baseline validation — ✅ COMPLETE

| # | Task | Status | Commit/Notes |
| 0.1 | `pi-admin source-check` cmd | ✅ | `8c7e726`, `7ddd9a8`, `f966da2` |
| 0.2 | Generated-script smoke checks in pi-doctor | ✅ | `ae3870c` |

## Phase 1 — Security hardening quick wins

| # | Task | Status | Commit/Notes |
| 1.1 | Policy preflight in wrapperPrelude | ✅ | `98b5787` |
| 1.2 | Narrow permission version check | ✅ | `98b5787` |
| 1.3 | `pi-cautious` alias | ✅ | Wrapper defined, aliases `pi-readonly`/`pi-safe`. |
| 1.4 | `pi-trusted` friction | ❌ | |
| 1.5 | Launch metadata stamping | ❌ | |

## Phase 2 — Admin introspection

| # | Task | Status | Commit/Notes |
| 2.1 | `pi-admin explain-profile` | ❌ | |
| 2.2 | `pi-admin mcp-check` | ✅ | Static MCP validation — directTools, lifecycle, unpinned commands |
| 2.3 | `pi-admin policy-lint` | ✅ | Static structural checks on all 6 profile policy files |
| 2.4 | Dry-run / diff for sync/drift | ❌ | |

## Phase 3 — Home Manager module interface

| # | Task | Status | Commit/Notes |
| 3.1 | `programs.pi.enable` | ❌ | |
| 3.2 | Core path options | ❌ | |
| 3.3 | Basic assertions | ❌ | |

## Phase 4 — Declarative global runtime

| # | Task | Status | Commit/Notes |
| 4.1 | Activation drift warning | ❌ | |
| 4.2 | Activation global sync | ❌ | |
| 4.3 | Immutable files to home.file | ❌ | |

## Phase 5 — MCP pinning

| # | Task | Status | Commit/Notes |
| 5.1 | MCP flake/store pin | ✅ | mcp-nixos flake input + wrapper + generated JSON |
| 5.2 | Static mcp-check | ✅ | pi-admin mcp-check — 40 checks, 0 failures, 1 warning for Anki npx |

## Phase 6 — Supply-chain tightening

| # | Task | Status | Commit/Notes |
| 6.1 | Exact version enforcement | ❌ | |
| 6.2 | pkg lock/stamp | ❌ | |
| 6.3 | Nix-package permission-system | ❌ | |

### P6A — Read-only npm supply-chain check

| # | Task | Status | Commit/Notes |
| A.1 | `pi-admin npm-check` script | ✅ | Read-only auditor: source pins, runtime versions, lockfiles, npm config, lifecycle scripts, fetch surfaces, compat pointer |
| A.2 | pi-admin wiring | ✅ | `pi-admin npm-check` dispatch and help |
| A.3 | Online mode deferred | ⏸️ | Default offline; PI_NPM_CHECK_ONLINE=1 deferred to P6F

## Phase 7 — Shell maintainability

| # | Task | Status | Commit/Notes |
| 7.1 | `writeShellApplication` for small scripts | ❌ | |
| 7.2 | Shared wrapper preflight | ❌ | |
| 7.3 | Move shell bodies out of Nix strings | ❌ | |

## Phase 8 — Sandbox

| # | Task | Status | Commit/Notes |
| 8.1 | Experimental pi-sandbox | ❌ | |
| 8.2 | Sandbox regression tests | ❌ | |
| 8.3 | Aliasing decision | ❌ | |

## Phase 9 — Documentation

| # | Task | Status | Commit/Notes |
| 9.1 | Architecture diagram | ❌ | |
| 9.2 | Threat model | ❌ | |
| 9.3 | Runbooks | ❌ | |

## Bonus — Prompt debugging

| # | Task | Status | Commit/Notes |
| — | pi-permission-system prompt tuning | ✅ | `8e24063` |

---

## 2026-06 Engram/Hermes/MCP hardening — ✅ COMPLETE

New section for the ChatGPT-reviewed memory and MCP hardening work.

| # | Task | Status | Commit/Notes |
| — | Engram Go package derivation | ✅ | `d8abe09` |
| — | Engram project config | ✅ | `c5c6fe5` |
| — | Engram MCP server config (directTools: false) | ✅ | `8358270` |
| — | Engram binary wiring in wrappers/module | ✅ | `c21973b` |
| — | Engram DB gitignore | ✅ | `e36bd77` |
| — | Hermes compact coexistence config | ✅ | Deployed to `~/.pi/agent/hermes-memory-config.json` (policy-only + compact), wired into Nix bootstrap |
| — | Engram + Hermes memory policy in AGENTS.md | ✅ | `26fa485` |
| — | SDD parent-only memory orchestration policy | ✅ | Documented in AGENTS.md |
| — | Hermes memory doctor (`pi-hermes-doctor`) | ✅ | DB backup, integrity checks, Node ABI drift detection |
| — | MCP token-footprint audit | ✅ | Completed — all lazy, 2 direct tools total, no duplicates |
| — | Drift tracking for Hermes config | ✅ | `OK: Hermes config` in pi-admin drift |
| — | Cautious mode alias | ✅ | `pi-cautious` wrapper, aliases `pi-readonly`/`pi-safe` |
| — | Dev tooling packages | ✅ | nixd, nixfmt, statix, deadnix, ruff, pyright, stylua, luacheck |
| — | NVChad python LSP cleanup | ✅ | `74a364c` |

---

## P0 — Fix drift noise

| # | Task | Status | Commit/Notes |
| 0.1 | Add mcp/work.json and mcp/research.json source files | ✅ | Creates empty mcpServers; drift now reports OK |

## P1 — Compatibility and permission enforcement

| # | Task | Status | Commit/Notes |
| 1.1 | peerDependency semver enforcement in pi-admin compat | ✅ | Warn-only; detects powerline-footer and simplify incompatibilities |
| 1.2 | `pi-admin policy-test` runtime permission regression tests | ❌ | Verify safe/nixos/trusted profile behavior, secret path denial, pi-raw bypass |
| 1.3 | `pi-admin policy-lint` | ✅ | 119 checks, 0 failures on current profiles |
| 1.4 | `pi-admin explain-profile` | ❌ | Profile detail introspection |

## P2 — MCP future-proofing

| # | Task | Status | Commit/Notes |
| 2.1 | `pi-admin mcp-check` | ✅ | Static MCP validation only (40 checks, 0 failures); pinning handled in P2.2 |
| 2.2 | Pin mcp-nixos through flake/store path | ✅ | Flake input + wrapper; absolute store path; directTools: true explicit; drift-check follow-up |
| 2.3 | Anki MCP pinning decision | ✅ | Accepted exception: study-only, npx -y, directTools: false, 30 excluded tools, --read-only. Revisit if unreliable |

## P3 — Memory architecture documentation

| # | Task | Status | Commit/Notes |
| 3.1 | Add docs/MEMORY.md | ✅ | Created — architecture overview, coexistence rules, SDD orchestration, config, validation |
| 3.2 | Update INDEX, LOOKUP, CHANGE_ROUTING, DECISIONS | ✅ | All routing updated; stale `pi-study avoids external memory` decision clarified |

## P4 — Activation-time sync/drift integration

| # | Task | Status | Commit/Notes |
| 4.1 | Activation drift warning | ❌ | Warning-only on HM activation |
| 4.2 | Activation global sync option | ❌ | programs.pi.syncGlobalOnActivation |
| 4.3 | Immutable files to home.file | ❌ | AGENTS.md, policies — NOT mutable files |

## P5 — NPM/runtime supply-chain hardening

| # | Task | Status | Commit/Notes |
| 5.1 | Installed package stamp | ❌ | nix-managed-packages.json |
| 5.2 | npm audit/signature/provenance report | ❌ | pi-admin npm-audit |
| 5.3 | Enforce exact installed versions for control packages | ❌ | In pi-admin compat |
| 5.4 | Evaluate lockfile or Nix-packaged critical extensions | ❌ | Verify, do not implement all at once |

## P6 — Script maintainability

| # | Task | Status | Commit/Notes |
| 6.1 | Extract domain script modules | ❌ | Only after P0-P5 tests exist |
| 6.2 | Reduce pi-bootstrap / pi-admin sync duplication | ❌ | |
| 6.3 | Shellcheck-style checks | ❌ | |

## P7 — Home Manager module interface

| # | Task | Status | Commit/Notes |
| 7.1 | `programs.pi.enable` | ❌ | |
| 7.2 | Core path options | ❌ | |
| 7.3 | Basic assertions | ❌ | |

## P8 — Sandbox experiments

| # | Task | Status | Commit/Notes |
| 8.1 | Experimental pi-sandbox | ❌ | Only after P1 permission tests stable |
| 8.2 | Sandbox regression tests | ❌ | |
| 8.3 | Aliasing decision | ❌ | |

## P9 — Documentation cleanup

| # | Task | Status | Commit/Notes |
| 9.1 | Architecture diagram | ❌ | |
| 9.2 | Threat model | ❌ | |
| 9.3 | Runbooks | ❌ | |
