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
      ./host-packages.nix

      # Core modules
      ../../modules/scripts
      ../../modules/core/boot.nix
      ../../modules/core/starship.nix
      ../../modules/core/fonts.nix
      ../../modules/core/hardware.nix
      ../../modules/core/network.nix
      ../../modules/core/dns.nix
      ../../modules/core/nh.nix
      ../../modules/core/packages.nix
      ../../modules/core/sddm.nix
      ../../modules/core/security.nix
      ../../modules/core/services.nix
      ../../modules/core/syncthing.nix
      ../../modules/core/system.nix
      ../../modules/core/users.nix

      # Hardware and selected user-facing modules. Choice lookup is explicit so
      # a typo fails here instead of becoming an accidental filesystem import.
      (select "video driver" choices.videoDrivers vars.videoDriver)
      ../../modules/hardware/drives
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
    ++ lib.optional vars.games ../../modules/core/games.nix;

  # Keep automatic garbage collection off during the staged hardening rollout.
  # A single retention policy will be reintroduced after rollback is proven.
  programs.nh.clean.enable = lib.mkForce false;

  workstation = {
    user.name = vars.username;
    hostName = vars.hostname;

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

    network = {
      trustedConnectionUuids = vars.trustedConnectionUuids;
      ankiSyncHostname = vars.ankiSyncHostname;
    };

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

  # Swap
  swapDevices = [
    {
      device = "/swapfile";
      size = 8192;
    }
  ];

  programs.kdeconnect = {
    enable = true;
    package = pkgs.valent;
  };
}
