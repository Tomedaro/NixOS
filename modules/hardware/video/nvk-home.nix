{lib, ...}: {
  _class = "homeManager";

  # Historical NVK workaround retained on the user side until the pending
  # driver profile is modernized and validated.
  wayland.windowManager.hyprland.settings.misc.vrr = lib.mkForce 0;
}
