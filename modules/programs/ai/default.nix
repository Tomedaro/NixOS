# modules/programs/ai/default.nix
{ lib, pkgs, ... }:
{
  imports = [
    ./anki-bridge
    ./hypr-agent
    ./coach-daemon
    ./vault-bridge
    ./notifications
    ./browser-bridge
    ./activitywatch
    ./ollama
    ./compat
    ./phone-bridge
    ./dialog-bridge
  ];

  my.ai.vault.enable = lib.mkDefault true;
  my.ai.vault.root = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu";
  my.ai.vault.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";
  my.ai.vault.taskNotesDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/TaskNotes";

  my.ai.ollama.enable = lib.mkDefault true;
  my.ai.ollama.package = lib.mkDefault pkgs.ollama-cpu;
  my.ai.ollama.loadModels = lib.mkDefault [ "qwen2.5vl:3b" "gemma3:4b" ];

  # Add this if you want ActivityWatch enabled by default
  my.ai.activitywatch.enable = lib.mkDefault true;

  my.ai.coachDaemon.enable = lib.mkDefault true;
  my.ai.coachDaemon.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";
  my.ai.coachDaemon.intervalSeconds = lib.mkDefault 60;
  my.ai.coachDaemon.notificationCooldownSeconds = lib.mkDefault 300;

  my.ai.ankiBridge.enable = lib.mkDefault true;
  my.ai.ankiBridge.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";
  my.ai.ankiBridge.taskNotesDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/TaskNotes";
  my.ai.ankiBridge.decks = lib.mkDefault [ "Language" "General" ];
  my.ai.ankiBridge.intervalSeconds = lib.mkDefault 300;
  my.ai.ankiBridge.createTaskNote = lib.mkDefault true;

  my.ai.phoneBridge.enable = lib.mkDefault true;
  my.ai.phoneBridge.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";
  my.ai.phoneBridge.intervalSeconds = lib.mkDefault 60;
  my.ai.phoneBridge.stabilitySeconds = lib.mkDefault 10;
  my.ai.phoneBridge.processedRetentionDays = lib.mkDefault 14;
  my.ai.phoneBridge.createTemplates = lib.mkDefault true;

  my.ai.dialogBridge.enable = lib.mkDefault true;
  my.ai.dialogBridge.aiDir = lib.mkDefault "/home/daniil/Sync/Perseverance.Gu/AI";

# Keep timer off until manual test works.
  my.ai.dialogBridge.enableTimer = lib.mkDefault false;
  my.ai.dialogBridge.timerOnCalendar = lib.mkDefault "*:0/2";

  my.ai.dialogBridge.notificationTimeoutSeconds = lib.mkDefault 60;
  my.ai.dialogBridge.notificationCooldownSeconds = lib.mkDefault 600;
  my.ai.dialogBridge.maxQuestionAgeSeconds = lib.mkDefault 14400;
  my.ai.dialogBridge.triggerPlannerOnAnswer = lib.mkDefault true;
}
