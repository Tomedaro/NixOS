{
  inputs,
  lib,
  pkgs,
  self,
  choices,
  workstationSettings,
  ...
}: let
  vars = workstationSettings;
  selectChoice = kind: set: name: let
    choice = set.${name} or (throw "Unknown ${kind} choice: ${name}");
  in
    if choice.status == "supported"
    then choice
    else throw "${kind} choice '${name}' is ${choice.status}: ${choice.reason}";
  selectedVideo = selectChoice "video driver" choices.videoDrivers vars.videoDriver;
  selectedDesktop = selectChoice "desktop" choices.desktops vars.desktop;
  selectedTerminal = selectChoice "terminal" choices.terminals vars.terminal;
  selectedEditor = selectChoice "editor" choices.editors vars.editor;
in {
  imports =
    [
      ../../modules/options/workstation.nix
      ./hardware-configuration.nix
      ./storage.nix
      ./boot.nix
      ./network.nix
      ./host-packages.nix

      # Baseline modules
      ../../modules/scripts
      ../../modules/core/boot.nix
      ../../modules/core/fonts.nix
      ../../modules/core/hardware.nix
      ../../modules/core/network.nix
      ../../modules/core/dns.nix
      ../../modules/core/nh.nix
      ../../modules/core/packages.nix
      ../../modules/core/sddm.nix
      ../../modules/core/security.nix
      ../../modules/core/services.nix
      ../../modules/services/syncthing
      ../../modules/core/system.nix
      ../../modules/core/users.nix

      # Hardware, desktop, and optional system sides of user-facing choices.
      # Choice lookup is explicit so a typo fails here instead of becoming an
      # accidental filesystem import.
      selectedVideo.module
      selectedDesktop.module

      ../../modules/programs/cli/omp
      ../../modules/programs/misc/tlp
      ../../modules/programs/misc/thunar
      ../../modules/programs/misc/virt-manager
      ../../modules/programs/anki

      # Browser packages and native-messaging integration remain in
      # host-packages.nix. Browser profile modules are catalogued separately but
      # deliberately not composed while mutable profile adoption is deferred.
    ]
    ++ lib.optionals (selectedTerminal ? module) [selectedTerminal.module]
    ++ lib.optionals (selectedEditor ? module) [selectedEditor.module]
    ++ lib.optionals vars.games [
      ../../modules/programs/games
      ../../modules/core/flatpak.nix
      ../../modules/programs/games/geforce-now
    ];

  # Keep automatic garbage collection off during the staged hardening rollout.
  # A single retention policy will be reintroduced after rollback is proven.
  programs.nh.clean.enable = lib.mkForce false;

  workstation = {
    user.name = vars.username;
    desktop = {
      environment = vars.desktop;
      bar = vars.bar;
      waybarTheme = vars.waybarTheme;
    };

    appearance = {
      sddmTheme = vars.sddmTheme;
      wallpaper = vars.defaultWallpaper;
      lockWallpaper = vars.hyprlockWallpaper;
    };

    apps = {
      terminal = vars.terminal;
      editor = vars.editor;
      browser = vars.browser;
      fileManager = vars.fileManager;
      shell = vars.shell;
    };

    features.gaming = vars.games;

    hardware = {
      videoDriver = vars.videoDriver;
      bluetooth = vars.bluetoothSupport;
    };

    network.ankiSyncHostname = vars.ankiSyncHostname;

    localization = {
      timeZone = vars.timezone;
      locale = vars.locale;
      clock24h = vars.clock24h;
      xkbLayout = vars.kbdLayout;
      xkbVariant = vars.kbdVariant;
      consoleKeymap = vars.consoleKeymap;
      capslockAsEscape = vars.capslockAsESC;
    };
  };

  # Concrete Home Manager installation for daniil on Singularity. The reusable
  # user module intentionally does not own compatibility state.
  home-manager.users.${vars.username} = {
    imports = [
      (import ../../users/daniil {
        bzmenuPackage = inputs.bzmenu.packages.${pkgs.stdenv.hostPlatform.system}.default;
        inherit choices;
        devShellsPath = "${self}/dev-shells";
        mkMcpNixos = inputs.mcp-nixos.lib.mkMcpNixos;
        nixpkgsSource = inputs.nixpkgs;
        nixvimPackages = inputs.nixvim.packages;
        nvchadModule = inputs.nvchad4nix.homeManagerModules.default;
        spicetifyModule = inputs.spicetify-nix.homeManagerModules.default;
        spicetifyPackages = inputs.spicetify-nix.legacyPackages;
        thunderbirdTheme = inputs.thunderbird-catppuccin;
        ytXPackage = inputs.yt-x.packages.${pkgs.stdenv.hostPlatform.system}.default;
        userSelections = {
          inherit
            (vars)
            bar
            browser
            clock24h
            desktop
            editor
            fileManager
            games
            kbdLayout
            kbdVariant
            shell
            terminal
            waybarTheme
            ;
          capslockAsEscape = vars.capslockAsESC;
          lockWallpaper = vars.hyprlockWallpaper;
          wallpaper = vars.defaultWallpaper;
        };
      })
    ];
    home.stateVersion = "26.05";
  };

  # Compatibility baseline belongs to this concrete NixOS installation.
  # Keep the migrated value stable; see docs/state-version-26.05.md.
  system.stateVersion = "26.05";

  programs.kdeconnect = {
    enable = true;
    package = pkgs.valent;
  };
}
