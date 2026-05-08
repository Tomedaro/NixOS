# modules/programs/ai/session-manager/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.sessionManager;

  sessionScript = pkgs.writeShellScriptBin "ai-session" ''
    export PYTHONPATH="${../python}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${pkgs.python3}/bin/python3 ${./session_manager.py} "$@"
  '';
in
{
  imports = [ ../core ];
  options.my.ai.sessionManager = {
    enable = lib.mkEnableOption "AI productivity session manager";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      sessionScript
    ];

    systemd.user.services.ai-session-status = {
      description = "Show current AI productivity session";

      environment = {
        AI_DIR = cfg.aiDir;
        AI_TIMEZONE = config.my.ai.core.timezone;

        AI_SESSION_TIMEZONE = config.my.ai.core.timezone;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${sessionScript}/bin/ai-session status";
      };
    };
  };
}
