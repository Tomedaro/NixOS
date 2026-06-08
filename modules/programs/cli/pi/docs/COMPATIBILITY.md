# Compatibility Preflight

Run `pi-compat-check` after changing Pi package pins, after updating the Nix-provided Pi binary, or before relying on a newly applied setup.

## What it checks

- The installed Pi version is visible.
- The Pi CLI advertises the flags used by the wrappers, such as `--offline`, `--no-extensions`, `--tools`, `--prompt-template`, and `--skill`.
- The pinned control package specs in `settings/global.json` are visible.
- Installed package versions under `~/.pi/agent/npm/node_modules` match the pinned specs. Missing pinned control packages are warnings/failures, not harmless skips.
- Peer dependencies are printed when package metadata exposes them.

## Offline by default

`pi-compat-check` does not query npm by default. To inspect live npm metadata intentionally, run:

```bash
PI_COMPAT_ONLINE=1 pi-compat-check
```

Use this before intentionally updating package pins. Do not treat live npm metadata as source of truth for the running setup until you edit `settings/global.json`, rebuild/test, and resync with `pi-bootstrap`.

## Why this exists

The Pi binary is provided by Nix, while Pi packages are installed by npm into `~/.pi/agent/npm`. Versioned npm package specs reduce accidental movement, but they are not the same as a Nix flake lock for the entire transitive dependency graph. `pi-readonly` also depends on the pinned `pi-permission-system` package being installed, because it refuses to start without that extension.
