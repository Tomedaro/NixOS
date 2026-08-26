{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) getExe;
  bar = config.workstation.desktop.bar;
  browser = config.workstation.apps.browser;
  terminal = config.workstation.apps.terminal;
  fileManager = config.workstation.apps.fileManager;
  kbdLayout = config.workstation.localization.xkbLayout;
  kbdVariant = config.workstation.localization.xkbVariant;
  capslockAsESC = config.workstation.localization.capslockAsEscape;
  defaultWallpaper = config.workstation.appearance.wallpaper;
  # Import script modules
  # autowaybar = pkgs.callPackage ./scripts/autowaybar.nix { };
  autoclicker = pkgs.callPackage ./scripts/autoclicker.nix {};
  batterynotify = pkgs.callPackage ./scripts/batterynotify.nix {};
  clipmanager = pkgs.callPackage ./scripts/clipmanager.nix {};
  fileManagerScript = pkgs.callPackage ./scripts/file-manager.nix {inherit terminal;};
  gamemode = pkgs.callPackage ./scripts/gamemode.nix {};
  keyboardswitch = pkgs.callPackage ./scripts/keyboardswitch.nix {};
  keybinds-yad = pkgs.callPackage ./scripts/keybinds-yad.nix {};
  # keybinds-rofi = pkgs.callPackage ./scripts/keybinds-yad.nix { };
  # mediactrl = pkgs.callPackage ./scripts/mediactrl.nix { };
  launcher = pkgs.callPackage ../../scripts/launcher.nix {inherit lib pkgs terminal;};
  rofimusic = pkgs.callPackage ./scripts/rofimusic.nix {};
  rotate-monitor = pkgs.callPackage ./scripts/rotate-monitor.nix {};
  screen-record = pkgs.callPackage ./scripts/screen-record.nix {};
  screenshot = pkgs.callPackage ./scripts/screenshot.nix {};
  wallpaper = pkgs.callPackage ./scripts/wallpaper.nix {inherit defaultWallpaper;};
  zoom = pkgs.callPackage ./scripts/zoom.nix {};
in {
  home-manager.sharedModules = [
    (
      {config, ...}: {
        xdg.configFile."hypr/variables.lua" = {
          text = ''
            -- Scripts
            autoclicker = "${getExe autoclicker}"
            batterynotify = "${getExe batterynotify}"
            clipmanager = "${getExe clipmanager}"
            fileManagerScript = "${getExe fileManagerScript}"
            gamemode = "${getExe gamemode}"
            keyboardswitch = "${getExe keyboardswitch}"
            keybinds_yad = "${getExe keybinds-yad}"
            rofimusic = "${getExe rofimusic}"
            rotate_monitor = "${getExe rotate-monitor}"
            screen_record = "${getExe screen-record}"
            screenshot = "${getExe screenshot}"
            wallpaper = "${getExe wallpaper}"
            zoom = "${getExe zoom}"

            mainMod = "SUPER"
            launcher = "${getExe launcher}"
            bar = "${bar}"
            term = "${terminal}"
            editor = "code --disable-gpu"
            browser = "${browser}"
            fileManager = "${fileManager}"
            capslockAsESC = ${lib.boolToString capslockAsESC}
            kbdLayout = "${kbdLayout}"
            kbdVariant = "${kbdVariant}"
          '';
        };
      }
    )
  ];
}
