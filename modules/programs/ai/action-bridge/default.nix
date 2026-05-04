# modules/programs/ai/action-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.actionBridge;

  actionBridgeScript = pkgs.writeShellScriptBin "ai-action-bridge" ''
    exec ${pkgs.python3}/bin/python3 ${./action_bridge.py} "$@"
  '';
in
{
  options.my.ai.actionBridge = {
    enable = lib.mkEnableOption "unified local AI action bridge";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    taskNotesDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.taskNotesDir;
      description = "TaskNotes directory inside the Obsidian vault.";
    };

    enablePath = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Use a systemd path unit to process action files when they appear.";
    };

    stabilitySeconds = lib.mkOption {
      type = lib.types.int;
      default = 2;
      description = "Seconds an action file must be unchanged before processing.";
    };

    authorityLevel = lib.mkOption {
      type = lib.types.int;
      default = 2;
      description = "Maximum deterministic action authority level.";
    };

    triggerHelpNow = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether check-in actions trigger help-now planning.";
    };

    helpNowService = lib.mkOption {
      type = lib.types.str;
      default = "llm-planner-help-now.service";
      description = "User systemd service started after a check-in action.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      actionBridgeScript
    ];

    systemd.user.services.ai-action-bridge = {
      description = "Unified local AI action bridge";

      # Development-friendly: path units and manual tests may trigger several
      # short oneshot runs in quick succession. Keep protection, but avoid
      # false failures during normal action bursts.
      unitConfig = {
        StartLimitIntervalSec = 60;
        StartLimitBurst = 60;
      };

      after = [
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        TASKNOTES_DIR = cfg.taskNotesDir;
        AI_SESSION_BIN = "/run/current-system/sw/bin/ai-session";
        SYSTEMCTL = "${pkgs.systemd}/bin/systemctl";
        ACTION_BRIDGE_TIMEZONE = "Europe/Paris";
        ACTION_STABILITY_SECONDS = toString cfg.stabilitySeconds;
        ACTION_AUTHORITY_LEVEL = toString cfg.authorityLevel;
        TRIGGER_HELP_NOW = if cfg.triggerHelpNow then "1" else "0";
        TRIGGER_HELP_NOW_SERVICE = cfg.helpNowService;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${actionBridgeScript}/bin/ai-action-bridge";
      };
    };

    systemd.user.paths.ai-action-bridge = lib.mkIf cfg.enablePath {
      description = "Watch local AI action inbox";

      wantedBy = [ "default.target" ];

      pathConfig = {
        PathExistsGlob = "${cfg.aiDir}/inbox/actions/*.json";
        Unit = "ai-action-bridge.service";
      };
    };
  };
}
