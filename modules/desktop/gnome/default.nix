<<<<<<< HEAD
{pkgs, ...}: {
  imports = [
    ./dconf.nix
  ];
  services.xserver = {
    enable = true;
    desktopManager.gnome.enable = true;
    #layout = "gb";
    #libinput = { touchpad.tapping = true; };
  };
  services.gnome.gnome-initial-setup.enable = false;
  services.gnome.games.enable = true;

  environment.gnome.excludePackages = with pkgs.gnome; [
=======
{ lib, pkgs, ... }:
{
  imports = [
    ./dconf.nix
    ../../themes/Catppuccin
  ];
  services = {
    desktopManager.gnome.enable = true;
    gnome.gnome-initial-setup.enable = false;
    gnome.games.enable = false;
    tlp.enable = lib.mkForce false; # gnome has builtin power management
  };

  environment.gnome.excludePackages = with pkgs; [
>>>>>>> upstream/master
    #gnome-backgrounds
    #pkgs.gnome-video-effects
    gnome-maps
    gnome-music
<<<<<<< HEAD
    pkgs.gnome-tour
    pkgs.gnome-text-editor
    pkgs.gnome-user-docs
  ];
  environment.systemPackages = with pkgs; [
    gnomeExtensions.appindicator
    gnomeExtensions.blur-my-shell
    gnomeExtensions.burn-my-windows
    gnomeExtensions.compact-top-bar
    gnomeExtensions.custom-accent-colors
    gradience
    gnomeExtensions.gtile
    gnomeExtensions.dash-to-panel
    gnomeExtensions.tray-icons-reloaded
    gnome.gnome-tweaks
    gnomeExtensions.arcmenu
    gnomeExtensions.gesture-improvements
    gnomeExtensions.paperwm
    gnomeExtensions.just-perfection
    gnomeExtensions.rounded-window-corners
    gnomeExtensions.vitals
=======
    gnome-tour
    gnome-text-editor
    gnome-user-docs
    gnome-contacts
    gnome-initial-setup
    geary
    gedit
    epiphany
    cheese
  ];
  environment.systemPackages = with pkgs; [
    gnome-tweaks
    gnomeExtensions.vitals
    gnomeExtensions.arcmenu
    # gnomeExtensions.appindicator
    # gnomeExtensions.blur-my-shell
    # gnomeExtensions.burn-my-windows
    # gnomeExtensions.compact-top-bar
    # gnomeExtensions.custom-accent-colors
    # gradience
    # gnomeExtensions.gtile
    # gnomeExtensions.dash-to-panel
    # gnomeExtensions.tray-icons-reloaded
    # gnomeExtensions.paperwm
    # gnomeExtensions.just-perfection
>>>>>>> upstream/master
  ];
}
