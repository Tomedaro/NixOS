# modules/programs/ai/default.nix
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
}
