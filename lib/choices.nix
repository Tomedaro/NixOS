let
  supported = module: extra:
    {
      inherit module;
      status = "supported";
    }
    // extra;

  # User-facing choices expose a dependency constructor. Most simply return a
  # module path; choices with external dependencies bind only what they need.
  supportedHome = homeModulePath: extra:
    {
      homeModule = _: homeModulePath;
      status = "supported";
    }
    // extra;

  supportedHomeWith = homeModule: extra:
    {
      inherit homeModule;
      status = "supported";
    }
    // extra;

  # Hybrid choices retain a genuine NixOS side alongside their user module.
  supportedHybrid = module: homeModulePath: extra:
    {
      inherit module;
      homeModule = _: homeModulePath;
      status = "supported";
    }
    // extra;

  supportedHybridWith = module: homeModule: extra:
    {
      inherit module homeModule;
      status = "supported";
    }
    // extra;

  pendingHomeWith = homeModule: reason: extra:
    {
      inherit homeModule reason;
      status = "pending";
    }
    // extra;

  pendingHybridWith = module: homeModule: reason: extra:
    {
      inherit module homeModule reason;
      status = "pending";
    }
    // extra;

  legacyHybridWith = module: homeModule: reason: extra:
    {
      inherit module homeModule reason;
      status = "legacy";
    }
    // extra;

  experimentalHybridWith = module: homeModule: reason: extra:
    {
      inherit module homeModule reason;
      status = "experimental";
    }
    // extra;

  supportedBrowserWith = module: profileModule: profileReason: extra:
    {
      inherit module profileModule profileReason;
      packageOwner = "system";
      profileStatus = "deferred";
      status = "supported";
    }
    // extra;

  pendingBrowserWith = profileModule: reason: extra:
    {
      inherit profileModule reason;
      packageOwner = "unresolved";
      profileReason = reason;
      profileStatus = "deferred";
      status = "pending";
    }
    // extra;
