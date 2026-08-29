{
  username = "daniil"; # Temporary host settings interface; composed only by flake.nix.

  # Desktop Environment
  desktop = "hyprland"; # Choice catalogue: lib/choices.nix

  # Theme & Appearance
  bar = "waybar"; # Choice catalogue: lib/choices.nix
  waybarTheme = "minimal"; # Choice catalogue: lib/choices.nix
  sddmTheme = "astronaut"; # astronaut, black_hole, purple_leaves, jake_the_dog, hyprland_kath
  defaultWallpaper = "galaxy.webp"; # Change with SUPER + SHIFT + W (Hyprland)
  hyprlockWallpaper = "galaxy.webp";

  # Default Applications
  terminal = "kitty"; # Choice catalogue: lib/choices.nix
  editor = "nixvim"; # Choice catalogue: lib/choices.nix
  browser = "zen-beta"; # Choice catalogue: lib/choices.nix
  fileManager = "yazi"; # Choice catalogue: lib/choices.nix
  shell = "zsh"; # Choice catalogue: lib/choices.nix
  games = true; # Enable/disable gaming applications and services.

  # Hardware
  hostname = "Singularity";
  videoDriver = "intel"; # Choice catalogue: lib/choices.nix
  bluetoothSupport = true;

  # Network trust
  # Existing NetworkManager profiles remain externally managed. These UUIDs
  # are assigned to the firewalld home zone at runtime without persisting
  # changes back into the connection profile.
  trustedConnectionUuids = [
    "c7d1f765-e254-4a6f-ab29-21ec5a9f49e1" # Bbox-93F30CDB
  ];

  # Localization
  timezone = "Europe/Paris";
  locale = "en_GB.UTF-8";
  clock24h = true;
  kbdLayout = "us";
  kbdVariant = "colemak_dh_ortho";
  consoleKeymap = "colemak";
  capslockAsESC = false;
}
