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
  ];

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

}
