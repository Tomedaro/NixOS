# Home Manager ownership

The repository is migrating from a single-user `home-manager.sharedModules`
transport model to explicit user-owned Home Manager composition.

## Ownership layers

- `modules/core/users.nix` owns NixOS/Home Manager integration, NixOS user
  creation, integration policy (`useGlobalPkgs`, `useUserPackages`, backup
  behavior), and the transitional single-user assertion.
- `hosts/Singularity/default.nix` owns the concrete `daniil@Singularity` Home
  Manager installation compatibility baseline (`home.stateVersion = "26.05"`).
- `users/daniil/default.nix` is the reusable Home Manager entrypoint for Daniil.
  It is a `homeManager`-class module and deliberately does not set
  `home.stateVersion`, username, UID, or home directory.

Pinned Home Manager's NixOS integration derives username, UID (when defined),
and home directory from the corresponding NixOS user.

## Transitional rule

46 feature/host modules still contribute through `home-manager.sharedModules`.
The extracted CLI user layer now includes Starship, tmux, lazygit, Cava,
direnv, and btop as `homeManager`-class modules imported directly by
`users/daniil/default.nix`. This remains safe only because
`modules/core/users.nix` asserts exactly one managed Home Manager user while the
remaining shared-module payloads are migrated incrementally.

On NixOS, these extracted modules now receive Home Manager's `pkgs` argument.
Singularity currently sets `home-manager.useGlobalPkgs = true`, so this is the same
package set that the old NixOS wrappers captured. Standalone Home Manager reuse can
therefore use its own package set naturally instead of depending on NixOS module
context.

MPV and OBS Studio are also `homeManager`-class modules selected directly by
`users/daniil/default.nix`. MPV takes `config.home.homeDirectory` from Home Manager;
both modules receive its `pkgs`. Their application settings, script/plugin lists,
and enabled state are preserved. No NixOS arguments are passed into these modules.

Discord's direct `home.packages` contribution remains for the package-ownership
tranche, where ordering can be reviewed with the rest of the personal package list.
Spicetify and Thunderbird still have system/input boundaries, and YouTube Music
has no active import; this migration does not activate or rewrite them.

Direnv is fully user-owned: its warning threshold is written through
`programs.direnv.config.global.warn_timeout` rather than the deprecated
`DIRENV_WARN_TIMEOUT` system environment variable, and Home Manager is the sole
owner of Bash/Zsh direnv hook generation.

Btop uses Home Manager's default `pkgs.btop` package, with the existing settings
and Catppuccin theme. The old unconditional CUDA/ROCm override is removed for
Singularity's Intel configuration. The pinned package already builds Intel GPU
collection; CUDA and ROCm package options add vendor-specific library lookup
support. Compiled support does not guarantee access to GPU counters, and this
change grants no additional privileges.

Hyprland no longer installs a second, system-wide btop package. Daniil's Home
Manager profile owns the executable, including its existing Hyprland key binding.
A future AMD/NVIDIA installation should explicitly review its btop runtime library
requirements; evaluation of the video-driver variants is not a telemetry test.

Do not use `osConfig` or `home-manager.extraSpecialArgs` as a universal escape
hatch. A user module should depend on NixOS state only when the user behavior is
genuinely a function of system configuration.
