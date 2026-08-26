# Workstation choice contract

The repository intentionally supports multiple workstation variants while keeping
host-specific values out of reusable modules.

## Source of truth

`hosts/Default/variables.nix` remains the editable host selection file during the
installer transition. It is imported only by `flake.nix` and passed to the host
composition as `workstationSettings`.

`hosts/Default/configuration.nix` maps those raw selections into typed
`workstation.*` NixOS options from `modules/options/workstation.nix`.
Reusable modules consume `config.workstation.*`; they must not import a host
`variables.nix` directly.

## Module selection

`lib/choices.nix` is the explicit registry from stable selector names to module
paths. Composition modules may use the raw settings only when Nix requires an
import choice before the module fixed point is available. Currently those
composition points are the host, Hyprland bar selection, and Waybar theme
selection.

This deliberately avoids filesystem conventions such as
`../../modules/desktop/${desktop}`. A selector name is a public configuration
interface; a module directory may be renamed without changing that interface.

## Support policy

A choice is not considered supported merely because a directory exists. The
registry states the intended choices, and follow-up variant checks must prove
that every registered alternative evaluates with the current input graph.

The current `Default` host remains the behavioral baseline. Browser package and
profile ownership is intentionally unchanged in this tranche; the browser
selector is typed, but the browser module remains disabled until that ownership
migration can be tested independently.
