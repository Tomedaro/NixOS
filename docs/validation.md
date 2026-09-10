# Validation pyramid

Validation is layered so that cheap failures arrive early and expensive or
machine-specific evidence is requested deliberately. A synthetic workstation
choice is a capability probe, not a real host.

## Tiers

| Tier | Evidence | Normal trigger |
| --- | --- | --- |
| 1 | Alejandra formatting, Bash syntax, GitHub Actions linting, and repository boundary scans | Every pull request and push to `master` |
| 2 | No-IFD flake evaluation, including every real `nixosConfigurations` host, all policy assertions, and the exact supported non-default choice matrix | Every pull request and push to `master` |
| 3 | Targeted derivation or complete system builds | Local rebuilds or an explicit manual CI request |
| 4 | NixOS VM and interaction tests | Added only for an interaction that warrants them |
| 5 | Hardware, session, application, and mutable-state validation | Deliberate local test activation and manual smoke checks |

CI runs on a GitHub-hosted `ubuntu-24.04` runner with read-only repository
permission. Third-party actions are pinned to full commit hashes and updated in
grouped monthly Dependabot pull requests. The workflow does not receive project
secrets, use a self-hosted runner, activate a system, deploy, or write to a binary
cache.

## Automatic CI

`.github/workflows/nixos-validation.yml` performs Tier 1 and Tier 2. The complete
Singularity closure is deliberately not a `checks.*` output: `nix flake check`
evaluates every real NixOS configuration and builds the declared cheap checks,
but it does not turn every validation run into a full system build.

Instead, CI:

1. runs a writable `nix flake check`, building the cheap source checks and
   forcing the real hosts and policy assertions to evaluate; and
2. runs `check-variants`, which evaluates each supported non-default capability
   in a fresh process.

All authoritative evaluations explicitly disable Import From Derivation, the
evaluation cache, and lock-file writes. No separate host registry is maintained:
the flake's `nixosConfigurations` output is the inventory of real hosts.

## Manual system build

Run the **NixOS validation** workflow manually with `build_singularity` enabled
to build `nixosConfigurations.Singularity.config.system.build.toplevel`. This
builds the complete closure but does not activate, deploy, or publish it.

On Singularity, `rebuild` remains the guarded activation path. `rebuild --full`
also builds every declared flake check and evaluates all supported variants.
`scripts/nixos-assist bundle-run` remains the stricter migration path with exact
HEAD checks, rollback, reports, and phase-specific runtime hooks.

## Deliberate omissions

- CI does not build every capability variant; variants are evaluation probes.
- CI does not native-build other architectures from the x86_64 runner.
- VM tests are not placeholders. Add one when a service or cross-module
  interaction has a concrete boot/runtime contract worth testing.
- Hardware, graphical-session behavior, credentials, NetworkManager profiles,
  Anki data, and other mutable state remain outside evaluation-only claims.
