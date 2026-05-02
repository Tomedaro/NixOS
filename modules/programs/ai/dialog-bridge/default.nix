# modules/programs/ai/dialog-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.dialogBridge;

  dialogScript = pkgs.writeTextFile {
    name = "dialog-bridge";
    destination = "/bin/dialog-bridge";
    executable = true;

    text = ''
      #!${pkgs.python3}/bin/python3

      import json
      import os
      import subprocess
      import sys
      import time
      from datetime import datetime
      from pathlib import Path
      from zoneinfo import ZoneInfo


      AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()

      NOTIFY_SEND = os.environ.get("NOTIFY_SEND", "notify-send")
      TIMEOUT_BIN = os.environ.get("TIMEOUT_BIN", "timeout")
      SYSTEMCTL = os.environ.get("SYSTEMCTL", "systemctl")

      NOTIFICATION_TIMEOUT_SECONDS = int(os.environ.get("NOTIFICATION_TIMEOUT_SECONDS", "60"))
      NOTIFICATION_COOLDOWN_SECONDS = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "600"))
      MAX_QUESTION_AGE_SECONDS = int(os.environ.get("MAX_QUESTION_AGE_SECONDS", "14400"))
      TRIGGER_PLANNER_ON_ANSWER = os.environ.get("TRIGGER_PLANNER_ON_ANSWER", "1") == "1"

      TIMEZONE = ZoneInfo(os.environ.get("DIALOG_BRIDGE_TIMEZONE", "Europe/Paris"))

      STATE_LLM_DIR = AI_DIR / "state" / "llm"
      STATE_DESKTOP_DIR = AI_DIR / "state" / "desktop"
      OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"

      PENDING_QUESTION_JSON = STATE_LLM_DIR / "pending-question.json"
      CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"
      LAST_ANSWER_JSON = STATE_LLM_DIR / "last-answer.json"
      DIALOG_STATE_JSON = STATE_DESKTOP_DIR / "dialog-bridge-state.json"

      INBOX_FROM_DESKTOP_EVENTS = AI_DIR / "inbox" / "from-desktop" / "events"
      EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"


      def now():
          return datetime.now(TIMEZONE)


      def now_iso():
          return now().isoformat(timespec="seconds")


      def today():
          return now().strftime("%Y-%m-%d")


      def ensure_dirs():
          for path in [
              STATE_LLM_DIR,
              STATE_DESKTOP_DIR,
              OUTBOX_TO_PHONE_DIR,
              INBOX_FROM_DESKTOP_EVENTS,
              EVENTS_DESKTOP_DIR,
          ]:
              path.mkdir(parents=True, exist_ok=True)


      def read_json(path, default=None):
          if default is None:
              default = {}
          try:
              if path.exists():
                  return json.loads(path.read_text(encoding="utf-8"))
          except Exception as error:
              return {"_error": str(error)}
          return default


      def write_json_atomic(path, data):
          tmp = path.with_suffix(path.suffix + ".tmp")
          tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
          tmp.replace(path)


      def load_dialog_state():
          return read_json(DIALOG_STATE_JSON, {})


      def save_dialog_state(state):
          write_json_atomic(DIALOG_STATE_JSON, state)


      def current_question_markdown_is_active():
          if not CURRENT_QUESTION_MD.exists():
              return True

          try:
              text = CURRENT_QUESTION_MD.read_text(encoding="utf-8")
          except Exception:
              return True

          if "Status: inactive" in text:
              return False

          return True


      def parse_created_at(value):
          if not value:
              return None

          try:
              # Python accepts "+02:00" offsets here.
              return datetime.fromisoformat(value)
          except Exception:
              return None


      def question_is_too_old(question):
          created = parse_created_at(question.get("created_at"))
          if created is None:
              return False

          age = now().timestamp() - created.timestamp()
          return age > MAX_QUESTION_AGE_SECONDS


      def should_show_question(question, state):
          question_id = question.get("question_id")
          if not question_id:
              return False, "missing question_id"

          if not question.get("question"):
              return False, "missing question text"

          if not question.get("answer_options"):
              return False, "missing answer options"

          if not current_question_markdown_is_active():
              return False, "current-question.md is inactive"

          answered_questions = state.get("answered_questions", {})
          if question_id in answered_questions:
              return False, "already answered"

          if question_is_too_old(question):
              return False, "question too old"

          last_notified = state.get("last_notified", {})
          last_for_question = float(last_notified.get(question_id, 0))
          if time.time() - last_for_question < NOTIFICATION_COOLDOWN_SECONDS:
              return False, "cooldown active"

          return True, "ok"


      def trim_options(options):
          cleaned = []
          seen = set()

          for opt in options:
              opt_id = str(opt.get("id", "")).strip()
              label = str(opt.get("label", "")).strip()

              if not opt_id or not label:
                  continue

              # notify-send action IDs should stay simple.
              opt_id = opt_id.replace(" ", "_")

              if opt_id in seen:
                  continue

              seen.add(opt_id)
              cleaned.append({"id": opt_id, "label": label})

          return cleaned[:3]


      def show_notification(question):
          options = trim_options(question.get("answer_options", []))
          if not options:
              return None

          summary = "AI question"
          body_lines = []

          q = question.get("question", "")
          reason = question.get("reason", "")

          body_lines.append(q)

          if reason:
              body_lines.append("")
              body_lines.append(f"Reason: {reason}")

          if question.get("free_text_allowed"):
              body_lines.append("")
              body_lines.append("Free text is not supported on desktop v0; choose the closest option.")

          body = "\n".join(body_lines)

          cmd = [
              TIMEOUT_BIN,
              str(NOTIFICATION_TIMEOUT_SECONDS),
              NOTIFY_SEND,
              "-a",
              "AI Coach",
              "-u",
              "normal",
              "--wait",
          ]

          for opt in options:
              cmd.append(f"--action={opt['id']}={opt['label']}")

          cmd.extend([summary, body])

          print("showing question notification", flush=True)

          completed = subprocess.run(
              cmd,
              text=True,
              stdout=subprocess.PIPE,
              stderr=subprocess.PIPE,
              check=False,
          )

          if completed.returncode == 124:
              print("notification timed out", flush=True)
              return None

          if completed.stderr.strip():
              print(f"notify-send stderr: {completed.stderr.strip()}", file=sys.stderr, flush=True)

          answer = completed.stdout.strip()

          if not answer:
              return None

          # Sometimes notify-send can include extra lines; use first non-empty line.
          for line in answer.splitlines():
              line = line.strip()
              if line:
                  return line

          return None


      def find_label_for_answer(question, answer_id):
          for opt in question.get("answer_options", []):
              opt_id = str(opt.get("id", "")).strip().replace(" ", "_")
              if opt_id == answer_id:
                  return str(opt.get("label", "")).strip()
          return answer_id


      def write_answer_event(question, answer_id):
          label = find_label_for_answer(question, answer_id)
          epoch = int(time.time())

          event = {
              "source": "dialog-bridge",
              "device": "desktop",
              "event": "question_answered",
              "question_id": question.get("question_id"),
              "question": question.get("question"),
              "reason": question.get("reason", ""),
              "answer": answer_id,
              "answer_label": label,
              "free_text": "",
              "timestamp_epoch": epoch,
              "timestamp": now_iso(),
              "date": today(),
              "time": now().strftime("%H:%M:%S"),
          }

          raw_path = INBOX_FROM_DESKTOP_EVENTS / f"{epoch}_question_answered.json"
          write_json_atomic(raw_path, event)

          jsonl_path = EVENTS_DESKTOP_DIR / f"{today()}.jsonl"
          with jsonl_path.open("a", encoding="utf-8") as handle:
              handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
              handle.write("\n")

          write_json_atomic(LAST_ANSWER_JSON, event)

          return event


      def mark_answered(state, event):
          question_id = event.get("question_id")

          if question_id:
              state.setdefault("answered_questions", {})
              state["answered_questions"][question_id] = {
                  "answered_at": event.get("timestamp"),
                  "answer": event.get("answer"),
                  "answer_label": event.get("answer_label"),
              }

          state["last_answer"] = event
          save_dialog_state(state)


      def mark_notified(state, question):
          question_id = question.get("question_id")
          if not question_id:
              return

          state.setdefault("last_notified", {})
          state["last_notified"][question_id] = time.time()
          state["last_seen_question_id"] = question_id
          state["last_seen_at"] = now_iso()
          save_dialog_state(state)


      def trigger_planner():
          if not TRIGGER_PLANNER_ON_ANSWER:
              return

          try:
              subprocess.run(
                  [
                      SYSTEMCTL,
                      "--user",
                      "start",
                      "llm-planner.service",
                  ],
                  check=False,
              )
          except Exception as error:
              print(f"failed to trigger planner: {error}", file=sys.stderr, flush=True)


      def run_once():
          ensure_dirs()

          question = read_json(PENDING_QUESTION_JSON, {})
          state = load_dialog_state()

          if question.get("_error"):
              print(f"could not read pending question: {question['_error']}", file=sys.stderr, flush=True)
              return

          show, reason = should_show_question(question, state)
          if not show:
              print(f"no dialog shown: {reason}", flush=True)
              return

          mark_notified(state, question)

          answer_id = show_notification(question)
          if not answer_id:
              print("no answer selected", flush=True)
              return

          event = write_answer_event(question, answer_id)
          mark_answered(state, event)

          print(f"answered question {event.get('question_id')} with {answer_id}", flush=True)

          trigger_planner()


      def main():
          try:
              run_once()
          except Exception as error:
              print(f"dialog-bridge failed: {error}", file=sys.stderr, flush=True)
              sys.exit(1)


      if __name__ == "__main__":
          main()
    '';
  };
