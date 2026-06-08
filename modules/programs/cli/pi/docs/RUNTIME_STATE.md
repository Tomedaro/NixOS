# Runtime State and Source of Truth

## Source-managed files

Edit these under `/home/daniil/NixOS/modules/programs/cli/pi/`:

- `settings/*.json`
- `policies/*.jsonc`
- `mcp/global.json`
- `resources/**`
- `docs/**`
- `scripts.nix`
- `wrappers.nix`

Then run the relevant sync command.

## Runtime files

Generated or synchronized runtime files live under:

- `~/.pi/agent/`
- `~/Learning/.pi/`
- work project `.pi/` directories selected by `PI_WORK_DIR`

Do not edit runtime files as the durable source of truth unless you are experimenting. Move durable changes back into the Nix source tree.

## Sync commands

```bash
pi-bootstrap      # global settings, MCP, policies, AGENTS, DeepSeek provider
pi-study-init     # ~/Learning local-first resources
pi-study-tutor-init
PI_WORK_DIR=/path/to/project pi-work-init
pi-drift-check
```

## Managed vs seed files

Managed files are overwritten from source and tracked by `.pi/managed-files.txt`.

Seed files are created only if missing. They are user-owned after creation.

If a previously managed file disappears from source, sync moves the runtime copy to:

```text
.pi/managed-stale/
```

Review and delete or archive those stale files manually.
