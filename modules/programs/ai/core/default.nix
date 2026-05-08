# modules/programs/ai/core/default.nix
{ lib, ... }:

{
  options.my.ai.core = {
    vaultRoot = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu";
      description = "Root path of the human-facing Obsidian vault used by the local AI system.";
    };

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "Canonical AI runtime directory containing queues, state, outboxes, logs, and reports.";
    };

    taskNotesDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/TaskNotes";
      description = "TaskNotes directory used for human-facing tasks and reviewed task drafts.";
    };

    timezone = lib.mkOption {
      type = lib.types.str;
      default = "Europe/Paris";
      description = "Canonical timezone for local AI timestamps, timers, and deterministic CLI output.";
    };

    paths = lib.mkOption {
      type = lib.types.submodule {
        options = {
          phoneOutbox = lib.mkOption {
            type = lib.types.str;
            default = "outbox/to-phone";
            description = "Protocol-relative phone outbox path under my.ai.core.aiDir.";
          };

          desktopOutbox = lib.mkOption {
            type = lib.types.str;
            default = "outbox/to-desktop";
            description = "Protocol-relative desktop outbox path under my.ai.core.aiDir.";
          };

          obsidianOutbox = lib.mkOption {
            type = lib.types.str;
            default = "outbox/to-obsidian";
            description = "Protocol-relative Obsidian outbox path under my.ai.core.aiDir.";
          };

          actionInbox = lib.mkOption {
            type = lib.types.str;
            default = "inbox/actions";
            description = "Protocol-relative intentional action inbox path under my.ai.core.aiDir.";
          };

          phoneEventInbox = lib.mkOption {
            type = lib.types.str;
            default = "inbox/from-phone/events";
            description = "Protocol-relative passive phone telemetry inbox path under my.ai.core.aiDir.";
          };

          obsidianMessageInbox = lib.mkOption {
            type = lib.types.str;
            default = "inbox/obsidian/messages";
            description = "Protocol-relative Obsidian natural-language message inbox path under my.ai.core.aiDir.";
          };

          obsidianActionInbox = lib.mkOption {
            type = lib.types.str;
            default = "inbox/obsidian/actions";
            description = "Protocol-relative Obsidian proposal/action decision inbox path under my.ai.core.aiDir.";
          };
        };
      };
      default = {};
      description = "Canonical protocol-relative paths. Keep stable by default; override only during migrations.";
    };
  };
}
