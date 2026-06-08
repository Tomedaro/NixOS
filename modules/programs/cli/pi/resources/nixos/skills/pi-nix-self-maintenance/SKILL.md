---
name: pi-nix-self-maintenance
description: Maintain this NixOS-managed Pi setup using the setup wiki, source-managed settings/resources, safe sync commands, and focused verification.
---
<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->


# Pi Nix Self-Maintenance Skill

Use this skill when Daniil asks to change, explain, debug, extend, harden, or clean up the Pi setup.

## Workflow

1. Read `modules/programs/cli/pi/docs/INDEX.md`.
2. Use `modules/programs/cli/pi/docs/LOOKUP.json` for routing.
3. Read the smallest relevant source files.
4. Decide whether the change belongs to:
   - global behavior or response style in `resources/global/AGENTS.md`
   - global settings/resources
   - a profile wrapper
   - a policy
   - study local-first resources
   - study-tutor resources/packages
   - work resources
   - docs/wiki
5. Patch source-managed files only.
6. Do not edit runtime `.pi` state directly unless explicitly debugging drift.
7. Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` for durable setup changes. Patch source-managed settings/resources/policies instead.
8. Give exact `pi-admin` sync/check commands, plus lower-level compatibility commands only when useful.

## Verification checklist

For Nix source changes, suggest:

```bash
cd /home/daniil/NixOS
nix-instantiate --parse modules/programs/cli/pi/default.nix >/dev/null
nix-instantiate --parse modules/programs/cli/pi/home-module.nix >/dev/null
nix-instantiate --parse modules/programs/cli/pi/package.nix >/dev/null
nix-instantiate --parse modules/programs/cli/pi/scripts.nix >/dev/null
nix-instantiate --parse modules/programs/cli/pi/wrappers.nix >/dev/null
sudo nixos-rebuild test --flake /home/daniil/NixOS#Default
```

For runtime sync, suggest only the relevant commands:

```bash
pi-admin sync
pi-admin status
pi-admin drift
pi-admin compat
```

## Guardrails

- Never claim runtime state is synced unless the user ran the sync command or you have inspected it.
- For small global behavior changes, prefer editing `resources/global/AGENTS.md` directly; do not read wrappers, scripts, policies, or package files unless needed.
- Never add secrets to Nix files.
- Never widen policy from `ask`/`deny` to `allow` without explaining risk.
- Never use `pi-work` for `/home/daniil/NixOS` unless the user explicitly overrides with `PI_WORK_ALLOW_NIXOS=1`.
- Preserve package order during merges.
- Keep security/control packages pinned unless the user explicitly asks to update them.
