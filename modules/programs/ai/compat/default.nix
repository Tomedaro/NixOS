{ pkgs, ... }:
{
  environment.binsh = "${pkgs.bash}/bin/bash";

  programs.nix-ld = {
    enable = true;
    libraries = with pkgs; [
      stdenv.cc.cc.lib  # libstdc++.so.6
      libgbm            # libgbm.so.1 (separate from mesa on NixOS!)
      wayland           # libwayland-client.so.0
      libxcb            # libxcb.so.1
      dbus              # libdbus-1.so.3
      openblas          # libopenblas.so.0
      openssl           # libssl.so.3, libcrypto.so.3
      xz                # liblzma.so.5
      libpulseaudio     # libpulse.so.0
      zlib
    ];
  };
}
