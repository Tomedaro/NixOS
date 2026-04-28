{ config, lib, pkgs, ... }:
let
  cfg = config.my.ai.activitywatch;
in
{
  options.my.ai.activitywatch = {
    enable = lib.mkEnableOption "ActivityWatch-based productivity telemetry";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = with pkgs; [
      activitywatch
    ];

    # later:
    # systemd.user.services.aw-watcher = { ... };
  };
}
