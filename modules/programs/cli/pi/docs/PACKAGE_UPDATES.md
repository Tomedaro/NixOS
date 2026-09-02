# Pi Package Updates

This setup pins the security/control Pi packages in `settings/global.json`.

## Why packages are pinned

Pi packages can load extensions, skills, prompts, and themes. Extensions are executable code in the Pi process. The permission system and MCP adapter are therefore part of the trusted computing base for this setup.

Pinned packages make normal rebuilds and bootstraps reproducible. Do not switch them back to floating `npm:package` strings casually.

## How to update intentionally

1. Run `pi-compat-check` to record the current local state.
2. Check the current version in `~/.pi/agent/npm/package-lock.json` or with intentional npm metadata lookup: `PI_COMPAT_ONLINE=1 pi-compat-check`.
3. Read the package changelog/source for the new version.
4. Edit `modules/programs/cli/pi/settings/global.json`.
5. Run `sudo nixos-rebuild test --flake /home/daniil/NixOS#Singularity`.
6. Run `pi-bootstrap`.
7. Run `pi-compat-check`, `pi-doctor`, and `pi-drift-check`.
8. Run `pi update --extensions` only when you intentionally want Pi to install/update the pinned resources.
9. Confirm `pi-compat-check` reports no missing control packages before using `pi-readonly` or policy-backed profiles.

## Package update checklist

When updating any Pi extension or package pin:

1. **Update exact package pins intentionally.**
   - Edit `modules/programs/cli/pi/settings/global.json`.
   - Do not use `npm update` or `npm audit fix` as the update strategy.

2. **Regenerate the source global-pins lockfile if package pins changed.**
   - Create an isolated temp directory.
   - Write `package.json` with exact dependency versions from `settings/global.json`.
   - Run `npm install --package-lock-only --ignore-scripts` inside the temp dir.
   - Copy generated `package.json` and `package-lock.json` to `modules/programs/cli/pi/npm/global-pins/`.
   - Verify root dependencies match source pins.
   - Do not copy from runtime `~/.pi/agent/npm/package-lock.json`.

3. **Run validation checks after editing.**
   - `pi-admin npm-check` — verify direct versions match pins
   - `pi-admin compat` — verify peerDependency ranges
   - `pi-admin mcp-check` — verify MCP invariants, `directTools`, lifecycle
   - `pi-source-check` — verify source integrity (170+ checks)
   - Nix build if Nix/module files changed

4. **Review these aspects for every updated package.**
   - Direct version changes
   - peerDependency ranges
   - Lifecycle scripts (via `pi-admin npm-check`)
   - Runtime fetch surfaces (via `pi-admin npm-check`)
   - MCP `directTools` and lifecycle settings
   - Anki/read-only constraints if touching study MCP
   - Source/runtime drift after activation (via `pi-admin drift`)

5. **Activate and confirm.**
   - `sudo nixos-rebuild switch --flake .#Singularity`
   - Re-run all validation checks
   - Confirm `pi-admin drift` is clean

> For future lockfile/offline work: this belongs to P6C6 or later, not the normal package update flow.

## Durable-change rule

Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` as the durable source of truth for this Nix-managed setup. Those commands mutate runtime settings. Durable changes belong in this module and then get synced into runtime.
