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

    # Keep nix-flatpak's default Flathub remote (needed for GFN's Freedesktop
    # runtime) and add NVIDIA's official GeForce NOW repository.
    remotes = lib.mkOptionDefault [
      {
        name = "GeForceNOW";
        location = "https://international.download.nvidia.com/GFNLinux/flatpak/geforcenow.flatpakrepo";
      }
    ];

    packages = [
      {
        appId = "com.nvidia.geforcenow";
        origin = "GeForceNOW";
      }
    ];

    # Empirically required GFN compatibility settings. Do not leak them into
    # the global graphics environment or unrelated Flatpaks.
    overrides."com.nvidia.geforcenow" =
      {
        # GFN's forced EGL Wayland backend crashes its CEF GPU process on this
        # setup. Let EGL choose the backend while keeping the Wayland session.
        Context."unset-environment" = ["EGL_PLATFORM"];
      }
      // lib.optionalAttrs (config.workstation.hardware.videoDriver == "intel") {
        # Intel ANV hides Vulkan Video decode behind this opt-in flag. GFN
        # requires the Vulkan Video H.264/H.265 decode extensions.
        Environment.ANV_DEBUG = "video-decode";
      };

    # Preserve Flatpaks installed outside this declaration. Avoid updating
    # applications during routine NixOS activation; use the timer instead.
    uninstallUnmanaged = false;
    update = {
      onActivation = false;
      auto = {
        enable = true;
        onCalendar = "weekly";
      };
    };

    # Repository/network failures should recover without an endless 60-second
    # retry loop hammering NVIDIA/Flathub.
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
