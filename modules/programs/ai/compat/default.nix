# modules/compat.nix
{ pkgs, ... }:
{
  # Enables /lib64/ld-linux-x86-64.so.2 compatibility shim.
  # Required for any pre-compiled binary not built by Nix (e.g. npm-shipped binaries).
  programs.nix-ld = {
    enable = true;
    # Common libs pre-compiled binaries expect to find
    libraries = with pkgs; [
      stdenv.cc.cc.lib   # libstdc++, libgcc_s
      zlib
      openssl
      ffmpeg
    ];
  };
}
