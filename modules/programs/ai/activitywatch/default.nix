# modules/programs/ai/activitywatch/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.activitywatch;

  awatcherConfig = pkgs.writeText "awatcher.toml" ''
    [server]
    port = 5600
    host = "127.0.0.1"

    [awatcher]
    idle-timeout-seconds = ${toString cfg.idleTimeoutSeconds}
    poll-time-idle-seconds = ${toString cfg.pollTimeIdleSeconds}
    poll-time-window-seconds = ${toString cfg.pollTimeWindowSeconds}
  '';
in
{
  options.my.ai.activitywatch = {
    enable = lib.mkEnableOption "ActivityWatch-based productivity telemetry";

    serverPackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.aw-server-rust;
      description = "ActivityWatch server package.";
    };

    watcherPackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.awatcher;
      description = "ActivityWatch watcher package.";
    };

    idleTimeoutSeconds = lib.mkOption {
      type = lib.types.int;
      default = 180;
      description = "Seconds of inactivity before awatcher reports idle state.";
    };

    pollTimeIdleSeconds = lib.mkOption {
      type = lib.types.int;
      default = 4;
      description = "How often awatcher checks idle state.";
    };

    pollTimeWindowSeconds = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "How often awatcher checks active window.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      cfg.serverPackage
      cfg.watcherPackage
    ];

    systemd.user.services.aw-server-rust = {
      description = "ActivityWatch Rust server";
      wantedBy = [ "default.target" ];

      serviceConfig = {
        ExecStart = "${cfg.serverPackage}/bin/aw-server";
        Restart = "on-failure";
        RestartSec = 5;
      };
    };

    systemd.user.services.awatcher = {
      description = "Awatcher ActivityWatch window and idle watcher";
      wantedBy = [ "default.target" ];

      after = [ "aw-server-rust.service" ];
      wants = [ "aw-server-rust.service" ];

      serviceConfig = {
        ExecStart = "${cfg.watcherPackage}/bin/awatcher --config ${awatcherConfig}";
        Restart = "on-failure";
        RestartSec = 5;
      };
    };
  };
}
