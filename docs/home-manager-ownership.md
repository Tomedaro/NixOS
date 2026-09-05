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
  Its constructor accepts the user-facing choice catalog and selections plus
  the explicit Pi, editor, desktop, Spicetify, and Thunderbird dependencies,
  then returns a `homeManager`-class module. It deliberately does not set
  `home.stateVersion`, username, UID, or home directory.

Pinned Home Manager's NixOS integration derives username, UID (when defined),
and home directory from the corresponding NixOS user.

## Transitional rule

15 feature/host modules still contribute through `home-manager.sharedModules`.
The extracted CLI user layer now includes Starship, tmux, lazygit, Cava,
direnv, and btop as `homeManager`-class modules imported directly by
`users/daniil/default.nix`. This remains safe only because
`modules/core/users.nix` asserts exactly one managed Home Manager user while the
remaining shared-module payloads are migrated incrementally.

Supported terminal, editor, terminal file-manager, and shell choices expose a
user-side module constructor in `lib/choices.nix`. The concrete host binds the
selection values and exact external dependencies; `users/daniil/default.nix`
selects and imports the resulting Home Manager modules. This keeps the choice
catalog shared without giving reusable user modules `osConfig`, general flake
`inputs`, or Home Manager `extraSpecialArgs`.

The twelve supported user-side implementations—Kitty, Alacritty, WezTerm,
Nixvim, NvChad, VS Code, Helix, Emacs, Yazi, lf, Zsh, and Bash—are explicitly
`homeManager`-class modules. WezTerm retains its selected system font module,
and VS Code retains its selected NixOS unfree predicate, as optional system
sides of the same catalog entries. Other choices have no empty NixOS wrapper.

The user root now owns `EDITOR`, `VISUAL`, `BROWSER`, and `TERMINAL`. Values are
still derived from the typed choice catalog. Browser package/profile ownership
is not activated by this change: the current Zen package remains host-owned,
and the pending Firefox/Floorp profile migrations remain pending.

Nixvim receives only its platform package collection and selected terminal;
NvChad receives only its upstream Home Manager module; Helix receives only the
pinned nixpkgs source used in its nixd expression; Bash and Zsh receive only the
pinned `dev-shells` path used by their template aliases.

Supported desktops now expose both sides of their ownership boundary in the
choice catalog. Hyprland, GNOME, and i3 retain NixOS modules for display-manager,
window-manager, package, and service policy, while their personal configuration
is composed by `users/daniil/default.nix`. Supported Waybar and its minimal and
stylish configurations are user-only choice constructors. The selected desktop
receives only the concrete bar, theme, application, appearance, and localization
values its Home Manager constructor needs.

Gruvbox and Catppuccin were already entirely personal configuration despite
being transported through NixOS wrappers. They are now direct
`homeManager`-class modules. Hyprland wallpaper/configuration files, variables,
idle/lock behavior, Rofi, SwayNotificationCenter, Waybar, and wlogout are likewise
user-owned. GNOME dconf and i3/picom/Dunst/Polybar configuration follow the same
boundary. GNOME derives personal paths from `config.home.username`, so standalone
composition follows the selected Home Manager identity rather than a NixOS user
option.

The former `workstationSelections` import-time escape hatch is removed. Desktop,
bar, and Waybar-theme selection now occurs in explicit user composition; system
selection still uses the typed desktop catalog. Legacy, experimental, and pending
desktop/theme modules remain dormant and are not silently legitimized by this
migration.

One active shared-module payload remains on Singularity: gaming-dependent
MangoHud. B4C will split that final active transport, remove the transitional
single-user assertion, and establish zero active `sharedModules` payloads.

On NixOS, these extracted modules now receive Home Manager's `pkgs` argument.
Singularity currently sets `home-manager.useGlobalPkgs = true`, so this is the same
package set that the old NixOS wrappers captured. Standalone Home Manager reuse can
therefore use its own package set naturally instead of depending on NixOS module
context.

MPV and OBS Studio are also `homeManager`-class modules selected directly by
`users/daniil/default.nix`. MPV takes `config.home.homeDirectory` from Home Manager;
both modules receive its `pkgs`. Their application settings, script/plugin lists,
and enabled state are preserved. No NixOS arguments are passed into these modules.

