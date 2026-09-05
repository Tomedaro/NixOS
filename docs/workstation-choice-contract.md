# Workstation choice contract

The repository intentionally supports more than the currently selected `Singularity`
configuration, but a module existing in the tree is not by itself a support claim.

## Choice states

Every selectable family is catalogued in `lib/choices.nix` with one of four states:

- `supported`: selectable through `hosts/Singularity/variables.nix` and covered by a
  one-factor NixOS evaluation check.
- `pending`: retained source with a known integration gap. It is deliberately not
  accepted by the typed workstation options until repaired.
- `experimental`: a current integration that needs an explicit compatibility/runtime
  validation before it becomes a normal choice.
- `legacy`: an integration for an upstream generation that is no longer the current
  product/configuration model.

Only `supported` values appear in the `workstation.*` option enums. The composition
layer also rejects a raw host setting whose catalogue entry is not supported, so a
stale or experimental module cannot be enabled accidentally by bypassing option
validation.

## Composition boundary

`hosts/Singularity/variables.nix` is raw host-composition input. `flake.nix` merges variant
overrides into that data and passes the result to the host module as
`workstationSettings`. Ordinary modules must not consume that raw set; after module
composition they read the typed `config.workstation.*` interface instead.

The concrete host passes the selected user-facing values to
`users/daniil/default.nix`. That Home Manager composition root resolves desktop, bar,
Waybar-theme, terminal, editor, file-manager, and shell modules through the same typed
catalogue. Choice constructors receive only the scalar selections and explicit
dependencies their user module needs. There is no aggregate import-time selector
argument shared with ordinary NixOS modules.

Supported desktop entries are hybrid boundaries: their `module` is the NixOS side and
their `homeModule` constructor is the personal Home Manager side. Hyprland, GNOME, and
i3 therefore retain display-manager, window-manager, service, package, and policy
configuration in NixOS while Daniil's desktop files and preferences are composed by
his user root. The structural boundary check rejects `workstationSettings` anywhere
under `modules/`, preventing the raw host interface from leaking back into reusable
modules.

## Current exceptions

- Plasma 6 is pending until its Plasma Manager integration is refreshed against the
  current upstream Home Manager module.
- HyprPanel is legacy: upstream archived the project on 2026-04-27 in favor of
  Wayle. The checked-in HyprPanel module remains historical source; a future Wayle
  integration should be added independently rather than pretending HyprPanel is
  maintained.
- Noctalia is legacy: the checked-in module targets Noctalia Shell v4. A future v5
  integration is a migration, not an in-place dependency bump.
- Caelestia is experimental until the checked-in settings are validated against a
  pinned stable upstream release.
- The standalone Neovim choice is pending. Its historical external personal-config
  input is not restored merely to preserve an old selector; the replacement should
  be self-contained or use a current maintained integration.
- Doom Emacs is pending until its external configuration/dependency ownership is
  redesigned deliberately.
- Firefox and Floorp are pending until browser package/profile ownership is migrated
  without overwriting existing mutable browser state.
- NVK is pending even though Mesa NVK itself is mature: the repository module still
  contains old experimental-era Nouveau/Zink overrides and must be modernized first.

Pending, experimental, and legacy choices do not add root flake inputs. External
inputs are added only when a choice is deliberately promoted to supported status.
This keeps the lock graph aligned with functionality the repository actually promises.

## Variant checks

Routine `nix flake check` validates the real `Singularity` host plus cheap structural
invariants. Alternate full-system configurations deliberately do not live under
`checks.*`: `nix flake check --no-build` still evaluates every check derivation, so a
large matrix there makes ordinary validation slow and memory-heavy.

Supported non-default choices are instead exposed lazily under `lib.workstation.variantDrvPaths`
and evaluated with:

```console
nix run .#check-variants
```

The app starts a fresh `nix eval` process for each selected variant so evaluator
memory is released between configurations. `--list` shows the matrix, and individual
names can be supplied when a change affects only one integration. `rebuild --full`
runs the complete serial matrix in addition to the normal flake checks.

The matrix is one-factor-at-a-time. Context-dependent choices carry their
prerequisites explicitly: bar checks force Hyprland, and Waybar-theme checks force
Hyprland + Waybar. Choices already exercised by the current `Singularity` configuration
are omitted from the alternate matrix, avoiding redundant evaluation.

Variant evaluation catches missing inputs, removed or renamed options, module
conflicts, and selector rot. It does not claim runtime validation of every alternate
desktop or hardware configuration; actually switching to an alternative still
requires its own smoke test.

## Home Manager ownership

The configuration currently has exactly one Home Manager user. Supported personal
features are composed explicitly by `users/daniil/default.nix`; they do not use
`home-manager.sharedModules` to apply personal policy to every managed account.

One active shared payload remains: gaming-dependent MangoHud. Until B4C moves that
final payload, `modules/core/users.nix` retains the single-user assertion so it cannot
silently configure a future second account. The remaining shared-module assignment
sites belong to dormant pending, experimental, or legacy choices.
`home-manager.useGlobalPkgs = true` remains so NixOS and Home Manager share the same
`pkgs` instance and overlays.

## Commands versus selector names

Choice names are configuration identities, not necessarily executable names.
Terminal, editor, browser, and shell entries therefore carry command/package metadata
in `lib/choices.nix`. Session variables such as `EDITOR`, `VISUAL`, `BROWSER`, and
`TERMINAL` are derived from that metadata rather than guessing that a selector string
is also the correct command.
