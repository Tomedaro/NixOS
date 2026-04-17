{ pkgs, lib, ... }:

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

  screenpipeCli = pkgs.writeShellScriptBin "screenpipe" ''
    export LD_LIBRARY_PATH="${runtimeLibs}"
    export PATH="${pkgs.bun}/bin:$PATH"
    exec "${screenpipeBin}" "record --disable-telemetry"
  '';

in
{
  environment.systemPackages = with pkgs; [
    bun
    nodejs_22 ffmpeg tesseract libnotify curl pipewire grim
    screenpipeStart
    screenpipeCli
  ];

  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-hyprland ];
  };
}
