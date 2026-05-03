# modules/programs/ai/session-manager/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.sessionManager;

  sessionScript = pkgs.writeShellScriptBin "ai-session" ''
    exec ${pkgs.python3}/bin/python3 ${./session_manager.py} "$@"
  '';

  requestScript = pkgs.writeShellScriptBin "ai-session-requests" ''
    exec ${pkgs.python3}/bin/python3 ${./session_requests.py} "$@"
  '';
in
{
  options.my.ai.sessionManager = {
    enable = lib.mkEnableOption "AI productivity session manager";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "AI system directory inside the Obsidian vault.";
    };

    enableRequestBridge = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Process session request JSON files from the vault inbox.";
    };

    enableRequestPath = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Use a systemd path unit to process session requests when files appear.";
    };

    requestStabilitySeconds = lib.mkOption {
      type = lib.types.int;
      default = 2;
      description = "Seconds a request file must be unchanged before processing.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      sessionScript
      requestScript
    ];

    systemd.user.services.ai-session-status = {
      description = "Show current AI productivity session";

      environment = {
        AI_DIR = cfg.aiDir;
        AI_SESSION_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${sessionScript}/bin/ai-session status";
      };
    };

    systemd.user.services.ai-session-requests = lib.mkIf cfg.enableRequestBridge {
      description = "Process AI session request files";

      after = [
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        AI_SESSION_BIN = "${sessionScript}/bin/ai-session";
        AI_SESSION_TIMEZONE = "Europe/Paris";
        SESSION_REQUEST_STABILITY_SECONDS = toString cfg.requestStabilitySeconds;
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${requestScript}/bin/ai-session-requests";
      };
    };

    systemd.user.paths.ai-session-requests = lib.mkIf (cfg.enableRequestBridge && cfg.enableRequestPath) {
      description = "Watch AI session request inbox";

      wantedBy = [ "default.target" ];

      pathConfig = {
        PathExistsGlob = "${cfg.aiDir}/inbox/session-requests/*.json";
        Unit = "ai-session-requests.service";
      };
    };
  };
}
