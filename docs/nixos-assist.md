# nixos-assist v6.4

A reusable, deliberately conservative harness for this workstation's NixOS
maintenance workflow.

## Why v6.4 exists

v5 had useful commands, but it mixed generic mechanics with Phase 3B-specific
firewall facts, formatted source as part of validation, and did not reliably
rollback a failed test activation. Later revisions separated those concerns,
made system-generation reporting lock-free, and made generic handoffs complete.

v6.4 tightens the evaluation contract after the post-GC failures showed that
two constraints had been bundled together. On Nix 2.34, `flake check
--no-build` switches evaluation to a read-only store and also disables Import
From Derivation (IFD) by default. A failure in that mode therefore does not, by
itself, distinguish a genuine IFD from a failure caused by the additional
read-only-store constraint.

The authoritative gate is a fresh, writable `nix flake check` with
`allow-import-from-derivation = false` set explicitly. This preserves the
store-state-independent invariant we actually care about — evaluation must not
build derivations — without also making the evaluator read-only. After
successful evaluation, `flake check` builds every declared `checks` derivation.
The read-only `--no-build` pass remains a diagnostic only. Non-default
workstation variants are evaluated uncached with IFD disabled as well.

The generic harness owns:

- clean-tree / exact-HEAD preflight;
- bundle SHA-256 verification;
- patch apply-check + apply;
- `git diff --check` (validation never reformats source);
- a fresh writable full-flake check with `allow-import-from-derivation = false`;
- a non-authoritative read-only `flake check --no-build` diagnostic;
- optional full variant matrix, also fresh and IFD-free;
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

## Repository usage

`nixos-assist` is already tracked as `scripts/nixos-assist`; no bootstrap installer is required.

From the repository:

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

`handoff generic` includes every Git-tracked repository file plus current changed paths; scoped `network` and `storage` handoffs remain intentionally smaller.
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
  "host": "Singularity",
  "patch": "change.patch",
  "network_preflight": true,
  "full_variants": true,
  "allowed_failed_user_units": ["swaync.service"],
  "preflight_hook": "hooks/preflight.sh",
  "pre_activate_hook": "hooks/pre-activate.sh",
  "runtime_hook": "hooks/runtime.sh",
  "postboot_hook": "hooks/postboot.sh"
}
```

All files referenced by the manifest must be covered by `SHA256SUMS`.
`bundle-run` verifies the checksums before touching the repository.

`bundle-run` now builds the flake's complete local-system `checks` set in the
authoritative gate. A legacy schema-v1 `build_checks` field is tolerated in old
bundles but no longer selects a subset.

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
