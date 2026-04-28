{ config, lib, pkgs, ... }:
let
  cfg = config.my.ai.notifications;
in
{
  options.my.ai.notifications = {
    enable = lib.mkEnableOption "desktop productivity notifications";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.mako ];
  };
}
