# Security Model

## Important boundary

Pi profiles are policy and ergonomics layers, not OS sandboxes.

- Plain `pi` is the daily smart launcher.
- `PI_PROFILE=cautious pi`, `pi-readonly`, and `pi-safe` are cautious policy-backed modes only.
- `PI_OFFLINE=1` / `--offline` disables Pi startup network operations; it is not a complete network sandbox.
- Extensions are code and can run with user permissions when loaded.

## Historical symlink finding

A previous test showed policy-only external-directory checks allowed reading through a project-local symlink whose real target was outside the project. That means textual path checks are insufficient for a hard security boundary.

Read `docs/SECURITY_LIMITATIONS.md` for the exact limitation and future hardening direction.

## Secret rules

Never place API keys, tokens, passwords, OAuth material, or private SSH/GPG material in Nix files. Nix store paths can be readable.

Default policies still deny obvious secret paths such as:

- `~/.ssh*`
- `~/.gnupg*`
- `~/.pi/agent/auth.json*`

Do not rely only on pattern denies. Keep sensitive paths outside project scopes and do not use Pi profiles as a hard boundary for untrusted repositories.

## Cautious mode

Cautious mode:

1. Loads only the pinned `pi-permission-system` extension.
2. Uses `policies/safe.jsonc`.
3. Disables normal project context files, extensions, skills, prompt templates, and themes.
4. Restricts built-in tools to read-style tools.
5. Launches in an empty readonly workspace by default.

It is still not a sandbox. Real isolation requires canonical path checks and/or OS-level isolation such as bubblewrap or an audited sandbox extension.
