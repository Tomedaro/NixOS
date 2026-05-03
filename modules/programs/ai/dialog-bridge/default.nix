# modules/programs/ai/dialog-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.dialogBridge;

  dialogScript = pkgs.writeShellScriptBin "dialog-bridge" ''
    exec ${pkgs.python3}/bin/python3 ${./dialog_bridge.py} "$@"
  '';
in
{
  options.my.ai.dialogBridge = {
    enable = lib.mkEnableOption "desktop dialog bridge for LLM questions";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to periodically check for pending LLM questions.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/5";
      description = "systemd OnCalendar expression for checking pending questions.";
    };

    notificationTimeoutSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How long the notification waits for an answer.";
    };

    notificationCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 600;
      description = "Minimum seconds before repeating the same unanswered question.";
    };

    maxQuestionAgeSeconds = lib.mkOption {
      type = lib.types.int;
      default = 14400;
      description = "Maximum age of a question before it is expired.";
    };

    triggerPlannerOnAnswer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to start a planner service after an answer is selected.";
    };

    plannerServiceOnAnswer = lib.mkOption {
      type = lib.types.str;
      default = "llm-planner-help-now.service";
      description = "User systemd service started after a dialog answer.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      pkgs.libnotify
      dialogScript
    ];

    systemd.user.services.dialog-bridge = {
      description = "Desktop dialog bridge for LLM questions";

      after = [
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        NOTIFY_SEND = "${pkgs.libnotify}/bin/notify-send";
        TIMEOUT_BIN = "${pkgs.coreutils}/bin/timeout";
        SYSTEMCTL = "${pkgs.systemd}/bin/systemctl";
        NOTIFICATION_TIMEOUT_SECONDS = toString cfg.notificationTimeoutSeconds;
        NOTIFICATION_COOLDOWN_SECONDS = toString cfg.notificationCooldownSeconds;
        MAX_QUESTION_AGE_SECONDS = toString cfg.maxQuestionAgeSeconds;
        TRIGGER_PLANNER_ON_ANSWER = if cfg.triggerPlannerOnAnswer then "1" else "0";
        TRIGGER_PLANNER_SERVICE = cfg.plannerServiceOnAnswer;
        DIALOG_BRIDGE_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${dialogScript}/bin/dialog-bridge";
      };
    };

    systemd.user.timers.dialog-bridge = lib.mkIf cfg.enableTimer {
      description = "Check for pending LLM questions";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "dialog-bridge.service";
      };
    };
  };
}
