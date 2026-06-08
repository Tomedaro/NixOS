# Improvement Plan — Progress Tracking

**Started:** 2026-06-08
**Full plan:** `improvement-plan.md`

Status legend:
- ❌ Not started
- 🔄 In progress
- ✅ Done
- ⏸️ Skipped / deferred

---

## Phase 0 — Baseline validation

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 0.1 | `pi-admin source-check` command | ❌ | |
| 0.2 | Generated-script smoke checks in pi-doctor | ❌ | |

## Phase 1 — Security hardening quick wins

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 1.1 | Policy preflight in wrapperPrelude | ❌ | |
| 1.2 | Version verification helper | ❌ | |
| 1.3 | `pi-cautious` alias | ❌ | |
| 1.4 | `pi-trusted` friction | ❌ | |
| 1.5 | Launch metadata stamping | ❌ | |

## Phase 2 — Admin introspection

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 2.1 | `pi-admin explain-profile` | ❌ | |
| 2.2 | `pi-admin mcp-check` | ❌ | |
| 2.3 | `pi-admin policy-lint` | ❌ | |
| 2.4 | Dry-run / diff for sync/drift | ❌ | |

## Phase 3 — Home Manager module interface

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 3.1 | `programs.pi.enable` | ❌ | |
| 3.2 | Core path options | ❌ | |
| 3.3 | Basic assertions | ❌ | |

## Phase 4 — Declarative global runtime

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 4.1 | Activation drift warning | ❌ | |
| 4.2 | Activation global sync | ❌ | |
| 4.3 | Immutable files to home.file | ❌ | |

## Phase 5 — MCP pinning

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 5.1 | MCP flake/store pin | ❌ | |
| 5.2 | Strict mcp-check | ❌ | |

## Phase 6 — Supply-chain tightening

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 6.1 | Exact version enforcement | ❌ | |
| 6.2 | Package lock/stamp | ❌ | |
| 6.3 | Nix-package permission-system | ❌ | |

## Phase 7 — Shell maintainability

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 7.1 | writeShellApplication for small scripts | ❌ | |
| 7.2 | Shared wrapper preflight | ❌ | |
| 7.3 | Move shell bodies out of Nix strings | ❌ | |

## Phase 8 — Sandbox

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 8.1 | Experimental pi-sandbox | ❌ | |
| 8.2 | Sandbox regression tests | ❌ | |
| 8.3 | Aliasing decision | ❌ | |

## Phase 9 — Documentation

| # | Task | Status | Commit/Notes |
|---|---|---|---|
| 9.1 | Architecture diagram | ❌ | |
| 9.2 | Threat model | ❌ | |
| 9.3 | Runbooks | ❌ | |
