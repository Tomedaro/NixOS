# Module ownership

The directory name should describe who owns a piece of configuration, not merely where
it happened to be imported first.

- `modules/core/`: machine-wide operating-system policy and cross-cutting foundations.
  Examples: boot, hardware baseline, networking, security, system policy, users.
- `modules/desktop/`: desktop/window-manager integration and components whose lifecycle
  belongs to a desktop session.
- `modules/programs/`: applications and user-facing program configuration, including
  shells and the gaming application bundle.
- `modules/services/`: independently identifiable long-running services such as
  Syncthing.
- `modules/hardware/`: hardware-family or device-specific configuration.
- `modules/options/`: typed repository-local configuration interfaces.
- `hosts/<name>/`: concrete installation facts and overrides that must not leak to
  another machine: filesystem UUIDs/mounts, explicit foreign-OS boot entries,
  installation compatibility baselines, and host-specific network identifiers.
- `users/<name>/`: reusable Home Manager configuration owned by a person rather
  than a physical machine. Concrete `user@host` compatibility state stays with
  the host/integration and must not be copied into the reusable user entrypoint.

A module should have one canonical owner. Do not keep a second inactive implementation
under another namespace as a migration fallback; Git history is the archive. Raw host
composition data belongs in `hosts/` and may select imports there. Reusable modules
consume `config.workstation.*`. `specialArgs` is reserved for values that are strictly
required while resolving `imports` before the module fixed point; ordinary module context
belongs in canonical options, lexical composition, or `_module.args`. The current repo-supplied import-time
set is intentionally limited to flake `inputs`, `choices`, `workstationSettings`, and
`workstationSelections`. A host's target architecture is owned by `nixpkgs.hostPlatform` in
its hardware configuration; repository tooling systems are a separate flake-output concern.
