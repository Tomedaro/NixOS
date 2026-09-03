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

49 feature/host modules still contribute through `home-manager.sharedModules`.
The extracted CLI user layer now includes Starship, tmux, lazygit, Cava, and
direnv as `homeManager`-class modules imported directly by
`users/daniil/default.nix`. This remains safe only because
`modules/core/users.nix` asserts exactly one managed Home Manager user while the
remaining shared-module payloads are migrated incrementally.

On NixOS, these extracted modules now receive Home Manager's `pkgs` argument.
Singularity currently sets `home-manager.useGlobalPkgs = true`, so this is the same
package set that the old NixOS wrappers captured. Standalone Home Manager reuse can
therefore use its own package set naturally instead of depending on NixOS module
context.

Direnv is fully user-owned: its warning threshold is written through
`programs.direnv.config.global.warn_timeout` rather than the deprecated
`DIRENV_WARN_TIMEOUT` system environment variable, and Home Manager is the sole
owner of Bash/Zsh direnv hook generation.

Btop remains intentionally deferred as a whole. Its current package override enables
both CUDA and ROCm support even though Singularity selects the Intel video-driver
profile, and Hyprland separately installs a generic `pkgs.btop`. That package-policy
debt should be corrected deliberately rather than formalized during user-ownership
extraction.

Do not use `osConfig` or `home-manager.extraSpecialArgs` as a universal escape
hatch. A user module should depend on NixOS state only when the user behavior is
genuinely a function of system configuration.
