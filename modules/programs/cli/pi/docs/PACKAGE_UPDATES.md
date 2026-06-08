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
5. Run `sudo nixos-rebuild test --flake /home/daniil/NixOS#Default`.
6. Run `pi-bootstrap`.
7. Run `pi-compat-check`, `pi-doctor`, and `pi-drift-check`.
8. Run `pi update --extensions` only when you intentionally want Pi to install/update the pinned resources.
9. Confirm `pi-compat-check` reports no missing control packages before using `pi-readonly` or policy-backed profiles.

## Durable-change rule

Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` as the durable source of truth for this Nix-managed setup. Those commands mutate runtime settings. Durable changes belong in this module and then get synced into runtime.
