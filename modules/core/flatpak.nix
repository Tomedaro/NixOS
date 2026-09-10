{
  config,
  inputs,
  lib,
  pkgs,
  ...
}: {
  imports = [inputs.nix-flatpak.nixosModules.nix-flatpak];

  # Flatpak requires a portal implementation on every desktop variant.
  # Desktop environments/compositors can provide a more specific backend;
  # GTK is only the low-priority fallback for variants that provide none.
  xdg.portal = {
    enable = true;
    extraPortals = lib.mkDefault [pkgs.xdg-desktop-portal-gtk];

    # i3 has no desktop-specific portal configuration in this repo. Keep this
    # fallback scoped to that variant so Hyprland/GNOME retain their native
    # portal selection.
    config = lib.mkIf (config.workstation.desktop.environment == "i3") {
      common.default = "gtk";
    };
  };

  services.flatpak = {
    enable = true;

    # Flatpak state is mutable outside the Nix store. Preserve packages the
    # user installed independently, avoid network work during normal NixOS
    # activation, and update managed applications on a separate timer.
    uninstallUnmanaged = false;
    update = {
      onActivation = false;
      auto = {
        enable = true;
        onCalendar = "weekly";
      };
    };

    # Repository/network failures should recover without an endless 60-second
    # retry loop hammering remotes.
    restartOnFailure = {
      enable = true;
      restartDelay = "1m";
      exponentialBackoff = {
        enable = true;
        steps = 6;
        maxDelay = "1h";
      };
    };
  };
}
