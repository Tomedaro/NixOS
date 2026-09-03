{lib, ...}: {
  fileSystems."/mnt/arch" = {
    device = "/dev/disk/by-uuid/0b608695-3b2f-4dd6-a56a-c5ce7dc8a7cd";
    fsType = "ext4";
  };

  fileSystems."/mnt/games" = lib.mkForce {
    device = "/dev/disk/by-uuid/01DA12C1CBDE9100";
    fsType = "ntfs-3g";
    options = [
      "rw"
      "uid=1000"
      "gid=100"
      "noatime"
      "umask=000"
      "nofail"
      "x-gvfs-show"
      "x-systemd.mount-timeout=5"
    ];
  };

  fileSystems."/mnt/work" = lib.mkForce {
    device = "/dev/disk/by-uuid/f6f6d68c-68f8-4c50-8155-105a22b9ff35";
    fsType = "ext4";
    options = [
      "defaults" # Default flags
      "async" # Run all operations async
      "nofail" # Don't error if not plugged in
      "x-gvfs-show" # Show in file explorer
      "x-systemd.mount-timeout=5" # Timout for error
      "X-mount.mkdir" # Make dir if it doesn't exist
    ];
  };

  swapDevices = [
    {
      device = "/swapfile";
      size = 8192;
    }
  ];
}
