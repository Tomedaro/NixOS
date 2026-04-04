{pkgs, ...}: {
  nixpkgs.config.packageOverrides = pkgs: {
    intel-vaapi-driver = pkgs.intel-vaapi-driver.override {enableHybridCodec = true;};
  };

  boot.initrd.kernelModules = ["i915"];  # early KMS
  boot.kernelParams = [
    "intel_pstate=active"
    "i915.enable_guc=3"    # GuC + HuC (was =2)
    "i915.enable_psr=1"
    "i915.enable_fbc=1"
    "i915.fastboot=1"
    "mem_sleep_default=deep"
    "i915.enable_dc=2"
    "nvme.noacpi=1"
  ];

  services.xserver.videoDrivers = ["modesetting"];

  hardware.graphics = {
    enable = true;
    extraPackages = with pkgs; [
      intel-media-driver
      intel-vaapi-driver
      libva-vdpau-driver
      libvdpau-va-gl
    ];
  };

  environment.sessionVariables = {
    LIBVA_DRIVER_NAME = "iHD";  # use intel-media-driver for Iris Xe
  };

  services.thermald.enable = true;
  services.throttled.enable = true;
}
