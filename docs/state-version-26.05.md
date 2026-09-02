# NixOS and Home Manager state-version baseline

This workstation intentionally uses `system.stateVersion = "26.05"` and
`home.stateVersion = "26.05"`.

## History

The configuration was originally created with a `23.11` state-version
baseline. Commit `4f965df4` changed both values to `26.05` on 2026-02-18
without documenting the compatibility migration.

The values are now retained deliberately. They are compatibility baselines,
not package-channel selectors: package freshness continues to be determined by
the flake inputs and lock file.

## Migration contract

Before this migration is considered complete on the real workstation:

1. Review NixOS and Home Manager state-version changes between 23.11 and 26.05
   that affect enabled modules.
2. Build the complete `Singularity` closure.
3. Run `nixos-rebuild test` and verify the active user session and mutable
   application state.
4. Reboot a switched 26.05 generation and verify boot, login, networking,
   Home Manager activation, and key applications.
5. Keep the pre-migration NixOS generation available in GRUB until the new
   baseline has survived a reboot and normal use.

Known Home Manager areas worth explicit review in this repository include Zsh
XDG paths, Yazi wrapper/config behavior, XDG user-directory variables, Firefox
configuration paths, Neovim defaults, GTK4 theming, and Hyprland defaults.

Do not bump either state version merely because a newer NixOS/Home Manager
release exists. A future bump is a separate compatibility migration with its
own release-note review and rollback plan.
