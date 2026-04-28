# modules/programs/ai/default.nix
{lib, pkgs, ... }:
{
  imports = [
    ./hypr-agent
    ./coach-daemon
    ./vault-bridge
    ./notifications
    ./browser-bridge
    ./activitywatch
    ./ollama
    ./compat
    ./screenpipe
  ];

  my.ai.ollama.enable = lib.mkDefault true;
  my.ai.ollama.package = lib.mkDefault pkgs.ollama-cpu;
  my.ai.ollama.loadModels = lib.mkDefault [ "qwen2.5vl:3b" "gemma3:4b" ];
}
