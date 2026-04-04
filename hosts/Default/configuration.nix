{ lib, pkgs, ... }:
let
  vars = import ./variables.nix;
in
{
  imports = [
    ./hardware-configuration.nix
    ./host-packages.nix

    # Core Modules
    ../../modules/scripts
    ../../modules/core/boot.nix
    ../../modules/core/bash.nix
    ../../modules/core/zsh.nix
    ../../modules/core/starship.nix
    ../../modules/core/fonts.nix
    ../../modules/core/hardware.nix
    ../../modules/core/network.nix
    ../../modules/core/dns.nix
    ../../modules/core/nh.nix
    ../../modules/core/packages.nix
    ../../modules/core/printing.nix
    ../../modules/core/sddm.nix
    ../../modules/core/security.nix
    ../../modules/core/services.nix
    ../../modules/core/syncthing.nix
    ../../modules/core/system.nix
    ../../modules/core/users.nix
    # ../../modules/core/flatpak.nix
    # ../../modules/core/virtualisation.nix
    # ../../modules/core/dlna.nix

    # Hardware
    ../../modules/hardware/drives
    ../../modules/hardware/video/${vars.videoDriver}.nix

    # Desktop & Programs
    ../../modules/desktop/${vars.desktop}
    ../../modules/programs/browser/${vars.browser}
    ../../modules/programs/terminal/${vars.terminal}
    ../../modules/programs/editor/${vars.editor}
    ../../modules/programs/cli/${vars.tuiFileManager}

    ../../modules/programs/cli/tmux
    ../../modules/programs/cli/direnv
    ../../modules/programs/cli/lazygit
    ../../modules/programs/cli/cava
    ../../modules/programs/cli/btop
    ../../modules/programs/media/discord
    ../../modules/programs/media/spicetify
    ../../modules/programs/media/thunderbird
    ../../modules/programs/media/obs-studio
    ../../modules/programs/media/mpv
    ../../modules/programs/misc/tlp
    ../../modules/programs/misc/thunar
    ../../modules/programs/misc/lact
    ../../modules/programs/anki
    ../../modules/programs/misc/virt-manager
  ]
  ++ lib.optional (vars.games == true) ../../modules/core/games.nix;

  # Networking
  networking = {
    hostName = vars.hostName;
    firewall = {
      enable = false;
      allowedTCPPortRanges = [{ from = 1714; to = 1764; }];
      allowedUDPPortRanges = [{ from = 1714; to = 1764; }];
      allowedTCPPorts = [ 27701 21027 22000 ];
    };
  };

  programs.kdeconnect.enable = true;

  # Home-manager personal packages
  home-manager.sharedModules = [
    (_: {
      home.packages = with pkgs; [
        krita
        vlc
        gimp
        github-desktop
      ];
    })
    ../../modules/services/syncthing
  ];

  environment.systemPackages = with pkgs; [];

  # DLNA media server
  services.minidlna = {
    enable = true;
    openFirewall = true;
    settings = {
      friendly_name = "NixOS-DLNA";
      media_dir = [
        "/mnt/work/Pimsleur"
        "/mnt/work/Media/Films"
        "/mnt/work/Media/Series"
        "/mnt/work/Media/Videos"
        "/mnt/work/Media/Music"
      ];
      inotify = "yes";
      log_level = "error";
    };
  };
  users.users.minidlna.extraGroups = [ "users" ];
}
