{
  lib,
  pkgs,
  ...
}: {
  programs.thunar.enable = lib.mkForce false;

  services = {
    # xserver.enable = lib.mkForce true;
    tlp.enable = lib.mkForce false; # Plasma has built-in power management
    desktopManager.plasma6 = {
      enable = true;
      enableQt5Integration = true;
    };
  };

  environment.plasma6.excludePackages = with pkgs.kdePackages; [
    konsole
    oxygen
    plasma-browser-integration
  ];

  environment.systemPackages = with pkgs; [
    (catppuccin-kde.override {
      flavour = ["mocha"];
      accents = ["mauve"];
    })
    bibata-cursors
  ];
}
