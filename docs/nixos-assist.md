# nixos-assist v6.1

A reusable, deliberately conservative harness for this workstation's NixOS
maintenance workflow.

## Why v6.1 exists

v5 had useful commands, but it mixed generic mechanics with Phase 3B-specific
firewall facts, formatted source as part of validation, and did not reliably
rollback a failed test activation. v6.1 separates those concerns and reads system-generation metadata without taking the root-owned profile lock.

The generic harness owns:

- clean-tree / exact-HEAD preflight;
- bundle SHA-256 verification;
- patch apply-check + apply;
- `git diff --check` (validation never reformats source);
- `nix flake check --no-build`;
- selected flake check builds;
- optional full variant matrix;
- one exact system closure build;
- dry activation;
- non-persistent test activation;
- exact runtime rollback on failure;
- DNS recovery after rollback if needed;
- sudo timestamp keepalive during long runs;
- reports, handoffs, postboot checks;
- read-only Nix storage/GC planning.

Phase-specific facts belong in a small bundle (`phase.json` + optional hooks),
not in `nixos-assist` itself.

## Install into the repository

From this extracted directory:

```bash
./install.sh
```

This adds `scripts/nixos-assist` and `docs/nixos-assist.md` to the Git working
tree and marks them intent-to-add so `git diff` can inspect them. It does not
rebuild NixOS, stage their contents, or commit anything.

Then:

```bash
cd ~/NixOS
scripts/nixos-assist doctor
scripts/nixos-assist gc-plan
```

`gc-plan` is read-only. It does **not** delete generations or run GC.

## Commands

```text
nixos-assist doctor
nixos-assist report [generic|network|storage]
nixos-assist handoff [generic|network|storage]
nixos-assist gc-plan
nixos-assist bundle-run BUNDLE_DIR
nixos-assist postboot [BUNDLE_DIR]
```

## Bundle schema v1

A future change bundle contains:

```text
phase-name/
├── phase.json
├── SHA256SUMS
├── change.patch
└── hooks/                 # optional
    ├── preflight.sh
    ├── pre-activate.sh
    ├── runtime.sh
    └── postboot.sh
```

Example `phase.json`:

```json
{
  "schema": 1,
  "name": "phase-example",
  "expected_head": "FULL_GIT_COMMIT",
  "expected_branch": "feat/example",
  "host": "Default",
  "patch": "change.patch",
  "network_preflight": true,
  "full_variants": true,
  "build_checks": ["formatting", "system-policy"],
  "allowed_failed_user_units": ["swaync.service"],
  "preflight_hook": "hooks/preflight.sh",
  "pre_activate_hook": "hooks/pre-activate.sh",
  "runtime_hook": "hooks/runtime.sh",
  "postboot_hook": "hooks/postboot.sh"
}
```

All files referenced by the manifest must be covered by `SHA256SUMS`.
`bundle-run` verifies the checksums before touching the repository.

Hooks run as the invoking user and inherit:

- `NIXOS_ASSIST_REPO`
- `NIXOS_ASSIST_BUNDLE`
- `NIXOS_ASSIST_REPORT`
- `NIXOS_ASSIST_PREVIOUS_SYSTEM`
- `NIXOS_ASSIST_TARGET_SYSTEM`
- `NIXOS_ASSIST_HOST`

The harness maintains sudo authorization, so a trusted hook can use `sudo -n`
for read-only runtime assertions when required. A bundle is executable input;
only run bundles you trust.

## Deliberate non-features

- no automatic commit;
- no permanent `switch`/`boot`;
- no automatic generation deletion;
- no automatic GC;
- no implicit source formatting;
- no hard-coded firewall ports, DNS providers, Syncthing settings, or known
  service topology in the generic harness.

Those are policy decisions, not harness mechanics.
