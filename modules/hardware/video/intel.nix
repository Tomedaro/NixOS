{ pkgs, lib, config, ... }: {
  nixpkgs.config.packageOverrides = pkgs: {
    intel-vaapi-driver = pkgs.intel-vaapi-driver.override { enableHybridCodec = true; };
  };

  boot.initrd.kernelModules = [ "i915" ]; # Early KMS — cleaner Hyprland startup

  boot.kernelParams = [
    "intel_pstate=active"
    "i915.enable_guc=3"    # GuC + HuC firmware (Tiger Lake supports both)
    "i915.enable_psr=1"    # Panel Self Refresh for power savings
    "i915.enable_fbc=1"    # Framebuffer compression
    "i915.fastboot=1"      # Skip unnecessary mode sets at boot
    "mem_sleep_default=deep"
    "i915.enable_dc=2"     # Display power saving
    "nvme.noacpi=1"        # NVME power consumption
  ];

  services.xserver.videoDrivers = [ "modesetting" ];

  hardware.graphics = {
    enable = true;
    extraPackages = with pkgs; [
      intel-media-driver
      intel-vaapi-driver
      libva-vdpau-driver
      libvdpau-va-gl
    ];
  };

  # Only set LIBVA when Hyprland is active — smarter than unconditional
  environment.sessionVariables = lib.optionalAttrs config.programs.hyprland.enable {
    LIBVA_DRIVER_NAME = "iHD";
  };

  # Thermal and Noise Management
  services.thermald.enable = true;
  services.throttled.enable = true;
}
