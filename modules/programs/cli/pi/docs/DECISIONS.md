# Decisions

## Source-managed Pi setup

Durable Pi setup lives under `modules/programs/cli/pi/**`; runtime files are generated or user-owned.

## Wiki-first routing

A small `AGENTS.md` points Pi to `docs/INDEX.md` and `docs/LOOKUP.json` so Pi can find exact source files without broad repository scans.

## Local-first study

Default `pi-study` avoids heavy learning packages. `pi-study-tutor` is optional.

(Originally said "avoids external memory systems" — this predates the Engram/Hermes architecture. Both Engram and Hermes are now available under the documented memory policy. See `docs/MEMORY.md`.)

## Read-only is not sandbox

`pi-readonly` is policy-backed and fail-closed, but it is still not a security sandbox. It restricts Pi tools and external-directory access through `pi-permission-system`; a real kernel/network sandbox should be designed separately.

## Narrow bash policies

Broad shell wildcards are avoided because they can read secrets or chain commands outside intended paths.

## Pinned control packages

Security/control packages are pinned because Pi packages can execute extension code in the Pi process. Updates should be intentional and reviewed.

## Work projects must be explicit

`pi-work-init` requires an existing project path to avoid accidentally creating typo directories or writing `.pi` state into the NixOS repo. A `README.md` alone is not considered a strong enough project marker.

## Engram is canonical durable memory

Engram owns durable project/cross-agent memory through `mem_*` tools. See `docs/MEMORY.md`.

## Hermes is Pi-local behavioral memory

Hermes owns Pi-local behavioral/session memory through `memory`, `memory_search`, `session_search`, and `skill`. See `docs/MEMORY.md`.

## SDD subagents use parent-orchestrated memory

SDD subagents do not have memory tools by default. The parent Pi orchestrates memory. See `docs/MEMORY.md` and `resources/global/AGENTS.md`.

## Memory is context, not instruction

Current repo files and tool output override memory. Memory is advisory. No secrets in memory.

## Compatibility preflight

The Pi binary comes from Nix, while Pi packages come from npm. `pi-compat-check` exists to make that boundary visible before package pin changes become operational assumptions.

## Source global-pins lockfile (P6C)

The repo owns 18 global npm pins declared in `settings/global.json`. A source-controlled lockfile at `npm/global-pins/` covers only these 18 packages.

Profile extras (`@majorgilles/pi-learning-tutor`, `keating`, `teach-me` from `study-tutor.overlay.json`) and user/Pi/legacy runtime extras (`context-mode`, `pi-memory`, `pi-obsidian`, `pi-studio`) are not part of the base global-pins lockfile.

The source lockfile is an audit/comparison artifact only. Runtime install behavior remains Pi-managed.

`npm ci`, `ignore-scripts=true`, and Nix packaging remain deferred.

## P6D: Runtime npm extras ownership

P6D classified unowned runtime npm root packages declared outside `settings/global.json`.

- `context-mode@1.0.162` — stale leftover from a previous intentional pin, later reverted from source control. Has `postinstall`, Elastic-2.0 license, exposes CLI/MCP functionality. Kept as WARN in `pi-admin npm-check`. Future explicit cleanup/removal candidate.
- `pi-memory@0.3.14` — legacy Pi memory extension superseded by Engram + Hermes architecture. Peer deps target old `@mariozechner/*` namespace. Has `postinstall`. Kept as WARN. Future explicit cleanup/removal candidate.
- `pi-obsidian@0.2.3` — likely user-installed Obsidian extension. No lifecycle scripts, current namespace peer deps. Kept as INFO accepted runtime extra.
- `pi-studio@0.9.32` — likely user/Pi-installed workspace UI extension. No lifecycle scripts, current namespace peer deps. Kept as INFO accepted runtime extra.

No package removal or source promotion is approved by this decision. Unowned extras remain visible in `pi-admin npm-check` for audit context.
