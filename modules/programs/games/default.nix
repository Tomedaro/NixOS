{
  pkgs,
  lib,
  ...
}: {
  nixpkgs.config.allowUnfreePredicate = pkg:
    builtins.elem (lib.getName pkg) [
      "steam"
      "steam-original"
      "steam-run"
    ];
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
  };
  environment.systemPackages = with pkgs; [
    #lutris
    heroic
    #bottles
    # ryujinx
    # prismlauncher

    steam-run
    wineWow64Packages.staging
    gamescope
  ];
  programs = {
    gamemode = {
      enable = true;
      enableRenice = false;
    };
    steam = {
      enable = true;
      remotePlay.openFirewall = false;
      dedicatedServer.openFirewall = false;
      localNetworkGameTransfers.openFirewall = false;
      extraCompatPackages = [pkgs.proton-ge-bin];
      gamescopeSession = {
        enable = true;
        args = [
          "--rt"
          "--expose-wayland"
          # "--immediate-flips" # Tearing and low input lag
          # "--adaptive-sync"  # G-Sync/FreeSync
        ];
      };
    };
    gamescope = {
      enable = true;
      capSysNice = true;
      package = pkgs.gamescope;
      args = [
        "--rt"
        "--expose-wayland"

        # experimental
        # "--immediate-flips"
      ];
    };
  };
}
