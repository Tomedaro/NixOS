# modules/programs/ai/vault-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.vault;

  initScript = pkgs.writeShellScript "ai-vault-init" ''
    set -eu

    AI_DIR="${cfg.aiDir}"
    TASKNOTES_DIR="${cfg.taskNotesDir}"

    mkdir -p "$AI_DIR"

    mkdir -p "$AI_DIR/control"
    mkdir -p "$AI_DIR/policy"

    mkdir -p "$AI_DIR/state/desktop"
    mkdir -p "$AI_DIR/state/phone"
    mkdir -p "$AI_DIR/state/shared"

    mkdir -p "$AI_DIR/state/action-bridge"
    mkdir -p "$AI_DIR/state/llm"
    mkdir -p "$AI_DIR/state/session"

    mkdir -p "$AI_DIR/inbox/from-phone/events"
    mkdir -p "$AI_DIR/inbox/from-phone/processed"
    mkdir -p "$AI_DIR/inbox/from-phone/failed"
    mkdir -p "$AI_DIR/inbox/from-desktop/events"

    mkdir -p "$AI_DIR/inbox/actions"
    mkdir -p "$AI_DIR/inbox/actions-processed"
    mkdir -p "$AI_DIR/inbox/actions-failed"

    mkdir -p "$AI_DIR/outbox/to-phone"
    mkdir -p "$AI_DIR/outbox/to-desktop"

    mkdir -p "$AI_DIR/events/phone"
    mkdir -p "$AI_DIR/events/desktop"
    mkdir -p "$AI_DIR/events/anki"

    mkdir -p "$AI_DIR/events/actions"
    mkdir -p "$AI_DIR/events/tasknotes"
    mkdir -p "$AI_DIR/events/proofs"

    mkdir -p "$AI_DIR/logs/phone"
    mkdir -p "$AI_DIR/logs/desktop"
    mkdir -p "$AI_DIR/logs/anki"

    mkdir -p "$AI_DIR/anki/sessions"

    mkdir -p "$AI_DIR/proofs/phone"

    mkdir -p "$AI_DIR/reflections"
    mkdir -p "$AI_DIR/reports/blocks"
    mkdir -p "$AI_DIR/reports/daily"
    mkdir -p "$AI_DIR/reports/weekly"
    mkdir -p "$AI_DIR/proposed-tasks"
    mkdir -p "$AI_DIR/prompts"
    mkdir -p "$AI_DIR/templates"
    mkdir -p "$AI_DIR/templates/actions"
    mkdir -p "$AI_DIR/schemas"
    mkdir -p "$AI_DIR/tmp"
    mkdir -p "$AI_DIR/cache"
    mkdir -p "$AI_DIR/archive"

    mkdir -p "$TASKNOTES_DIR/AI"

    if [ ! -f "$AI_DIR/README.md" ]; then
      cat > "$AI_DIR/README.md" <<'README'
# AI System Folder

This folder is used by the local productivity system.

## Ownership rules

Phone/Tasker writes:

- `inbox/from-phone/events/`
- `proofs/phone/`

Desktop services write:

- `state/desktop/`
- `logs/desktop/`
- `events/desktop/`
- `anki/`
- `reports/`
- `outbox/to-phone/`

Phone-bridge writes processed phone outputs:

- `events/phone/`
- `logs/phone/`
- `state/phone/`

Human-edited configuration lives in:

- `control/`
- `policy/`

LLM-created obligations should first go to:

- `proposed-tasks/`

Real tasks live in:

- `../TaskNotes/`
README
    fi

    if [ ! -f "$AI_DIR/control/current-task.md" ]; then
      if [ -f "$AI_DIR/current-task.md" ]; then
        cp "$AI_DIR/current-task.md" "$AI_DIR/control/current-task.md"
      else
        cat > "$AI_DIR/control/current-task.md" <<'EOF_TASK'
# Current Task

Task: Review Anki due cards
Mode: anki-study

Allowed apps: Anki, Obsidian, kitty, Zen
Distracting apps: Discord, Steam, Telegram

Allowed title keywords: Anki, Language, General, Programming, Obsidian
Distracting title keywords: YouTube, Reddit, Twitter, X.com, Twitch, Shorts
EOF_TASK
      fi
    fi

    if [ ! -f "$AI_DIR/control/current-block.md" ]; then
      cat > "$AI_DIR/control/current-block.md" <<'EOF_BLOCK'
# Current Block

Status: inactive
Mode: anki-study
Task: Review Anki due cards
Start:
End:
Intervention level: 1
Proof required: no

Allowed apps: Anki, Obsidian, kitty, Zen
Distracting apps: Discord, Steam, Telegram

Allowed domains: docs.ankiweb.net, ankiweb.net
Distracting domains: youtube.com, reddit.com, twitch.tv, x.com, twitter.com
EOF_BLOCK
    fi

    if [ ! -f "$AI_DIR/control/current-mode.md" ]; then
      cat > "$AI_DIR/control/current-mode.md" <<'EOF_MODE'
# Current Mode

Mode: normal
Intervention level: 1
Notes:
EOF_MODE
    fi

    if [ ! -f "$AI_DIR/policy/apps.md" ]; then
      cat > "$AI_DIR/policy/apps.md" <<'EOF_APPS'
