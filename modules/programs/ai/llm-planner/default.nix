# modules/programs/ai/llm-planner/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.llmPlanner;

  selectedHelpNowModel =
    if cfg.helpNowModel == null then cfg.model else cfg.helpNowModel;

  selectedBlockPlanModel =
    if cfg.blockPlanModel == null then cfg.model else cfg.blockPlanModel;

  selectedDailyReviewModel =
    if cfg.dailyReviewModel == null then cfg.model else cfg.dailyReviewModel;

  plannerScript = pkgs.writeShellScriptBin "llm-planner" ''
    export PYTHONPATH="${./python}:${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./planner.py} "$@"
  '';

  benchmarkScript = pkgs.writeShellScriptBin "llm-planner-benchmark-models" ''
    export PYTHONPATH="${./python}:${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./benchmark_models.py} "$@"
  '';

  commonEnvironment = {
    AI_DIR = cfg.aiDir;
    TASKNOTES_DIR = cfg.taskNotesDir;
    OLLAMA_URL = cfg.ollamaUrl;
    OLLAMA_MODEL = cfg.model;
    OLLAMA_FORMAT = cfg.ollamaFormat;
    OLLAMA_NUM_CTX = toString cfg.ollamaNumCtx;
    OLLAMA_NUM_PREDICT = toString cfg.ollamaNumPredict;
    OLLAMA_TIMEOUT_SECONDS = toString cfg.ollamaTimeoutSeconds;
    OLLAMA_KEEP_ALIVE = cfg.ollamaKeepAlive;
    ENABLE_SCHEMA_RETRY = "0";
    MAX_LOG_CHARS = toString cfg.maxLogChars;
    MAX_JSONL_EVENTS = toString cfg.maxJsonlEvents;
    MAX_TASKNOTES = toString cfg.maxTaskNotes;
    MAX_TASKNOTE_CHARS = toString cfg.maxTaskNoteChars;
    MAX_POLICY_CHARS = toString cfg.maxPolicyChars;
    MAX_CONTROL_CHARS = toString cfg.maxControlChars;
    MAX_CONTEXT_CHARS = toString cfg.maxContextChars;
    LLM_PLANNER_TIMEZONE = "Europe/Paris";
    PYTHONUNBUFFERED = "1";
  };
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
      description = "Default fallback Ollama model used by the planner.";
    };

    helpNowModel = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Ollama model used for fast help-now planning. Null means use my.ai.llmPlanner.model.";
    };

    blockPlanModel = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Ollama model used for normal block planning. Null means use my.ai.llmPlanner.model.";
    };

    dailyReviewModel = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Ollama model used for slower daily reviews. Null means use my.ai.llmPlanner.model.";
    };

    ollamaFormat = lib.mkOption {
      type = lib.types.str;
      default = "json";
      description = "Ollama structured output mode: json or schema.";
    };

    ollamaNumCtx = lib.mkOption {
      type = lib.types.int;
      default = 4096;
      description = "Ollama context window requested by the planner.";
    };

    ollamaNumPredict = lib.mkOption {
      type = lib.types.int;
      default = 900;
      description = "Maximum generated tokens for normal planner output.";
    };

    ollamaTimeoutSeconds = lib.mkOption {
      type = lib.types.int;
      default = 600;
      description = "Default Ollama request timeout for normal planner runs.";
    };

    ollamaKeepAlive = lib.mkOption {
      type = lib.types.str;
      default = "10m";
      description = "Ollama keep_alive value used by planner requests.";
    };

    helpNowNumPredict = lib.mkOption {
      type = lib.types.int;
      default = 180;
      description = "Maximum generated tokens for help-now planner output.";
    };

    helpNowTimeoutSeconds = lib.mkOption {
      type = lib.types.int;
      default = 45;
      description = "Ollama request timeout for help-now planner runs.";
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to run the block-plan planner periodically.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/30";
      description = "systemd OnCalendar expression for the planner timer.";
    };

    maxLogChars = lib.mkOption {
      type = lib.types.int;
      default = 800;
      description = "Maximum characters from each daily markdown log to include in context.";
    };

    maxJsonlEvents = lib.mkOption {
      type = lib.types.int;
      default = 20;
      description = "Maximum recent JSONL events to include from desktop and phone logs.";
    };

    maxTaskNotes = lib.mkOption {
      type = lib.types.int;
      default = 5;
      description = "Maximum TaskNotes markdown files to include as snippets.";
    };

    maxTaskNoteChars = lib.mkOption {
      type = lib.types.int;
      default = 700;
      description = "Maximum characters included from each TaskNotes file.";
    };

    maxPolicyChars = lib.mkOption {
      type = lib.types.int;
      default = 700;
      description = "Maximum characters included from each policy file.";
    };

    maxControlChars = lib.mkOption {
      type = lib.types.int;
      default = 1000;
      description = "Maximum characters included from each control file.";
    };

    maxContextChars = lib.mkOption {
      type = lib.types.int;
      default = 4500;
      description = "Maximum characters in final markdown context pack.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      plannerScript
      benchmarkScript
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

      environment = commonEnvironment // {
        PLANNER_MODE = "block-plan";
        OLLAMA_MODEL = selectedBlockPlanModel;
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${plannerScript}/bin/llm-planner --mode block-plan";
        TimeoutStartSec = 420;
      };
    };

    systemd.user.services.llm-planner-help-now = {
      description = "Fast local LLM planner after check-in or answer";

      after = [
        "productivity-coach.service"
        "phone-bridge.service"
        "anki-bridge.service"
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = commonEnvironment // {
        PLANNER_MODE = "help-now";
        OLLAMA_MODEL = selectedHelpNowModel;
        OLLAMA_NUM_PREDICT = toString cfg.helpNowNumPredict;
        OLLAMA_TIMEOUT_SECONDS = toString cfg.helpNowTimeoutSeconds;
        MAX_CONTEXT_CHARS = "1200";
        MAX_LOG_CHARS = "200";
        MAX_JSONL_EVENTS = "5";
        MAX_TASKNOTES = "1";
        MAX_TASKNOTE_CHARS = "300";
        MAX_POLICY_CHARS = "300";
        MAX_CONTROL_CHARS = "700";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${plannerScript}/bin/llm-planner --mode help-now";
        TimeoutStartSec = cfg.helpNowTimeoutSeconds + 30;
      };
    };

    systemd.user.services.llm-planner-daily-review = {
      description = "Slow local LLM daily review for productivity system";

      after = [
        "productivity-coach.service"
        "phone-bridge.service"
        "anki-bridge.service"
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = commonEnvironment // {
        PLANNER_MODE = "daily-review";
        OLLAMA_MODEL = selectedDailyReviewModel;
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${plannerScript}/bin/llm-planner --mode daily-review";
        TimeoutStartSec = 1200;
      };
    };

    systemd.user.timers.llm-planner = lib.mkIf cfg.enableTimer {
      description = "Run local LLM block planner periodically";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "llm-planner.service";
      };
    };
  };
}
