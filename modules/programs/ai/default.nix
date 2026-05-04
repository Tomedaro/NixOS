# modules/programs/ai/default.nix
{ lib, pkgs, ... }:

let
  vaultRoot = "/home/daniil/Sync/Perseverance.Gu";
  aiDir = "${vaultRoot}/AI";
  taskNotesDir = "${vaultRoot}/TaskNotes";
in
{
  imports = [
    ./session-manager
    ./action-bridge
    # Shared foundation / path protocol
    ./vault-bridge
    ./compat

    # Local model runtime
    ./ollama

    # Sensors / telemetry
    ./activitywatch
    ./anki-bridge
    ./phone-bridge
    ./recovery-manager
    ./recovery-trigger

    # Immediate feedback and interaction
    ./coach-daemon
    ./dialog-bridge

    # Higher-level reasoning
    ./llm-planner

    # Future / optional integration layers
    ./notifications
    ./browser-bridge
    ./hypr-agent
  ];

  ###########################################################################
  # Vault / shared file protocol
  ###########################################################################

  my.ai.vault = {
    enable = lib.mkDefault true;

    root = lib.mkDefault vaultRoot;
    aiDir = lib.mkDefault aiDir;
    taskNotesDir = lib.mkDefault taskNotesDir;
  };

  ###########################################################################
  # Ollama
  ###########################################################################

  my.ai.ollama = {
    enable = lib.mkDefault true;

    # Keep CPU for now. Vulkan can be tested later as a separate performance step.
    package = lib.mkDefault pkgs.ollama-cpu;

    # Planner currently uses gemma3:4b.
    #
    # Do not preload qwen2.5vl here yet unless screenshot/vision analysis is active.
    # Preloading extra models increases memory pressure and boot-time failure/noise.
    loadModels = lib.mkDefault [
      "qwen3:1.7b"
    ];

    # Later, when vision/screenshot processing is implemented:
    # loadModels = lib.mkDefault [
    #   "gemma3:4b"
    #   "qwen2.5vl:3b"
    # ];
  };

  ###########################################################################
  # ActivityWatch
  ###########################################################################

  my.ai.activitywatch = {
    enable = lib.mkDefault true;
  };

  ###########################################################################
  # Immediate desktop coach
  ###########################################################################

  my.ai.coachDaemon = {
    enable = lib.mkDefault true;

    # These are explicit for now, even if coach-daemon defaults to my.ai.vault.aiDir.
    # This keeps the file robust during the transition/refactor.
    aiDir = lib.mkDefault aiDir;

    intervalSeconds = lib.mkDefault 60;

    # 300 was a bit aggressive during debugging. Use 600 to avoid nag loops.
    notificationCooldownSeconds = lib.mkDefault 600;

    # Boot safety:
    # ActivityWatch persists old events, so ignore stale boot-time activity.
    eventFreshnessSeconds = lib.mkDefault 180;

    # Suppress notifications for the first few seconds after coach startup.
    startupGraceSeconds = lib.mkDefault 30;
  };

  ###########################################################################
  # Anki bridge
  ###########################################################################

  my.ai.ankiBridge = {
    enable = lib.mkDefault true;

    aiDir = lib.mkDefault aiDir;
    taskNotesDir = lib.mkDefault taskNotesDir;

    decks = lib.mkDefault [
      "Language"
      "General"
    ];

    intervalSeconds = lib.mkDefault 300;

    # Safer authority model:
    # - createTaskNote keeps backwards compatibility as a legacy gate.
    # - taskNoteMode controls whether Anki writes no task, a proposal, or a real TaskNote.
    createTaskNote = lib.mkDefault true;
    taskNoteMode = lib.mkDefault "propose";
  };

  ###########################################################################
  # Phone bridge
  ###########################################################################

  my.ai.phoneBridge = {
    enable = lib.mkDefault true;

    aiDir = lib.mkDefault aiDir;

    intervalSeconds = lib.mkDefault 60;
    stabilitySeconds = lib.mkDefault 10;
    processedRetentionDays = lib.mkDefault 14;

    # Ideally vault-bridge owns templates. Keep this true until phone-bridge
    # has been refactored and verified not to rely on creating any files.
    createTemplates = lib.mkDefault true;
  };

  ###########################################################################
  # LLM planner
  ###########################################################################

  my.ai.llmPlanner = {
    enable = lib.mkDefault true;

    aiDir = lib.mkDefault aiDir;
    taskNotesDir = lib.mkDefault taskNotesDir;

    ollamaUrl = lib.mkDefault "http://127.0.0.1:11434";

    # Default model used when a per-mode model is not configured.
    model = lib.mkDefault "gemma3:4b";

    # Per-mode routing.
    #
    # Keep help-now on gemma3:4b until a faster local model is benchmarked and pulled.
    # Candidate later:
    #   helpNowModel = lib.mkDefault "qwen3:1.7b";
    helpNowModel = lib.mkDefault "gemma3:4b";
    blockPlanModel = lib.mkDefault "gemma3:4b";
    dailyReviewModel = lib.mkDefault "gemma3:4b";

    # Keep manual/on-demand for now.
    # Planner works, but output quality and dialog loop should be stabilized
    # before automatic runs.
    enableTimer = lib.mkDefault false;
    timerOnCalendar = lib.mkDefault "*:0/30";

    # JSON mode is more robust than full schema mode for current local model.
    ollamaFormat = lib.mkDefault "json";

    # Keep context within the 4096 token context window.
    ollamaNumCtx = lib.mkDefault 4096;

    # 900 is enough for the current report/nudge/task output and faster than 1200.
    ollamaNumPredict = lib.mkDefault 900;

    # Fast help-now settings. Deterministic fallback remains permanent.
    helpNowNumPredict = lib.mkDefault 180;
    helpNowTimeoutSeconds = lib.mkDefault 45;

    # Compact context limits tested successfully.
    maxLogChars = lib.mkDefault 800;
    maxJsonlEvents = lib.mkDefault 20;
    maxTaskNotes = lib.mkDefault 5;
    maxContextChars = lib.mkDefault 4500;
    maxTaskNoteChars = lib.mkDefault 700;
    maxPolicyChars = lib.mkDefault 700;
    maxControlChars = lib.mkDefault 1000;
  };

  ###########################################################################
  # Dialog bridge
  ###########################################################################

  my.ai.dialogBridge = {
    enable = lib.mkDefault true;

    aiDir = lib.mkDefault aiDir;

    # Keep timer off until:
    # 1. planner output quality is acceptable,
    # 2. pending-question lifecycle is stable,
    # 3. stale test questions are cleared.
    enableTimer = lib.mkDefault false;

    # When re-enabled, I recommend every 5 minutes at first, not every 2.
    timerOnCalendar = lib.mkDefault "*:0/5";

    notificationTimeoutSeconds = lib.mkDefault 60;
    notificationCooldownSeconds = lib.mkDefault 600;
    maxQuestionAgeSeconds = lib.mkDefault 14400;

    # Good: answering a question should trigger replanning.
    # But this only becomes useful after pending-question lifecycle is stable.
    triggerPlannerOnAnswer = lib.mkDefault true;
  };


  ###########################################################################
  # Unified action bridge
  ###########################################################################

  my.ai.actionBridge = {
    enable = lib.mkDefault true;
    aiDir = lib.mkDefault aiDir;
    taskNotesDir = lib.mkDefault taskNotesDir;
    enablePath = lib.mkDefault true;
    stabilitySeconds = lib.mkDefault 2;
    authorityLevel = lib.mkDefault 2;
    triggerHelpNow = lib.mkDefault true;
  };


  ###########################################################################
  # Recovery nudge trigger
  ###########################################################################

  my.ai.recoveryTrigger = {
    enable = lib.mkDefault false;
  };

  ###########################################################################
  # Session manager / policy compiler
  ###########################################################################

  my.ai.sessionManager.enable = lib.mkDefault true;
  my.ai.sessionManager.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";


  ###########################################################################
  # Recovery lifecycle manager
  ###########################################################################

  my.ai.recoveryManager = {
    enable = lib.mkDefault true;
  };

}
