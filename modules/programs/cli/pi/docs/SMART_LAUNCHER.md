# Smart Launcher

The user-facing `pi` command is a NixOS-managed smart launcher.

## Detection order

1. `PI_PROFILE`, if set.
2. `/home/daniil/NixOS` or its children -> `nixos`.
3. `~/Learning` or its children -> `study`.
4. Any non-NixOS git repository -> `work`.
5. Project marker in current directory -> `work`.
6. Fallback -> `research`.

Project markers are `.git`, `flake.nix`, `package.json`, `pyproject.toml`, or `Cargo.toml`.

## Overrides

```bash
PI_PROFILE=raw pi
PI_PROFILE=nixos pi
PI_PROFILE=study pi
PI_PROFILE=study-tutor pi
PI_PROFILE=work pi
PI_PROFILE=research pi
PI_PROFILE=trusted pi
PI_PROFILE=cautious pi
```

## Raw Pi

Use `pi-raw` to bypass the smart launcher and run the wrapped upstream Pi binary directly.
