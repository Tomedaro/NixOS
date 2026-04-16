{ config, pkgs, lib, ... }:

let
  screenpipeBin = "/home/daniil/.npm/_npx/e158bcd0e578b626/node_modules/@screenpipe/cli-linux-x64/bin/screenpipe";

  runtimeLibs = lib.makeLibraryPath (with pkgs; [
    libgbm wayland libxcb dbus openblas
    stdenv.cc.cc.lib openssl xz libpulseaudio zlib pipewire
  ]);

  shmFix = pkgs.runCommandCC "screenpipe-shm-fix" {} ''
    mkdir -p $out/lib
    $CC -shared -fPIC -o $out/lib/screenpipe-shm-fix.so \
      ${./shm-fix.c} -ldl -lwayland-client \
      -L${pkgs.wayland}/lib \
      -I${pkgs.wayland.dev}/include
  '';

  screenpipeStart = pkgs.writeShellScriptBin "screenpipe-start" ''
    export LD_LIBRARY_PATH="${runtimeLibs}"
    export LD_PRELOAD="${shmFix}/lib/screenpipe-shm-fix.so"
    exec "${screenpipeBin}" record --disable-telemetry
  '';

in
{
  environment.systemPackages = with pkgs; [
    nodejs_22 ffmpeg tesseract libnotify curl pipewire grim
    screenpipeStart
  ];

  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-hyprland ];
  };
}