Daniil's 40 personal Home Manager package/output entries are declared in
`users/daniil/packages.nix`, imported by the user root. This is a personal package
selection, not a generic feature module. `hosts/Singularity/host-packages.nix`
currently retains the separate system package list, including the Anki wrapper,
flake-input packages, browser integration, and administrator tools.

FreeTube, qimgv, feh, Foliate, Sioyek, guvcview, Obsidian, Ludusavi, and GitHub
Desktop are user-owned applications. Their packages are unchanged, but they are
no longer installed globally by the host. Other accounts do not inherit these
applications merely by using Singularity. The i3 module retains its independent
feh dependency for its wallpaper capability. The explicit `feh.doc` entry preserves
the documentation output previously selected by NixOS's extra-output policy.

The system-to-user migration checks Daniil's declarative command and desktop
metadata resolution using the actual NixOS system and per-user profiles. Existing
package order outside the nine moved entries is preserved. No application
service, MIME default, user permission, or runtime activation is added.

EasyEffects session behavior, captive-browser, the Anki wrapper, and the Pi-related
lean-ctx tool remain pending integration-specific review. Browser/input packages
remain with their selection and input boundaries; device/administrator utilities
are not presumed to be personal applications.

Pi is a reusable `homeManager`-class module selected directly by the user root.
Its package, wrappers, scripts, session path, and home-derived runtime paths are
unchanged. The module receives only the `mcp-nixos` package constructor used to
build its pinned MCP server; it no longer receives the complete flake input set.
The dormant `piNix` package override was removed because this flake has no such
input and the active package remains Home Manager's `pkgs.pi-coding-agent`.

`lean-ctx` intentionally remains host-installed for now. Pi's copied mutable
runtime configuration still names `/run/current-system/sw/bin/lean-ctx`; moving
the package before that runtime boundary is redesigned and synchronized would
create an avoidable activation-time compatibility gap.

Discord is a reusable `homeManager`-class module selected by the user root. Its
existing package override and Vencord files are preserved. The system package
overlay still supplies the existing Discord build customizations. No new Discord
settings file is introduced.

Moving these direct package contributions changes their list positions. Package
identities, multiplicities, priorities, and the relative order of other packages
are preserved. The migration checks the package link trees in both orders, using
the same candidate packages. This avoids encoding historical import positions as
numeric ordering rules. Home Manager's MIME/font cache commands remain unchanged;
the link-tree comparison excludes those generated caches.

Spicetify is selected by the user root as a reusable `homeManager`-class module.
Singularity binds two explicit constructor arguments: the upstream Home Manager
module and its platform-indexed package collection. The feature selects the
platform using Home Manager's `pkgs`; neither reusable module receives the general
flake `inputs` set, `osConfig`, or extra Home Manager special arguments.

The configured Spotify package, theme, extensions, custom apps, Wayland setting,
and disabled window-manager patch are preserved. The old NixOS wrapper's Spotify
unfree predicate is removed: the existing central `allowUnfree = true` policy
already permits it. A standalone caller must supply a package set whose unfree
policy permits Spotify; a reusable user feature does not set system policy.

Thunderbird is a `homeManager`-class module selected by the user root. It receives
only the Catppuccin Thunderbird theme source lexically, not the complete flake
input set. The pinned Home Manager module embeds enterprise policies in its final
Thunderbird package. The previous NixOS policy is preserved explicitly: application
updates remain disabled, the Catppuccin extension remains installed, and the
do-not-track preference remains locked. Thunderbird is no longer installed in the
host-global profile, so other accounts do not inherit Daniil's mail client and
theme. No profiles, accounts, credentials, or mutable mail state are declared.
Home Manager also creates its canonical shared Mozilla native-messaging-host
directory using recursive per-file links. Before integration, the migration
builds that directory's actual source and checks candidate filenames for content
collisions. Unrelated existing manifests, such as FirefoxPWA's, are preserved;
same-name files must have identical content, and adopting a regular file must
not overwrite an existing backup. Symlinked parent directories,
conflicting files, and concurrent changes cause integration to be refused.

YouTube Music has no active import; this migration does not activate or rewrite
it.

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
