# modules/programs/ai/coach-daemon/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.coachDaemon;

  coachScript = pkgs.writeShellScriptBin "productivity-coach" ''
    exec ${pkgs.python3}/bin/python3 ${./coach.py} "$@"
  '';
in
{
  options.my.ai.coachDaemon = {
    enable = lib.mkEnableOption "rule-based productivity coach daemon";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "Directory where coach state, logs, and task files are stored.";
    };

    activityWatchUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:5600";
      description = "ActivityWatch server URL.";
    };

    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How often the coach checks ActivityWatch.";
    };

    notificationCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 600;
      description = "Minimum seconds between coach notifications.";
    };

    eventFreshnessSeconds = lib.mkOption {
      type = lib.types.int;
      default = 180;
      description = "Ignore ActivityWatch events older than this many seconds.";
    };

    startupGraceSeconds = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Suppress notifications during this many seconds after coach start.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      pkgs.libnotify
      coachScript
    ];

    systemd.user.services.productivity-coach = {
      description = "Rule-based productivity coach daemon";

      wantedBy = [ "default.target" ];

      after = [
        "aw-server-rust.service"
        "awatcher.service"
        "ai-vault-init.service"
      ];

      wants = [
        "aw-server-rust.service"
        "awatcher.service"
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        ACTIVITYWATCH_URL = cfg.activityWatchUrl;
        INTERVAL_SECONDS = toString cfg.intervalSeconds;
        NOTIFICATION_COOLDOWN_SECONDS = toString cfg.notificationCooldownSeconds;
        EVENT_FRESHNESS_SECONDS = toString cfg.eventFreshnessSeconds;
        STARTUP_GRACE_SECONDS = toString cfg.startupGraceSeconds;
        NOTIFY_SEND = "${pkgs.libnotify}/bin/notify-send";
        COACH_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        ExecStart = "${coachScript}/bin/productivity-coach";
        Restart = "always";
        RestartSec = 10;
      };
    };
  };
}
