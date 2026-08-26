{
  desktops = {
    hyprland = ../modules/desktop/hyprland;
    gnome = ../modules/desktop/gnome;
    i3 = ../modules/desktop/i3;
    plasma6 = ../modules/desktop/plasma6;
  };

  hyprlandBars = {
    waybar = ../modules/desktop/hyprland/programs/waybar;
    hyprpanel = ../modules/desktop/hyprland/programs/hyprpanel;
    noctalia = ../modules/desktop/hyprland/programs/noctalia-shell;
    caelestia = ../modules/desktop/hyprland/programs/caelestia-shell;
  };

  waybarThemes = {
    minimal = ../modules/desktop/hyprland/programs/waybar/minimal.nix;
    stylish = ../modules/desktop/hyprland/programs/waybar/stylish.nix;
  };

  terminals = {
    kitty = ../modules/programs/terminal/kitty;
    alacritty = ../modules/programs/terminal/alacritty;
    wezterm = ../modules/programs/terminal/wezterm;
  };

  editors = {
    nixvim = ../modules/programs/editor/nixvim;
    neovim = ../modules/programs/editor/neovim;
    nvchad = ../modules/programs/editor/nvchad;
    vscode = ../modules/programs/editor/vscode;
    helix = ../modules/programs/editor/helix;
    emacs = ../modules/programs/editor/emacs;
    doom-emacs = ../modules/programs/editor/doom-emacs;
  };

  browsers = {
    zen-beta = ../modules/programs/browser/zen-beta;
    firefox = ../modules/programs/browser/firefox;
    floorp = ../modules/programs/browser/floorp;
  };

  fileManagers = {
    yazi = ../modules/programs/cli/yazi;
    lf = ../modules/programs/cli/lf;
  };

  shells = {
    zsh = "zsh";
    bash = "bash";
  };

  videoDrivers = {
    intel = ../modules/hardware/video/intel.nix;
    amdgpu = ../modules/hardware/video/amdgpu.nix;
    nvidia = ../modules/hardware/video/nvidia.nix;
    nvk = ../modules/hardware/video/nvk.nix;
  };
}
