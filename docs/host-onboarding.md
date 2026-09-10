# Host onboarding

## Current status

The repository currently has one real NixOS host: `Singularity`.

The previous root-level `install.sh` and `live-install.sh` scripts were retired
because their host-creation model copied an existing host directory and then
mutated it. That is unsafe for a future multi-host setup: a copied host can
inherit filesystem UUIDs, generated hardware facts, state-version history,
network identifiers, or machine-specific tuning.

## Current Singularity rebuild

From the repository:

```bash
sudo nixos-rebuild switch --flake .#Singularity
```

The repository's `rebuild` helper remains the preferred guarded local workflow
when it is installed.

## Adding different hardware

Do **not** start by copying `hosts/Singularity`.

Until the provisioning phase supplies a dedicated scaffolder, treat a new host
as an explicit architecture task:

1. choose a canonical configuration/hostname identity;
2. create a fresh host directory rather than cloning another machine;
3. generate hardware data on the target machine (`nixos-generate-config`, or a
   future Facter-based workflow);
4. declare that installation's own storage, network, state-version and machine
   quirks;
5. compose only the reusable capabilities required by that machine;
6. add one explicit `nixosConfigurations.<HostName>`;
7. run repository checks and the host evaluation before deployment.

Configuration, provisioning, deployment, and external secret/mutable state are
separate concerns. A successful Nix evaluation does not imply that credentials,
NetworkManager profiles, SSH host identity, or service data have been restored.

## Future provisioning

A later phase will evaluate a safe fresh-machine workflow built around normal
NixOS host modules, with `nixos-anywhere`, hardware discovery (potentially
Facter), and Disko considered separately. Disko will be tested in a VM or other
sacrificial environment before any live Singularity disk migration.
