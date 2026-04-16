{ config, pkgs, lib, ... }:

let
  screenpipeBin = "/home/daniil/.npm/_npx/e158bcd0e578b626/node_modules/@screenpipe/cli-linux-x64/bin/screenpipe";

  runtimeLibs = lib.makeLibraryPath (with pkgs; [
    libgbm wayland libxcb dbus openblas
    stdenv.cc.cc.lib openssl xz libpulseaudio zlib pipewire
  ]);

  screenpipeStart = pkgs.writeShellScriptBin "screenpipe-start" ''
    export LD_LIBRARY_PATH="${runtimeLibs}"
    exec "${screenpipeBin}" record --disable-telemetry
  '';

in
{
  environment.systemPackages = with pkgs; [
    nodejs_22 ffmpeg tesseract libnotify curl pipewire
    screenpipeStart
  ];

  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-hyprland ];
  };
}
