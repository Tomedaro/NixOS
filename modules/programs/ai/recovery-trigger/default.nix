# modules/programs/ai/recovery-trigger/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.recoveryTrigger;

  recoveryTriggerScript = pkgs.writeShellScriptBin "ai-recovery-trigger" ''
    exec ${pkgs.python3}/bin/python3 ${./recovery_trigger.py} "$@"
  '';
in
{
  options.my.ai.recoveryTrigger = {
    enable = lib.mkEnableOption "local AI deterministic recovery nudge trigger";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/5";
      description = "systemd OnCalendar expression for recovery trigger checks.";
    };

    snoozeCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 1800;
      description = "Seconds after a nudge snooze before another recovery nudge may be offered.";
    };

    recentRecoveryCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 1800;
      description = "Seconds after a terminal recovery before another recovery nudge may be offered.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      recoveryTriggerScript
    ];

    systemd.user.services.ai-recovery-trigger = {
      description = "Local AI deterministic recovery nudge trigger";

      after = [
        "ai-vault-init.service"
        "ai-recovery-manager.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        RECOVERY_TRIGGER_TIMEZONE = "Europe/Paris";
        RECOVERY_TRIGGER_SNOOZE_COOLDOWN_SECONDS = toString cfg.snoozeCooldownSeconds;
        RECOVERY_TRIGGER_RECENT_RECOVERY_COOLDOWN_SECONDS = toString cfg.recentRecoveryCooldownSeconds;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${recoveryTriggerScript}/bin/ai-recovery-trigger --once";
      };
    };

    systemd.user.timers.ai-recovery-trigger = {
      description = "Run local AI deterministic recovery trigger";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "ai-recovery-trigger.service";
      };
    };
  };
}