in
{
  options.my.ai.dialogBridge = {
    enable = lib.mkEnableOption "desktop dialog bridge for LLM questions";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "AI system directory inside the Obsidian vault.";
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to periodically check for pending LLM questions.";
    };

    timerOnCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/2";
      description = "systemd OnCalendar expression for checking pending questions.";
    };

    notificationTimeoutSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How long the notification waits for an answer.";
    };

    notificationCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 600;
      description = "Minimum seconds before repeating the same unanswered question.";
    };

    maxQuestionAgeSeconds = lib.mkOption {
      type = lib.types.int;
      default = 14400;
      description = "Maximum age of a question before it is ignored.";
    };

    triggerPlannerOnAnswer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to start llm-planner.service after an answer is selected.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      pkgs.libnotify
      dialogScript
    ];

    systemd.user.services.dialog-bridge = {
      description = "Desktop dialog bridge for LLM questions";

      after = [
        "ai-vault-init.service"
      ];

      wants = [
        "ai-vault-init.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        NOTIFY_SEND = "${pkgs.libnotify}/bin/notify-send";
        TIMEOUT_BIN = "${pkgs.coreutils}/bin/timeout";
        SYSTEMCTL = "${pkgs.systemd}/bin/systemctl";
        NOTIFICATION_TIMEOUT_SECONDS = toString cfg.notificationTimeoutSeconds;
        NOTIFICATION_COOLDOWN_SECONDS = toString cfg.notificationCooldownSeconds;
        MAX_QUESTION_AGE_SECONDS = toString cfg.maxQuestionAgeSeconds;
        TRIGGER_PLANNER_ON_ANSWER = if cfg.triggerPlannerOnAnswer then "1" else "0";
        DIALOG_BRIDGE_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${dialogScript}/bin/dialog-bridge";
      };
    };

    systemd.user.timers.dialog-bridge = lib.mkIf cfg.enableTimer {
      description = "Check for pending LLM questions";

      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnCalendar = cfg.timerOnCalendar;
        Persistent = true;
        Unit = "dialog-bridge.service";
      };
    };
  };
}
