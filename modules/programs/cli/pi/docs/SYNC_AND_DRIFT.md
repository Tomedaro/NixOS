# Sync and Drift

## Preferred interface

Use:

```bash
pi-admin sync
pi-admin status
pi-admin drift
pi-admin compat
```

The older commands still exist:

```bash
pi-bootstrap
pi-study-init
pi-study-tutor-init
PI_WORK_DIR=/path/to/project pi-work-init
pi-drift-check
pi-compat-check
```

## Source of truth

Durable setup lives under:

```text
/home/daniil/NixOS/modules/programs/cli/pi/
```

Runtime files under `~/.pi/agent`, `~/Learning/.pi`, and project `.pi` directories are generated or user-owned depending on whether they are managed or seeded.

## Managed vs seed files

Managed files are overwritten from source and tracked by `.pi/managed-files.txt`.

Seed files are copied only if missing and then become user-owned.

If a previously managed file disappears from source, sync moves the runtime copy to `.pi/managed-stale/`.

## State stamp

`pi-admin sync` writes:

```text
~/.pi/agent/nix-managed-state.json
```

This records the source root, source hash, sync time, and Pi version for quick status checks.

## Package/runtime boundary

Do not set `PI_PACKAGE_DIR` in wrappers. Use `NPM_CONFIG_PREFIX` for npm install prefix. See `docs/package-runtime-boundary.md`.
