<<<<<<< HEAD
# This module is untested since i don't own an amd gpu!
{pkgs, ...}: {
  services.xserver = {
    enable = true;
    videoDrivers = ["amdgpu"];
  };
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
    extraPackages = with pkgs; [
      amdvlk
      libvdpau-va-gl
      libva-vdpau-driver
      # vulkan-loader
      # vulkan-extension-layer
      # vulkan-validation-layers
    ];
    extraPackages32 = with pkgs; [driversi686Linux.amdvlk];
=======
{ pkgs, ... }:

{
  services.xserver = {
    # enable = true;  # Already enabled in display manager
    videoDrivers = [ "amdgpu" ];
  };
  environment.systemPackages = with pkgs; [ rocmPackages.amdsmi ];
  hardware.amdgpu = {
    opencl.enable = true;
>>>>>>> upstream/master
  };
}
