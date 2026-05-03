# modules/programs/ai/anki-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.ankiBridge;

  decksJson = builtins.toJSON cfg.decks;

  effectiveTaskNoteMode =
    if cfg.createTaskNote then cfg.taskNoteMode else "off";

  ankiBridgeScript = pkgs.writeShellScriptBin "anki-bridge" ''
    export PYTHONPATH="${../python}:$PYTHONPATH"
    exec ${pkgs.python3}/bin/python3 ${./anki_bridge.py} "$@"
  '';
in
{
  options.my.ai.ankiBridge = {
    enable = lib.mkEnableOption "read-only Anki status bridge for the productivity system";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.aiDir;
      description = "Directory where AI Anki status files are written.";
    };

    taskNotesDir = lib.mkOption {
      type = lib.types.str;
      default = config.my.ai.vault.taskNotesDir;
      description = "Directory where TaskNotes task files are written.";
    };

    ankiConnectUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:8765";
      description = "Anki-Connect-Plus URL.";
    };

    decks = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "Language" "General" ];
      description = "Anki decks to track.";
    };

    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "How often the bridge polls Anki.";
    };

    createTaskNote = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Legacy gate for Anki task output. If false, taskNoteMode is forced to off.";
    };

    taskNoteMode = lib.mkOption {
      type = lib.types.enum [ "off" "propose" "direct" ];
      default = "propose";
      description = ''
        Authority mode for Anki recovery task output.

        off:
          Do not write any task/proposal file.

        propose:
          Write an inspectable proposal under AI/proposed-tasks/anki-recovery.md.

        direct:
          Write/update the real TaskNotes task directly.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      ankiBridgeScript
    ];

    systemd.user.services.anki-bridge = {
      description = "Read-only Anki status bridge";

      wantedBy = [ "default.target" ];

      environment = {
        AI_DIR = cfg.aiDir;
        TASKNOTES_DIR = cfg.taskNotesDir;
        ANKI_CONNECT_URL = cfg.ankiConnectUrl;
        INTERVAL_SECONDS = toString cfg.intervalSeconds;
        CREATE_TASKNOTE = if cfg.createTaskNote then "1" else "0";
        TASKNOTE_MODE = effectiveTaskNoteMode;
        ANKI_DECKS_JSON = decksJson;
        ANKI_BRIDGE_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        ExecStart = "${ankiBridgeScript}/bin/anki-bridge";
        Restart = "always";
        RestartSec = 20;
      };
    };
  };
}
