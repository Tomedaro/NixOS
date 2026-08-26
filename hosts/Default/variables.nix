{
  username = "daniil"; # auto-set with install.sh, live-install.sh, and rebuild scripts.

  # Desktop Environment
  desktop = "hyprland"; # hyprland, gnome, i3, plasma6

  # Theme & Appearance
  bar = "waybar"; # waybar, hyprpanel, noctalia, caelestia
  waybarTheme = "minimal"; # stylish, minimal
  sddmTheme = "astronaut"; # astronaut, black_hole, purple_leaves, jake_the_dog, hyprland_kath
  defaultWallpaper = "galaxy.webp"; # Change with SUPER + SHIFT + W (Hyprland)
  hyprlockWallpaper = "galaxy.webp";

  # Default Applications
  terminal = "kitty"; # kitty, alacritty, wezterm
  editor = "nixvim"; # nixvim, neovim, nvchad, vscode, helix, emacs, doom-emacs
  browser = "zen-beta"; # zen-beta, firefox, floorp
  fileManager = "yazi"; # yazi, lf
  shell = "zsh"; # zsh, bash
  games = true; # Enable/Disable gaming module

  # Hardware
  hostname = "Singularity";
  videoDriver = "intel"; # intel, amdgpu, nvidia, nvk
  bluetoothSupport = true; # Whether your motherboard supports bluetooth

  # Localization
  timezone = "Europe/Paris";
  locale = "en_GB.UTF-8";
  clock24h = true;
  kbdLayout = "us";
  kbdVariant = "colemak_dh_ortho";
  consoleKeymap = "colemak";
  capslockAsESC = false;
}
