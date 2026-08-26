{
  username = "daniil"; # Temporary host settings interface; composed only by flake.nix.

  # Desktop Environment
  desktop = "hyprland"; # supported: hyprland, gnome, i3; pending: plasma6

  # Theme & Appearance
  bar = "waybar"; # supported: waybar; legacy: hyprpanel, noctalia; experimental: caelestia
  waybarTheme = "minimal"; # supported: minimal, stylish
  sddmTheme = "astronaut"; # astronaut, black_hole, purple_leaves, jake_the_dog, hyprland_kath
  defaultWallpaper = "galaxy.webp"; # Change with SUPER + SHIFT + W (Hyprland)
  hyprlockWallpaper = "galaxy.webp";

  # Default Applications
  terminal = "kitty"; # supported: kitty, alacritty, wezterm
  editor = "nixvim"; # supported: nixvim, nvchad, vscode, helix, emacs; pending: neovim, doom-emacs
  browser = "zen-beta"; # supported: zen-beta; pending: firefox, floorp
  fileManager = "yazi"; # supported: yazi, lf
  shell = "zsh"; # supported: zsh, bash
  games = true; # Enable/disable gaming applications and services.

  # Hardware
  hostname = "Singularity";
  videoDriver = "intel"; # supported: intel, amdgpu, nvidia; pending: nvk
  bluetoothSupport = true;

  # Localization
  timezone = "Europe/Paris";
  locale = "en_GB.UTF-8";
  clock24h = true;
  kbdLayout = "us";
  kbdVariant = "colemak_dh_ortho";
  consoleKeymap = "colemak";
  capslockAsESC = false;
}
