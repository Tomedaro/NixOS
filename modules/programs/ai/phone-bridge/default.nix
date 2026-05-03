# modules/programs/ai/phone-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.phoneBridge;

  phoneBridgeScript = pkgs.writeShellScriptBin "phone-bridge" ''
    export PYTHONPATH="${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./phone_bridge.py} "$@"
  '';
in
{
  options.my.ai.phoneBridge = {
    enable = lib.mkEnableOption "phone event bridge for Tasker/Syncthing events";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "AI system directory inside the Obsidian vault.";
    };

    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How often the phone bridge scans for new phone event files.";
    };

    stabilitySeconds = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Minimum file age before processing a raw event, to avoid reading partially synced files.";
    };

    processedRetentionDays = lib.mkOption {
      type = lib.types.int;
      default = 14;
      description = "How many days to retain raw processed phone event files.";
    };

    createTemplates = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to create missing AI policy and phone outbox template files.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      phoneBridgeScript
    ];

    systemd.user.services.phone-bridge = {
      description = "Phone event bridge for local AI productivity system";

      wantedBy = [ "default.target" ];

      environment = {
        AI_DIR = cfg.aiDir;
        INTERVAL_SECONDS = toString cfg.intervalSeconds;
        STABILITY_SECONDS = toString cfg.stabilitySeconds;
        PROCESSED_RETENTION_DAYS = toString cfg.processedRetentionDays;
        CREATE_TEMPLATES = if cfg.createTemplates then "1" else "0";
        PHONE_BRIDGE_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        ExecStart = "${phoneBridgeScript}/bin/phone-bridge";
        Restart = "always";
        RestartSec = 20;
      };
    };
  };
}
