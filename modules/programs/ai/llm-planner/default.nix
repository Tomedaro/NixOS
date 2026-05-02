# modules/programs/ai/llm-planner/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.llmPlanner;

  plannerScript = pkgs.writeShellScriptBin "llm-planner" ''
    exec ${pkgs.python3}/bin/python3 ${./planner.py} "$@"
  '';
in
{
  options.my.ai.llmPlanner = {
    enable = lib.mkEnableOption "local LLM planner and report generator";

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

    ollamaUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:11434";
      description = "Ollama API URL.";
    };

    model = lib.mkOption {
      type = lib.types.str;
      default = "gemma3:4b";
      description = "Ollama model used by the planner.";
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to run the planner periodically.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/30";
      description = "systemd OnCalendar expression for the planner timer.";
    };

    maxLogChars = lib.mkOption {
      type = lib.types.int;
      default = 12000;
      description = "Maximum characters from each daily markdown log to include in context.";
    };

    maxJsonlEvents = lib.mkOption {
      type = lib.types.int;
      default = 120;
      description = "Maximum recent JSONL events to include from desktop and phone logs.";
    };

    maxTaskNotes = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Maximum TaskNotes markdown files to include as snippets.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      plannerScript
    ];

    systemd.user.services.llm-planner = {
      description = "Local LLM planner for productivity system";

      after = [
        "productivity-coach.service"
        "phone-bridge.service"
        "anki-bridge.service"
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        TASKNOTES_DIR = cfg.taskNotesDir;
        OLLAMA_URL = cfg.ollamaUrl;
        OLLAMA_MODEL = cfg.model;
        MAX_LOG_CHARS = toString cfg.maxLogChars;
        MAX_JSONL_EVENTS = toString cfg.maxJsonlEvents;
        MAX_TASKNOTES = toString cfg.maxTaskNotes;
        LLM_PLANNER_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${plannerScript}/bin/llm-planner";
      };
    };

    systemd.user.timers.llm-planner = lib.mkIf cfg.enableTimer {
      description = "Run local LLM planner periodically";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "llm-planner.service";
      };
    };
  };
}