in {
  desktops = {
    hyprland =
      supportedHybridWith
      ../modules/desktop/hyprland/system.nix
      (
        {
          bar,
          browser,
          capslockAsEscape,
          choices,
          clock24h,
          fileManager,
          kbdLayout,
          kbdVariant,
          lockWallpaper,
          terminal,
          wallpaper,
          waybarTheme,
          ...
        }:
          import ../modules/desktop/hyprland {
            inherit
              bar
              browser
              capslockAsEscape
              choices
              clock24h
              fileManager
              kbdLayout
              kbdVariant
              lockWallpaper
              terminal
              wallpaper
              waybarTheme
              ;
          }
      )
      {};
    gnome =
      supportedHybridWith
      ../modules/desktop/gnome/system.nix
      (
        {
          kbdLayout,
          wallpaper,
          ...
        }:
          import ../modules/desktop/gnome {inherit kbdLayout wallpaper;}
      )
      {};
    i3 =
      supportedHybridWith
      ../modules/desktop/i3/system.nix
      (
        {
          browser,
          terminal,
          wallpaper,
          ...
        }:
          import ../modules/desktop/i3 {inherit browser terminal wallpaper;}
      )
      {};
    plasma6 =
      pendingHybridWith
      ../modules/desktop/plasma6/system.nix
      (
        {
          browser,
          editor,
          games,
          plasmaManagerModule,
          terminal,
          wallpaper,
          ...
        }:
          import ../modules/desktop/plasma6 {
            inherit
              browser
              editor
              games
              plasmaManagerModule
              terminal
              wallpaper
              ;
          }
      )
      "Plasma itself is maintained, but this repository's plasma-manager integration must be refreshed before the selector is re-enabled."
      {};
  };

  hyprlandBars = {
    waybar =
      supportedHomeWith
      (
        {
          choices,
          clock24h,
          terminal,
          waybarTheme,
          ...
        }:
          import ../modules/desktop/hyprland/programs/waybar {
            inherit choices clock24h terminal waybarTheme;
          }
      )
      {
        providesNotifications = false;
      };
    hyprpanel =
      legacyHybridWith
      ../modules/desktop/hyprland/programs/hyprpanel/system.nix
      (
        {
          bluetoothSupport,
          clock24h,
          ...
        }:
          import ../modules/desktop/hyprland/programs/hyprpanel {
            inherit bluetoothSupport clock24h;
          }
      )
      "HyprPanel was archived upstream on 2026-04-27 in favor of Wayle. Keep the old module as historical source, but do not advertise it as a maintained selectable shell."
      {
        providesNotifications = true;
      };
    noctalia =
      legacyHybridWith
      ../modules/desktop/hyprland/programs/noctalia-shell/system.nix
      (
        {noctaliaModule, ...}:
          import ../modules/desktop/hyprland/programs/noctalia-shell {
            inherit noctaliaModule;
          }
      )
      "The checked-in module targets Noctalia Shell v4, whose final release is v4.7.7. Noctalia v5 is a separate incompatible product/configuration migration."
      {
        providesNotifications = false;
      };
    caelestia =
      experimentalHybridWith
      ../modules/desktop/hyprland/programs/caelestia-shell/system.nix
      (
        {
          bluetoothSupport,
          caelestiaModule,
          clock24h,
          ...
        }:
          import ../modules/desktop/hyprland/programs/caelestia-shell {
            inherit bluetoothSupport caelestiaModule clock24h;
          }
      )
      "The checked-in Caelestia configuration must be validated against a pinned stable Caelestia release before it is selectable again."
      {
        providesNotifications = true;
      };
  };

  waybarThemes = {
    minimal =
      supportedHomeWith
      (
        {clock24h, ...}:
          import ../modules/desktop/hyprland/programs/waybar/minimal.nix {inherit clock24h;}
      )
      {};
    stylish =
      supportedHomeWith
      (
        {
          clock24h,
          terminal,
          ...
        }:
          import ../modules/desktop/hyprland/programs/waybar/stylish.nix {inherit clock24h terminal;}
      )
      {};
  };

  terminals = {
    kitty = supportedHome ../modules/programs/terminal/kitty {command = "kitty";};
    alacritty = supportedHome ../modules/programs/terminal/alacritty {command = "alacritty";};
    wezterm = supportedHybrid ../modules/programs/terminal/wezterm/system.nix ../modules/programs/terminal/wezterm {command = "wezterm";};
  };

  editors = {
    nixvim =
      supportedHomeWith
      (
        {
          nixvimPackages,
          terminal,
          ...
        }:
          import ../modules/programs/editor/nixvim {
            inherit nixvimPackages terminal;
          }
      )
      {command = "nvim";};
    neovim =
      pendingHybridWith
      ../modules/programs/editor/neovim/system.nix
      (
        {
          neovimSource,
          terminal,
          ...
        }:
          import ../modules/programs/editor/neovim {
            inherit neovimSource terminal;
          }
      )
      "The old external Sly-Harvey/nvim source is no longer the maintained integration. This choice will be made self-contained before being re-enabled."
      {command = "nvim";};
    nvchad =
      supportedHomeWith
      (
        {nvchadModule, ...}:
          import ../modules/programs/editor/nvchad {inherit nvchadModule;}
      )
      {command = "nvim";};
    vscode = supportedHybrid ../modules/programs/editor/vscode/system.nix ../modules/programs/editor/vscode {command = "code --wait";};
    helix =
      supportedHomeWith
      (
        {nixpkgsSource, ...}:
          import ../modules/programs/editor/helix {inherit nixpkgsSource;}
      )
      {command = "hx";};
    emacs = supportedHome ../modules/programs/editor/emacs {command = "emacsclient -t -a emacs";};
    doom-emacs =
      pendingHomeWith
      (
        {
          doomConfig,
          doomEmacsModule,
          ...
        }:
          import ../modules/programs/editor/doom-emacs {
            inherit doomConfig doomEmacsModule;
          }
      )
      "Doom Emacs currently depends on removed external configuration inputs. It needs a deliberate current Unstraightened/local-config integration."
      {command = "emacsclient -t -a emacs";};
  };

  browsers = {
    zen-beta =
      supportedBrowserWith
      ../modules/programs/browser/zen-beta/system.nix
      (
        {
          betterfoxSource,
          zenBrowserModule,
          ...
        }:
          import ../modules/programs/browser/zen-beta {
            inherit betterfoxSource zenBrowserModule;
          }
      )
      "The existing mutable Zen profile and XDG MIME/default state must be inventoried, backed up, and validated before Home Manager may write profiles.ini or profile files."
      {command = "zen-beta";};
    firefox =
      pendingBrowserWith
      (
        {betterfoxSource, ...}:
          import ../modules/programs/browser/firefox {
            inherit betterfoxSource;
          }
      )
      "Firefox has no selected system-package integration, and declarative profile adoption must not silently overwrite existing mutable browser state."
      {command = "firefox";};
    floorp =
      pendingBrowserWith
      (
        {betterfoxSource, ...}:
          import ../modules/programs/browser/floorp {
            inherit betterfoxSource;
          }
      )
      "Floorp has no selected system-package integration, and declarative profile adoption must not silently overwrite existing mutable browser state."
      {command = "floorp";};
  };

  fileManagers = {
    yazi = supportedHome ../modules/programs/cli/yazi {};
    lf = supportedHome ../modules/programs/cli/lf {};
  };

  shells = {
    zsh =
      supportedHomeWith
      (
        {devShellsPath, ...}:
          import ../modules/programs/shell/zsh {inherit devShellsPath;}
      )
      {packageName = "zsh";};
    bash =
      supportedHomeWith
      (
        {devShellsPath, ...}:
          import ../modules/programs/shell/bash {inherit devShellsPath;}
      )
      {packageName = "bash";};
  };

  videoDrivers = {
    intel = supported ../modules/hardware/video/intel.nix {};
    amdgpu = supported ../modules/hardware/video/amdgpu.nix {};
    nvidia = supported ../modules/hardware/video/nvidia.nix {};
    nvk =
      pendingHybridWith
      ../modules/hardware/video/nvk.nix
      (_: ../modules/hardware/video/nvk-home.nix)
      "NVK itself is mature, but this repository's module still carries obsolete experimental-era Nouveau/Zink overrides and must be modernized before it is supported."
      {};
  };
}
