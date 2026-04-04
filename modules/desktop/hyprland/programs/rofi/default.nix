{
  pkgs,
  lib,
<<<<<<< HEAD
  terminal,
  ...
}: {
  home-manager.sharedModules = [
    (_: {
      programs.rofi = let
        inherit (lib) getExe;
      in {
        enable = true;
        package = pkgs.rofi;
=======
  host,
  ...
}:
let
  inherit (import ../../../../../hosts/${host}/variables.nix) terminal;
  inherit (lib) getExe;
in
{
  home-manager.sharedModules = [
    (_: {
      programs.rofi = {
        enable = true;
>>>>>>> upstream/master
        terminal = "${getExe pkgs.${terminal}}";
        plugins = with pkgs; [
          rofi-emoji # https://github.com/Mange/rofi-emoji 🤯
          rofi-games # https://github.com/Rolv-Apneseth/rofi-games 🎮
        ];
<<<<<<< HEAD
      };
      xdg.configFile."rofi/config-music.rasi".source = ./config-music.rasi;
      xdg.configFile."rofi/config-long.rasi".source = ./config-long.rasi;
      xdg.configFile."rofi/config-wallpaper.rasi".source = ./config-wallpaper.rasi;
=======
        extraConfig = import ./config.nix;
      };
>>>>>>> upstream/master
      xdg.configFile."rofi/launchers" = {
        source = ./launchers;
        recursive = true;
      };
      xdg.configFile."rofi/colors" = {
        source = ./colors;
        recursive = true;
      };
<<<<<<< HEAD
      xdg.configFile."rofi/assets" = {
        source = ./assets;
        recursive = true;
      };
      xdg.configFile."rofi/resolution" = {
        source = ./resolution;
        recursive = true;
      };
=======
>>>>>>> upstream/master
    })
  ];
}
