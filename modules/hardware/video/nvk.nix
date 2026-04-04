# This module uses nouveau with NVK which is the nvidia open-source user-space driver and is not recommended to use as of 30/05/24 since it's unstable
<<<<<<< HEAD
{pkgs, ...}: let
  env = {
    NVK_I_WANT_A_BROKEN_VULKAN_DRIVER = "1"; # Adds support for my gpu (gtx 1080)
    # MESA_VK_VERSION_OVERRIDE = "1.3";
    # __GLX_VENDOR_LIBRARY_NAME = "mesa";
    # GALLIUM_DRIVER = "zink";
    # MESA_LOADER_DRIVER_OVERRIDE = "zink"; # TODO TEST
    # MESA_VK_DEVICE_SELECT="nvk";

    WLR_RENDERER = "vulkan";
    __GL_GSYNC_ALLOWED = "1"; # GSync
  };
in {
  boot = {
    kernelParams = [
      "nouveau.config=NvGspRm=1"
      "nouveau.config=NvModesetKms=0" # TODO Test
      "nouveau.debug=info,VBIOS=info,gsp=debug" # TODO Remove
      # "nouveau.modeset=1"
    ];
    kernelModules = ["nouveau"];
    blacklistedKernelModules = ["nvidia" "nvidia_uvm"];
=======
{ pkgs, lib, ... }:
let
  env = {
    NVK_I_WANT_A_BROKEN_VULKAN_DRIVER = "1"; # Adds support for older gpus
    MESA_LOADER_DRIVER_OVERRIDE = "zink";
    GALLIUM_DRIVER = "zink";

    GBM_BACKEND = "nouveau";
    WLR_RENDERER = "vulkan";
    WLR_NO_HARDWARE_CURSORS = "1";
    __GL_GSYNC_ALLOWED = "1"; # GSync
  };
in
{
  boot = {
    kernelParams = [
      "nouveau.modeset=1"
      "nouveau.config=NvGspRm=1"
      # "nouveau.debug=info,VBIOS=info,gsp=debug" # TODO Remove
    ];
    kernelModules = [ "nouveau" ];
    blacklistedKernelModules = [
      "nvidia"
      "nvidia_uvm"
    ];
>>>>>>> upstream/master
  };

  environment.sessionVariables = env;
  environment.variables = env;

<<<<<<< HEAD
  services.xserver.videoDrivers = ["modesetting"]; # "modesetting" is better than "nouveau"
  # environment.variables.WLR_NO_HARDWARE_CURSORS = "1";
=======
  services.xserver.videoDrivers = [ "modesetting" ]; # "modesetting" is better than "nouveau"
>>>>>>> upstream/master

  hardware = {
    # nvidia.package = lib.mkDefault config.boot.kernelPackages.nvidiaPackages.latest;
    graphics = {
      enable = true;
      enable32Bit = true;
      extraPackages = with pkgs; [
        mesa # Enables mesa
<<<<<<< HEAD
        mesa.drivers # Enables the use of mesa drivers
=======
>>>>>>> upstream/master

        nvidia-vaapi-driver # Not sure if this is needed
        libva-vdpau-driver # Not sure if this is needed
        libvdpau-va-gl # Not sure if this is needed
      ];
    };
  };
<<<<<<< HEAD
=======
  # Fix black screen issues
  home-manager.sharedModules = [
    (
      { config, ... }:
      {
        wayland.windowManager.hyprland.settings.misc.vrr = lib.mkForce 0;
      }
    )
  ];
>>>>>>> upstream/master
}
