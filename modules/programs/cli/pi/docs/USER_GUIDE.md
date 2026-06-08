# Pi User Guide

## Daily command

Use plain:

```bash
pi
```

The NixOS-managed launcher detects where you are and chooses the mode:

- `/home/daniil/NixOS` -> NixOS mode
- `~/Learning` -> study mode
- another project or git repository -> work mode
- ordinary directory -> research mode

Use `PI_PROFILE=... pi` only when you want to override detection.

## Escape hatch

Use raw upstream Pi with:

```bash
pi-raw
```

## Maintenance

Use:

```bash
pi-admin status
pi-admin sync
pi-admin doctor
pi-admin drift
pi-admin compat
```

The older helper commands still exist for compatibility, but `pi-admin` is the preferred user interface.

## Setup questions inside Pi

When running from `/home/daniil/NixOS`, smart `pi` loads setup prompts. Use:

```text
/setup
/status
/security
/pi-change
```

For normal questions, just ask. Global instructions tell Pi to read `docs/INDEX.md` and `docs/LOOKUP.json` before broad searches.

## Durable changes

Do not make durable setup changes by editing runtime files under `~/.pi/agent`, `~/Learning/.pi`, or project `.pi` directories.

Edit source files under:

```text
/home/daniil/NixOS/modules/programs/cli/pi/
```

Then run:

```bash
pi-admin sync
pi-admin drift
```
