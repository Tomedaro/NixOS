{ config, lib, pkgs, ... }:
let
  cfg = config.my.ai.screenpipe;
in
{
  options.my.ai.screenpipe = {
    enable = lib.mkEnableOption "experimental Screenpipe integration";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.screen-pipe ];
  };
}
