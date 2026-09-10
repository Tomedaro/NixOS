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
}: {lib, ...}: let
  inherit (lib) optional;
  barChoice = choices.hyprlandBars.${bar} or (throw "Unknown Hyprland bar choice: ${bar}");
  barModule =
    if barChoice.status == "supported"
    then
      barChoice.homeModule {
        inherit choices clock24h terminal waybarTheme;
      }
    else throw "Hyprland bar choice '${bar}' is ${barChoice.status}: ${barChoice.reason}";
in {
  _class = "homeManager";

  imports =
    [
      ../../themes/Gruvbox
      (import ./variables.nix {
        inherit
          bar
          browser
          capslockAsEscape
          fileManager
          kbdLayout
          kbdVariant
          terminal
          wallpaper
          ;
      })
      barModule
      ./programs/wlogout
      (import ./programs/rofi {inherit terminal;})
      ./programs/hypridle
      (import ./programs/hyprlock {inherit lockWallpaper;})
    ]
    ++ optional (!barChoice.providesNotifications) ./programs/swaync;

  services.awww.enable = true;

  xdg.configFile = {
    "hypr/hyprland.lua".source = ./lua/hyprland.lua;
    "hypr/monitors.lua".source = ./lua/monitors.lua;
    "hypr/settings.lua".source = ./lua/settings.lua;
    "hypr/animations.lua".source = ./lua/animations.lua;
    "hypr/binds.lua".source = ./lua/binds.lua;
    "hypr/rules.lua".source = ./lua/rules.lua;

    "hypr/icons" = {
      source = ./icons;
      recursive = true;
    };
  };
}
