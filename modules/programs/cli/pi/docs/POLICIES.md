# Policies

Policies live under `policies/*.jsonc` and are synced to `~/.pi/agent/policies/<profile>/pi-permissions.jsonc` by `pi-admin sync global` / `pi-bootstrap`.

## Hardening rule

Avoid broad bash allow rules. Do not allow patterns like:

```json
"grep*": "allow"
"find*": "allow"
"ls*": "allow"
"git *": "allow"
```

Those are shell strings and can bypass intended path boundaries. Prefer Pi built-in read/grep/find/ls tools and exact safe commands.

## Profiles

- `safe.jsonc` - cautious read-only policy, not a sandbox.
- `nixos.jsonc` - NixOS work; file edits allowed, bash mostly ask.
- `study.jsonc` - study project; writes allowed inside project, external dirs denied by policy.
- `work.jsonc` - work projects; writes ask by default.
- `research.jsonc` - research, mostly ask.
- `trusted.jsonc` - more permissive, still asks for bash/destructive operations.

## Source-management guardrail

Policies discourage runtime-only Pi package/config mutation:

```json
"pi install*": "deny"
"pi remove*": "deny"
"pi uninstall*": "deny"
"pi config*": "ask"
"pi update*": "ask"
```

Durable changes should be made in `modules/programs/cli/pi/**`, then synced with `pi-admin sync`.

## Cautious policy

`safe.jsonc` is intentionally strict: bash denied, writes denied, MCP denied, and only read-style tools allowed. The wrapper also disables normal extension/resource discovery and loads only the pinned permission extension.

This is still not a security sandbox. See `docs/SECURITY_LIMITATIONS.md`.
