{
  lib,
  pkgs,
  ...
}: {
  services.xserver = {
    enable = lib.mkForce true;
    autorun = false;

    desktopManager = {
      xterm.enable = false;
    };

    windowManager.i3 = {
      enable = true;
      package = pkgs.i3;
      extraPackages = with pkgs; [
        i3status # gives you the default i3 status bar
        i3lock # default i3 screen locker
        i3blocks # if you are planning on using i3blocks over i3status
        feh
        dmenu
        rofi
        polybar
        cava
        xrandr
        edid-decode
        vim.xxd
      ];
    };
  };
}
