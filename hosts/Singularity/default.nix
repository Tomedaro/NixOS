{
  lib,
  pkgs,
  choices,
  workstationSettings,
  ...
}: let
  vars = workstationSettings;
  select = kind: set: name: let
    choice = set.${name} or (throw "Unknown ${kind} choice: ${name}");
  in
    if choice.status == "supported"
    then choice.module
    else throw "${kind} choice '${name}' is ${choice.status}: ${choice.reason}";
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
      ../../modules/programs/cli/starship
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

      # Hardware and selected user-facing modules. Choice lookup is explicit so
      # a typo fails here instead of becoming an accidental filesystem import.
      (select "video driver" choices.videoDrivers vars.videoDriver)
      (select "desktop" choices.desktops vars.desktop)
      (select "terminal" choices.terminals vars.terminal)
      (select "editor" choices.editors vars.editor)
      (select "file manager" choices.fileManagers vars.fileManager)
      (select "shell" choices.shells vars.shell)

      ../../modules/programs/cli/tmux
      ../../modules/programs/cli/pi
      ../../modules/programs/cli/omp
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
      ../../modules/programs/misc/virt-manager
      ../../modules/programs/anki

      # Browser ownership remains in host-packages.nix for this behavior-preserving
      # tranche. The browser selector is still typed and consumed by desktop/app
      # defaults; moving package/profile ownership is a separate migration.
      # (select "browser" choices.browsers vars.browser)
    ]
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

  # Compatibility baseline belongs to this concrete NixOS installation.
  # Keep the migrated value stable; see docs/state-version-26.05.md.
  system.stateVersion = "26.05";

  programs.kdeconnect = {
    enable = true;
    package = pkgs.valent;
  };
}
