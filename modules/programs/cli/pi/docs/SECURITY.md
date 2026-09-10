# Security Model

## Important boundary

Pi profiles are policy and ergonomics layers, not OS sandboxes.

- Plain `pi` is the daily smart launcher.
- `PI_PROFILE=cautious pi`, `pi-readonly`, and `pi-safe` are cautious policy-backed modes only.
- `PI_OFFLINE=1` / `--offline` disables Pi startup network operations; it is not a complete network sandbox.
- Extensions are code and can run with user permissions when loaded.

## Historical symlink finding

A previous test showed policy-only external-directory checks allowed reading through a project-local symlink whose real target was outside the project. That means textual path checks are insufficient for a hard security boundary.

Read `docs/SECURITY_LIMITATIONS.md` for the exact limitation and future hardening direction.

## Secret rules

Never place API keys, tokens, passwords, OAuth material, or private SSH/GPG material in Nix files. Nix store paths can be readable.

Default policies still deny obvious secret paths such as:

- `~/.ssh*`
- `~/.gnupg*`
- `~/.pi/agent/auth.json*`

Do not rely only on pattern denies. Keep sensitive paths outside project scopes and do not use Pi profiles as a hard boundary for untrusted repositories.

## NPM supply-chain posture

### Surfaces

The Pi setup uses npm in three ways:

1. **Pi extension packages** pinned in `settings/global.json` — direct dependency declarations with exact versions.
2. **Runtime npm installation** under `~/.pi/agent/npm` — resolved and installed by Pi's extension manager.
3. **Runtime npm fetch exceptions** — most notably the Anki MCP server started via `npx` in the study profile.

### Current mitigations

| Mitigation | Mechanism |
|------------|-----------|
| Exact direct pins | 18 packages pinned at exact versions in `settings/global.json` |
| Installed-version checks | `pi-admin npm-check` verifies runtime installed versions match source pins |
| Peer compatibility checks | `pi-admin compat` reports peerDependency warnings |
| MCP command checks | `pi-admin mcp-check` validates `directTools`, lifecycle, and unpinned commands across all profiles |
| Anki MCP constraints | Study-only profile, `directTools=false`, `--read-only` flag, 30 excluded write tools |
| mcp-nixos pinning | Flake/store pinned — no longer fetched via `npm` at runtime |
| Lifecycle visibility | `pi-admin npm-check` reports lifecycle scripts for direct and transitive packages |
| Source global-pins lockfile | `modules/programs/cli/pi/npm/global-pins/` — covers 18 repo-owned packages (audit/comparison only) |
| Source lockfile comparison | `pi-admin npm-check` compares source lockfile root deps against source pins, runtime install, and runtime lockfile entries |
| Runtime root extras classification | `pi-admin npm-check` classifies extra runtime root packages as profile extras, known extras, or unknown |

### Current gaps

| Gap | Impact |
|-----|--------|
| Source lockfile covers only 18 global pins | Full runtime npm tree (25 root deps) not source-reproducible |
| `ignore-scripts=false` | Lifecycle scripts run during install without gating |
| Runtime lockfile is generated state | Not a source-of-truth for the full runtime tree |
| No online registry metadata/signature checks by default | Package provenance is not cryptographically verified |

### Accepted monitored risks

| Risk | Reason accepted | Monitoring |
|------|-----------------|------------|
| `pi-lens@3.8.50` postinstall downloads grammars | Functional requirement; grammars enable language-aware code tools | `pi-admin npm-check` reports script presence |
| Anki MCP exact-version `npx -y @ankimcp/anki-mcp-server@0.19.2` | Study-only, read-only, direct tools disabled, write tools excluded | `pi-admin mcp-check` tracks the exception |
| `pi-powerline-footer@0.6.1` peer warning | Non-blocking UI package; installed version works in practice | `pi-admin compat` reports warning |
| `pi-simplify@0.2.2` peer warning | Non-blocking utility; installed version works in practice | `pi-admin compat` reports warning |

### Operating rules

- Do not use broad npm mutation commands (`npm install`, `npm update`, `npm audit fix`) for normal maintenance.
- Do not use `npm audit fix` as a blind remediation.
- Prefer exact-pin edits in `settings/global.json` with explicit review for package updates.
- Treat runtime npm lockfiles as evidence of what is installed, not as source of truth.
- Keep online npm metadata checks opt-in (`PI_NPM_CHECK_ONLINE=1`, `PI_COMPAT_ONLINE=1`).
- Re-run these checks after any package or MCP change:
  - `pi-admin npm-check`
  - `pi-admin compat`
  - `pi-admin mcp-check`
  - `pi-source-check`
  - Nix build if Nix/module files changed

### What is not claimed

- Transitive dependencies are not locked by source.
- Lifecycle scripts are not disabled.
- Anki `npx` usage is not risk-free.
- npm registry signatures are not currently verified.
- `npm ci` is not currently used.

## Cautious mode

Cautious mode:

1. Loads only the pinned `pi-permission-system` extension.
2. Uses `policies/safe.jsonc`.
3. Disables normal project context files, extensions, skills, prompt templates, and themes.
4. Restricts built-in tools to read-style tools.
5. Launches in an empty readonly workspace by default.

It is still not a sandbox. Real isolation requires canonical path checks and/or OS-level isolation such as bubblewrap or an audited sandbox extension.
