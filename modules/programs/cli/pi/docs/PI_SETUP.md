# Pi Setup Big Picture

This module manages Pi as a small NixOS-owned appliance with a simple daily interface.

## Daily interface

Use:

```bash
pi
```

The smart launcher detects the current directory and chooses NixOS, study, work, or research mode. Use `pi-raw` only when you want the upstream Pi binary directly.

Maintenance is grouped under:

```bash
pi-admin status
pi-admin sync
pi-admin doctor
pi-admin drift
pi-admin compat
pi-admin security
```

## Source-managed layer

Durable configuration lives under `modules/programs/cli/pi/**`.

Important files:

- `default.nix` - tiny Nix entrypoint.
- `home-module.nix` - Home Manager package wiring.
- `package.nix` - wrapped upstream Pi package and Pi-specific npm wrapper.
- `scripts.nix` - bootstrap/init/doctor/drift/compatibility commands.
- `wrappers.nix` - smart launcher, raw launcher, admin command, and compatibility wrappers.
- `settings/` - declarative settings and provider metadata.
- `policies/` - permission-system policies.
- `resources/` - managed and seeded prompts, skills, and instructions.
- `docs/` - this setup wiki.

## Runtime layer

Runtime files are generated under:

- `~/.pi/agent/`
- `~/Learning/`
- work project directories selected by `PI_WORK_DIR` or by smart launcher detection

Do not edit generated runtime files for durable changes. Edit source files and run `pi-admin sync`.

## Safety layer

Profiles and policies are convenience layers, not security sandboxes. Cautious mode is intentionally described as cautious rather than safe because policy-only file restrictions previously failed a symlink escape test.

Read `docs/SECURITY_LIMITATIONS.md` before relying on any profile for sensitive data protection.