# App Policy

## Productive apps

- Anki
- AnkiDroid
- Obsidian
- TaskForge
- kitty
- Zen

## Distracting apps

- Discord
- Steam
- Telegram
- YouTube
- Reddit
- Instagram
- TikTok

## Principle

Desktop browser app is neutral. Prefer URL/domain when available.
Phone browser app is ambiguous unless URL is explicitly shared.
EOF_APPS
    fi

    if [ ! -f "$AI_DIR/policy/domains.md" ]; then
      cat > "$AI_DIR/policy/domains.md" <<'EOF_DOMAINS'
# Domain Policy

## Generally productive

- ankiweb.net
- docs.ankiweb.net
- github.com
- nixos.org
- wiki.nixos.org
- tasknotes.dev
- taskforge.md

## Generally distracting

- youtube.com
- reddit.com
- twitch.tv
- x.com
- twitter.com
- instagram.com

## Context-dependent

- wikipedia.org
- google.com
- github.com
- reddit.com/r/NixOS
EOF_DOMAINS
    fi

    if [ ! -f "$AI_DIR/policy/proof.md" ]; then
      cat > "$AI_DIR/policy/proof.md" <<'EOF_PROOF'
# Proof Policy

Proof should be request-ID based.

Preferred folder:

`AI/proofs/phone/YYYY-MM-DD/<proof-id>/`

Expected files:

- `proof.jpg` or `proof.png`
- `metadata.json`

For Anki, prefer objective AnkiConnect/Anki-Connect-Plus progress over photo proof.
EOF_PROOF
    fi

    if [ ! -f "$AI_DIR/policy/retention.md" ]; then
      cat > "$AI_DIR/policy/retention.md" <<'EOF_RETENTION'
# Retention Policy

- Raw phone event files: keep processed copies for 14 days.
- Daily JSONL files: keep.
- Daily Markdown logs: keep.
- Daily reports: keep.
- Proof images: keep only when useful.
- Temporary/cache folders may be ignored by Syncthing.
EOF_RETENTION
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/current-nudge.md" ]; then
      cat > "$AI_DIR/outbox/to-phone/current-nudge.md" <<'EOF_NUDGE'
# Current Nudge

Status: inactive
Message: No current nudge.
Action: none
EOF_NUDGE
    fi


    if [ ! -f "$AI_DIR/outbox/to-phone/current-nudge.json" ]; then
      cat > "$AI_DIR/outbox/to-phone/current-nudge.json" <<'EOF_NUDGE_JSON'
{
  "schema_version": "phone_interaction.v1",
  "kind": "nudge",
  "status": "inactive",
  "source": "vault-bridge",
  "planner_mode": "none",
  "urgency": "normal",
  "message": "",
  "recommended_next_action": "",
  "actions": []
}
EOF_NUDGE_JSON
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/current-question.md" ]; then
      cat > "$AI_DIR/outbox/to-phone/current-question.md" <<'EOF_QUESTION_MD'
# Current Question

Status: inactive
Question: none
EOF_QUESTION_MD
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/current-question.json" ]; then
      cat > "$AI_DIR/outbox/to-phone/current-question.json" <<'EOF_QUESTION_JSON'
{
  "schema_version": "phone_interaction.v1",
  "kind": "question",
  "status": "inactive",
  "source": "vault-bridge",
  "planner_mode": "none",
  "question": "",
  "answer_options": [],
  "free_text_allowed": true,
  "response_action": "answer_question"
}
EOF_QUESTION_JSON
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/interaction-state.json" ]; then
      cat > "$AI_DIR/outbox/to-phone/interaction-state.json" <<'EOF_INTERACTION_STATE_JSON'
{
  "schema_version": "phone_interaction_state.v1",
  "source": "vault-bridge",
  "planner_mode": "none",
  "active_nudge": null,
  "active_question": null
}
EOF_INTERACTION_STATE_JSON
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/current-task.md" ]; then
      cat > "$AI_DIR/outbox/to-phone/current-task.md" <<'EOF_PHONE_TASK'
# Current Phone Task

Status: inactive
Task: none
EOF_PHONE_TASK
    fi

    if [ ! -f "$AI_DIR/outbox/to-phone/proof-request.md" ]; then
      cat > "$AI_DIR/outbox/to-phone/proof-request.md" <<'EOF_PROOF_REQUEST'
# Current Proof Request

Status: inactive
Proof ID:
Task:
Request:
Deadline:
EOF_PROOF_REQUEST
    fi

    echo "Initialized AI vault structure at $AI_DIR"
  '';
in
{
  options.my.ai.vault = {
    enable = lib.mkEnableOption "AI vault folder structure and templates";

    root = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu";
      description = "Root path of the Obsidian vault.";
    };

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "AI system directory inside the Obsidian vault.";
    };

    taskNotesDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/TaskNotes";
      description = "TaskNotes directory inside the Obsidian vault.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.user.services.ai-vault-init = {
      description = "Initialize AI productivity vault structure";
      wantedBy = [ "default.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${initScript}";
        RemainAfterExit = true;
      };
    };
  };
}
