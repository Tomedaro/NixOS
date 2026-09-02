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

A module should have one canonical owner. Do not keep a second inactive implementation
under another namespace as a migration fallback; Git history is the archive. Raw host
composition data belongs in `hosts/` and may select imports there. Reusable modules
consume `config.workstation.*`, except for narrowly scoped `specialArgs` values that are
strictly required to resolve `imports` before the module fixed point.
