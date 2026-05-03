# modules/programs/ai/desktop-event-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.desktopEventBridge;

  desktopEventBridgeScript = pkgs.writeShellScriptBin "desktop-event-bridge" ''
    export PYTHONPATH="${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./desktop_event_bridge.py} "$@"
  '';
in
{
  options.my.ai.desktopEventBridge = {
    enable = lib.mkEnableOption "desktop event bridge for Obsidian and future desktop-panel events";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    enablePath = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Use a systemd path unit to process desktop event files when they appear.";
    };

    stabilitySeconds = lib.mkOption {
      type = lib.types.int;
      default = 2;
      description = "Seconds a desktop event file must be unchanged before processing.";
    };

    triggerHelpNow = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether manual check-ins and answer events should trigger help-now planning.";
    };

    helpNowService = lib.mkOption {
      type = lib.types.str;
      default = "llm-planner-help-now.service";
      description = "User systemd service started after a meaningful desktop event.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      desktopEventBridgeScript
    ];

    systemd.user.services.desktop-event-bridge = {
      description = "Process local AI desktop event files";

      after = [
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        DESKTOP_EVENT_BRIDGE_TIMEZONE = "Europe/Paris";
        DESKTOP_EVENT_STABILITY_SECONDS = toString cfg.stabilitySeconds;
        TRIGGER_HELP_NOW = if cfg.triggerHelpNow then "1" else "0";
        TRIGGER_HELP_NOW_SERVICE = cfg.helpNowService;
        SYSTEMCTL = "${pkgs.systemd}/bin/systemctl";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${desktopEventBridgeScript}/bin/desktop-event-bridge";
      };
    };

    systemd.user.paths.desktop-event-bridge = lib.mkIf cfg.enablePath {
      description = "Watch local AI desktop event inbox";

      wantedBy = [ "default.target" ];

      pathConfig = {
        PathExistsGlob = "${cfg.aiDir}/inbox/from-desktop/events/*.json";
        Unit = "desktop-event-bridge.service";
      };
    };
  };
}
