{ lib, ... }:
let
  inherit (lib) mkOption types;
  choices = import ../../lib/choices.nix;
  choiceNames = set: builtins.attrNames set;
in
{
  options.workstation = {
    user.name = mkOption {
      type = types.str;
      description = "Primary workstation user name.";
    };

    hostName = mkOption {
      type = types.str;
      description = "Network hostname for this workstation.";
    };

    desktop = {
      environment = mkOption {
        type = types.enum (choiceNames choices.desktops);
        description = "Supported desktop/window-manager selection.";
      };

      bar = mkOption {
        type = types.enum (choiceNames choices.hyprlandBars);
        description = "Hyprland shell/bar selection.";
      };

      waybarTheme = mkOption {
        type = types.enum (choiceNames choices.waybarThemes);
        description = "Waybar configuration variant.";
      };
    };

    appearance = {
      sddmTheme = mkOption {
        type = types.enum [
          "astronaut"
          "black_hole"
          "purple_leaves"
          "jake_the_dog"
          "hyprland_kath"
        ];
        description = "Embedded SDDM Astronaut theme.";
      };

      wallpaper = mkOption {
        type = types.str;
        description = "Default wallpaper filename.";
      };

      lockWallpaper = mkOption {
        type = types.str;
        description = "Lock-screen wallpaper filename.";
      };
    };

    apps = {
      terminal = mkOption {
        type = types.enum (choiceNames choices.terminals);
        description = "Default terminal selection.";
      };

      editor = mkOption {
        type = types.enum (choiceNames choices.editors);
        description = "Default editor selection.";
      };

      browser = mkOption {
        type = types.enum (choiceNames choices.browsers);
        description = "Default browser selection.";
      };

      fileManager = mkOption {
        type = types.enum (choiceNames choices.fileManagers);
        description = "Default terminal file manager selection.";
      };

      shell = mkOption {
        type = types.enum (choiceNames choices.shells);
        description = "Login shell selection.";
      };
    };

    features.gaming = mkOption {
      type = types.bool;
      description = "Whether gaming support is included in the host configuration.";
    };

    hardware = {
      videoDriver = mkOption {
        type = types.enum (choiceNames choices.videoDrivers);
        description = "GPU driver module selection.";
      };

      bluetooth = mkOption {
        type = types.bool;
        description = "Whether Bluetooth hardware support is enabled.";
      };
    };

    localization = {
      timeZone = mkOption {
        type = types.str;
        description = "IANA timezone.";
      };

      locale = mkOption {
        type = types.str;
        description = "Default locale.";
      };

      clock24h = mkOption {
        type = types.bool;
        description = "Whether desktop clocks use 24-hour formatting.";
      };

      xkbLayout = mkOption {
        type = types.str;
        description = "XKB keyboard layout.";
      };

      xkbVariant = mkOption {
        type = types.str;
        description = "XKB keyboard variant.";
      };

      consoleKeymap = mkOption {
        type = types.str;
        description = "Linux console keymap.";
      };

      capslockAsEscape = mkOption {
        type = types.bool;
        description = "Whether Caps Lock is remapped to Escape in desktop configuration.";
      };
    };
  };
}
