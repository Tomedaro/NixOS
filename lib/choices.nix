let
  supported = module: extra:
    {
      inherit module;
      status = "supported";
    }
    // extra;

  pending = module: reason: extra:
    {
      inherit module reason;
      status = "pending";
    }
    // extra;

  legacy = module: reason: extra:
    {
      inherit module reason;
      status = "legacy";
    }
    // extra;

  experimental = module: reason: extra:
    {
      inherit module reason;
      status = "experimental";
    }
    // extra;
in {
  desktops = {
    hyprland = supported ../modules/desktop/hyprland {};
    gnome = supported ../modules/desktop/gnome {};
    i3 = supported ../modules/desktop/i3 {};
    plasma6 =
      pending ../modules/desktop/plasma6
      "Plasma itself is maintained, but this repository's plasma-manager integration must be refreshed before the selector is re-enabled."
      {};
  };

  hyprlandBars = {
    waybar = supported ../modules/desktop/hyprland/programs/waybar {
      providesNotifications = false;
    };
    hyprpanel =
      legacy ../modules/desktop/hyprland/programs/hyprpanel
      "HyprPanel was archived upstream on 2026-04-27 in favor of Wayle. Keep the old module as historical source, but do not advertise it as a maintained selectable shell."
      {
        providesNotifications = true;
      };
    noctalia =
      legacy ../modules/desktop/hyprland/programs/noctalia-shell
      "The checked-in module targets Noctalia Shell v4, whose final release is v4.7.7. Noctalia v5 is a separate incompatible product/configuration migration."
      {
        providesNotifications = false;
      };
    caelestia =
      experimental ../modules/desktop/hyprland/programs/caelestia-shell
      "The checked-in Caelestia configuration must be validated against a pinned stable Caelestia release before it is selectable again."
      {
        providesNotifications = true;
      };
  };

  waybarThemes = {
    minimal = supported ../modules/desktop/hyprland/programs/waybar/minimal.nix {};
    stylish = supported ../modules/desktop/hyprland/programs/waybar/stylish.nix {};
  };

  terminals = {
    kitty = supported ../modules/programs/terminal/kitty {command = "kitty";};
    alacritty = supported ../modules/programs/terminal/alacritty {command = "alacritty";};
    wezterm = supported ../modules/programs/terminal/wezterm {command = "wezterm";};
  };

  editors = {
    nixvim = supported ../modules/programs/editor/nixvim {command = "nvim";};
    neovim =
      pending ../modules/programs/editor/neovim
      "The old external Sly-Harvey/nvim source is no longer the maintained integration. This choice will be made self-contained before being re-enabled."
      {command = "nvim";};
    nvchad = supported ../modules/programs/editor/nvchad {command = "nvim";};
    vscode = supported ../modules/programs/editor/vscode {command = "code --wait";};
    helix = supported ../modules/programs/editor/helix {command = "hx";};
    emacs = supported ../modules/programs/editor/emacs {command = "emacsclient -t -a emacs";};
    doom-emacs =
      pending ../modules/programs/editor/doom-emacs
      "Doom Emacs currently depends on removed external configuration inputs. It needs a deliberate current Unstraightened/local-config integration."
      {command = "emacsclient -t -a emacs";};
  };

  browsers = {
    zen-beta = supported ../modules/programs/browser/zen-beta {command = "zen-beta";};
    firefox =
      pending ../modules/programs/browser/firefox
      "Browser package/profile ownership is still being migrated; selecting Firefox must not silently overwrite an existing mutable profile."
      {command = "firefox";};
    floorp =
      pending ../modules/programs/browser/floorp
      "Browser package/profile ownership is still being migrated; selecting Floorp must not silently overwrite an existing mutable profile."
      {command = "floorp";};
  };

  fileManagers = {
    yazi = supported ../modules/programs/cli/yazi {};
    lf = supported ../modules/programs/cli/lf {};
  };

  shells = {
    zsh = supported ../modules/core/zsh.nix {packageName = "zsh";};
    bash = supported ../modules/core/bash.nix {packageName = "bash";};
  };

  videoDrivers = {
    intel = supported ../modules/hardware/video/intel.nix {};
    amdgpu = supported ../modules/hardware/video/amdgpu.nix {};
    nvidia = supported ../modules/hardware/video/nvidia.nix {};
    nvk =
      pending ../modules/hardware/video/nvk.nix
      "NVK itself is mature, but this repository's module still carries obsolete experimental-era Nouveau/Zink overrides and must be modernized before it is supported."
      {};
  };
}
