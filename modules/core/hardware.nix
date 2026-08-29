{config, ...}: let
  hostname = config.workstation.hostName;
  bluetoothSupport = config.workstation.hardware.bluetooth;
in {
  hardware = {
    logitech.wireless.enable = false;
    logitech.wireless.enableGraphical = false;
    graphics.enable = true;
    enableRedistributableFirmware = true;
    keyboard.qmk.enable = true;
    bluetooth = {
      enable = bluetoothSupport;
      powerOnBoot = bluetoothSupport;
      # Keep only the user-visible adapter name. BlueZ's current defaults are
      # sufficient for transport mode, security, reconnect policy and GATT.
      settings.General.Name = hostname;
    };
  };
}
