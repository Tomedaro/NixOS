# modules/programs/ai/intervention-outcomes/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.interventionOutcomes;

  interventionOutcomesScript = pkgs.writeShellScriptBin "ai-intervention-outcomes" ''
    export PYTHONPATH="${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./intervention_outcomes_reporter.py} "$@"
  '';
in
{
  options.my.ai.interventionOutcomes = {
    enable = lib.mkEnableOption "local AI intervention outcome reporter";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run intervention outcome reporting on a systemd timer.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/30";
      description = "systemd OnCalendar expression for intervention outcome reports.";
    };

    days = lib.mkOption {
      type = lib.types.int;
      default = 7;
      description = "Number of recent days of event logs to summarize.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      interventionOutcomesScript
    ];

    systemd.user.services.ai-intervention-outcomes = {
      description = "Local AI intervention outcome reporter";

      after = [
        "ai-vault-init.service"
        "ai-action-bridge.service"
        "ai-recovery-manager.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        INTERVENTION_OUTCOMES_TIMEZONE = "Europe/Paris";
        INTERVENTION_OUTCOMES_DAYS = toString cfg.days;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${interventionOutcomesScript}/bin/ai-intervention-outcomes --days ${toString cfg.days} --write";
      };
    };

    systemd.user.timers.ai-intervention-outcomes = lib.mkIf cfg.enableTimer {
      description = "Run local AI intervention outcome reporter";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "ai-intervention-outcomes.service";
      };
    };
  };
}
