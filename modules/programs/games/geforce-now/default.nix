{
  config,
  lib,
  pkgs,
  ...
}: let
  appId = "com.nvidia.geforcenow";
  appOrigin = "GeForceNOW";
  isHyprland = config.workstation.desktop.environment == "hyprland";
  userName = config.workstation.user.name;

  launcher = pkgs.callPackage ./launcher.nix {
    inherit appId appOrigin;
    # Keep CAP_SYS_NICE on the compositor itself for the intended scheduling
    # behavior. The bridge clears inheritable/ambient bits before Flatpak, so
    # the capability does not cross the sandbox boundary.
    gamescope = "${config.security.wrapperDir}/gamescope";
    hyprland = config.programs.hyprland.package;
    targetModelRegex = "S2721DGF";
  };

  # Own the Flatpak desktop-file ID in XDG_DATA_HOME, whose XDG precedence is
  # higher than every Flatpak export and system profile.
  desktopItem = pkgs.makeDesktopItem {
    name = appId;
    desktopName = "GeForce NOW";
    genericName = "Cloud Gaming";
    comment = "GeForce NOW through host Gamescope";
    exec = "${launcher}/bin/geforce-now";
    icon = appId;
    terminal = false;
    categories = [
      "Game"
      "Network"
    ];
    startupNotify = false;

    extraConfig = {
      Keywords = "NVIDIA;GFN;cloud;gaming;";
      SingleMainWindow = "true";
      StartupWMClass = "GeForceNOW";
    };

    actions.reset = {
      name = "Reset GeForce NOW";
      exec = "${launcher}/bin/geforce-now --reset";
    };
  };
in {
  assertions = [
    {
      assertion = !isHyprland || config.services.flatpak.enable;
      message = "GeForce NOW integration requires services.flatpak.enable.";
    }
    {
      assertion = !isHyprland || config.programs.gamescope.enable;
      message = "GeForce NOW integration requires host programs.gamescope.enable.";
    }
  ];

  # Preserve nix-flatpak's default Flathub remote and add NVIDIA's official
  # application repository.
  services.flatpak.remotes = lib.mkOptionDefault [
    {
      name = appOrigin;
      location =
        "https://international.download.nvidia.com/GFNLinux/flatpak/geforcenow.flatpakrepo";
    }
  ];

  services.flatpak.packages = [
    {
      appId = appId;
      origin = appOrigin;
    }
  ];

  # Empirically verified GFN compatibility settings:
  # - forcing EGL_PLATFORM=wayland crashes this Intel/CEF setup;
  # - Intel ANV exposes Vulkan Video decoding behind this flag.
  services.flatpak.overrides.${appId} =
    {
      Context."unset-environment" = ["EGL_PLATFORM"];
    }
    // lib.optionalAttrs (config.workstation.hardware.videoDriver == "intel") {
      Environment.ANV_DEBUG = "video-decode";
    };

  # force = true intentionally adopts/replaces the manually copied test file.
  home-manager.users.${userName}.xdg.dataFile."applications/${appId}.desktop" =
    lib.mkIf isHyprland {
      source = "${desktopItem}/share/applications/${appId}.desktop";
      force = true;
    };

  environment.systemPackages = lib.optionals isHyprland [launcher];
}
