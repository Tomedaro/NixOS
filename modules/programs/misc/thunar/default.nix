<<<<<<< HEAD
{ pkgs, ... }: {
  programs.thunar = {
    enable = true;
    plugins = with pkgs.xfce; [
      thunar-archive-plugin
      thunar-volman
      thunar-media-tags-plugin
    ];
  };

  programs.file-roller.enable = true;  # proper archive integration
  programs.xfconf.enable = true;       # persist preferences
  programs.dconf.enable = true;        # GTK settings on Hyprland

  services.gvfs.enable = true;         # trash, MTP, SFTP, network mounts
  services.tumbler.enable = true;      # thumbnails
=======
{ pkgs, ... }:
{
  programs.thunar = {
    enable = true;
    plugins = with pkgs; [
      thunar-archive-plugin # Archive management
      thunar-volman # Volume management (automount removable devices)
      thunar-media-tags-plugin # Tagging & renaming feature for media files
    ];
  };
  # Archive manager
  environment.systemPackages = with pkgs; [ file-roller ];
>>>>>>> upstream/master
}
