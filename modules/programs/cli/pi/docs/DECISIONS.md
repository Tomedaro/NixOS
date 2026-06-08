# Decisions

## Source-managed Pi setup

Durable Pi setup lives under `modules/programs/cli/pi/**`; runtime files are generated or user-owned.

## Wiki-first routing

A small `AGENTS.md` points Pi to `docs/INDEX.md` and `docs/LOOKUP.json` so Pi can find exact source files without broad repository scans.

## Local-first study

Default `pi-study` avoids heavy learning packages and external memory systems. `pi-study-tutor` is optional.

## Read-only is not sandbox

`pi-readonly` is policy-backed and fail-closed, but it is still not a security sandbox. It restricts Pi tools and external-directory access through `pi-permission-system`; a real kernel/network sandbox should be designed separately.

## Narrow bash policies

Broad shell wildcards are avoided because they can read secrets or chain commands outside intended paths.

## Pinned control packages

Security/control packages are pinned because Pi packages can execute extension code in the Pi process. Updates should be intentional and reviewed.

## Work projects must be explicit

`pi-work-init` requires an existing project path to avoid accidentally creating typo directories or writing `.pi` state into the NixOS repo. A `README.md` alone is not considered a strong enough project marker.


## Compatibility preflight

The Pi binary comes from Nix, while Pi packages come from npm. `pi-compat-check` exists to make that boundary visible before package pin changes become operational assumptions.
