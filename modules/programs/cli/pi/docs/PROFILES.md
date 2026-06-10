# Pi Profiles

## Preferred usage

Use plain:

```bash
pi
```

The smart launcher selects the right mode automatically. See `docs/SMART_LAUNCHER.md`.

## `pi-raw`

Runs the wrapped upstream Pi binary directly, bypassing the smart launcher.

**MCP caveat:** `pi-raw` skips profile-aware MCP switching. It inherits whatever
`~/.pi/agent/mcp.json` was last set by a wrapper launch or `pi-admin sync`.
If the last active profile was `study`, Anki MCP tools may still be present.
Do not use `pi-raw` for Anki work. To reset MCP to the global (no-Anki) config,
run `pi-admin sync global` or launch any non-study wrapper such as `pi-nixos`.

## `pi-admin`

Maintenance interface for status, sync, doctor, drift, compatibility, and security notes.

## NixOS mode

Selected automatically inside `/home/daniil/NixOS`.

It creates a git checkpoint under `.pi/checkpoints/`, appends NixOS self-maintenance instructions, and explicitly loads:

- `resources/nixos/prompts/`
- `resources/nixos/skills/pi-nix-self-maintenance/`

Useful prompt commands include `/setup`, `/status`, `/security`, and `/pi-change`.

## Study mode

Selected automatically inside `~/Learning`.

Runs `pi-study-init --quiet` before launch and uses the local-first study resources.

## Study tutor mode

Use explicitly:

```bash
PI_PROFILE=study-tutor pi
```

It enables heavier tutor packages.

## Work mode

Selected automatically inside non-NixOS git/project directories.

It refuses to manage `/home/daniil/NixOS`; use NixOS mode there.

## Research mode

Fallback for ordinary directories.

## Trusted mode

Use explicitly:

```bash
PI_PROFILE=trusted pi
```

More permissive, but still not a sandbox.

## Cautious mode

Use explicitly only when you understand the limitation:

```bash
PI_PROFILE=cautious pi
```

or the deprecated compatibility aliases:

```bash
pi-readonly
pi-safe
```

Cautious mode is policy-backed convenience, not a security sandbox. It launches in an empty readonly workspace by default. Do not use it as a hard boundary for untrusted repositories.
