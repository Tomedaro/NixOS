<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->

# Pi NixOS self-maintenance instructions

These instructions are explicitly loaded by `pi-nixos`.

When modifying or explaining this Pi setup:

1. Read `modules/programs/cli/pi/docs/INDEX.md` first.
2. Use `modules/programs/cli/pi/docs/LOOKUP.json` to locate exact relevant source files.
3. Prefer source-managed changes under `modules/programs/cli/pi/**` over direct edits to `~/.pi/agent/**`, `~/Learning/.pi/**`, or work project `.pi/**`.
4. If runtime and source disagree, report drift and suggest the precise sync command: `pi-bootstrap`, `pi-study-init`, `PI_WORK_DIR=... pi-work-init`, or `pi-drift-check`.
5. Do not use broad repository search until the setup wiki routes are exhausted.
6. Do not widen permissions or add packages without explaining why and where they belong: global, study, study-tutor, work, research, or trusted.
7. Treat `pi-readonly`/`pi-safe` as cautious read-only profiles, not OS sandboxes.
8. Do not manage `/home/daniil/NixOS` with `pi-work`; use `pi-nixos`.
9. Preserve package order when merging settings. The permission package should stay before other normal global packages.
10. For project trust issues, tell the user to run the wrapper interactively, use `/trust` if prompted, exit, then restart the wrapper.
11. After package pin or Pi binary changes, route to `pi-compat-check` before claiming the setup is healthy.

Important entrypoints:

- `modules/programs/cli/pi/docs/INDEX.md`
- `modules/programs/cli/pi/docs/LOOKUP.json`
- `modules/programs/cli/pi/default.nix`
- `modules/programs/cli/pi/home-module.nix`
- `modules/programs/cli/pi/scripts.nix`
- `modules/programs/cli/pi/wrappers.nix`
- `modules/programs/cli/pi/settings/`
- `modules/programs/cli/pi/policies/`
- `modules/programs/cli/pi/resources/`
