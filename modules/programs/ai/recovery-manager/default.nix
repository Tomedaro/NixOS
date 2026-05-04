# modules/programs/ai/recovery-manager/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.recoveryManager;

  recoveryManagerScript = pkgs.writeShellScriptBin "ai-recovery-manager" ''
    exec ${pkgs.python3}/bin/python3 ${./recovery_manager.py} "$@"
  '';
in
{
  options.my.ai.recoveryManager = {
    enable = lib.mkEnableOption "local AI recovery lifecycle manager";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/1";
      description = "systemd OnCalendar expression for recovery lifecycle checks.";
    };

    openGraceSeconds = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Seconds in which close/open pairs are treated as app-context flapping.";
    };

    noLaunchExpireSeconds = lib.mkOption {
      type = lib.types.int;
      default = 900;
      description = "Seconds after recovery start before expiring if no target open is observed.";
    };

    rapidAbortSeconds = lib.mkOption {
      type = lib.types.int;
      default = 90;
      description = "Total dwell below this threshold is rapid-exit evidence, not immediate terminal abort.";
    };

    successDwellSeconds = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "Observed target dwell required for possible_success.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      recoveryManagerScript
    ];

    systemd.user.services.ai-recovery-manager = {
      description = "Local AI recovery lifecycle manager";

      after = [
        "ai-vault-init.service"
        "phone-bridge.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        RECOVERY_MANAGER_TIMEZONE = "Europe/Paris";
        RECOVERY_OPEN_GRACE_SECONDS = toString cfg.openGraceSeconds;
        RECOVERY_NO_LAUNCH_EXPIRE_SECONDS = toString cfg.noLaunchExpireSeconds;
        RECOVERY_RAPID_ABORT_SECONDS = toString cfg.rapidAbortSeconds;
        RECOVERY_SUCCESS_DWELL_SECONDS = toString cfg.successDwellSeconds;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${recoveryManagerScript}/bin/ai-recovery-manager --once";
      };
    };

    systemd.user.timers.ai-recovery-manager = {
      description = "Run local AI recovery lifecycle manager";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "ai-recovery-manager.service";
      };
    };
  };
}
