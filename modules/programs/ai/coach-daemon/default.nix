# modules/programs/ai/coach-daemon/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.coachDaemon;

  coachScript = pkgs.writeTextFile {
    name = "productivity-coach";
    destination = "/bin/productivity-coach";
    executable = true;

    text = ''
      #!${pkgs.python3}/bin/python3

      import json
      import os
      import subprocess
      import sys
      import time
      import urllib.parse
      import urllib.request
      from datetime import datetime
      from pathlib import Path
      from zoneinfo import ZoneInfo


      AI_DIR = Path(os.environ.get("AI_DIR", "/home/Daniil/Sync/Perseverance.Gu/AI")).expanduser()
      AW_URL = os.environ.get("ACTIVITYWATCH_URL", "http://127.0.0.1:5600").rstrip("/")
      INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
      NOTIFICATION_COOLDOWN_SECONDS = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "600"))
      NOTIFY_SEND = os.environ.get("NOTIFY_SEND", "notify-send")
      TIMEZONE = ZoneInfo(os.environ.get("COACH_TIMEZONE", "Europe/Paris"))


      CURRENT_TASK_FILE = AI_DIR / "current-task.md"
      STATE_DIR = AI_DIR / "state"
      LOG_DIR = AI_DIR / "logs"
      INBOX_PHONE_DIR = AI_DIR / "inbox" / "from-phone"
      OUTBOX_PHONE_DIR = AI_DIR / "outbox" / "to-phone"
      STATE_FILE = STATE_DIR / "coach-state.json"


      DEFAULT_TASK_TEMPLATE = """# Current Task

      Task: Study / productive computer work
      Mode: study

      Allowed apps: Anki, Obsidian, kitty, Zen, Firefox, Zathura, mpv
      Distracting apps: Discord, Steam, Telegram

      Allowed title keywords: NixOS, Anki, Programming, Obsidian, modules/programs/ai, documentation, docs
      Distracting title keywords: YouTube, Reddit, Twitter, X.com, Twitch, Shorts
      """


      def now_local():
          return datetime.now(TIMEZONE)


      def ensure_dirs():
          AI_DIR.mkdir(parents=True, exist_ok=True)
          STATE_DIR.mkdir(parents=True, exist_ok=True)
          LOG_DIR.mkdir(parents=True, exist_ok=True)
          INBOX_PHONE_DIR.mkdir(parents=True, exist_ok=True)
          OUTBOX_PHONE_DIR.mkdir(parents=True, exist_ok=True)


      def load_state():
          if not STATE_FILE.exists():
              return {}
          try:
              return json.loads(STATE_FILE.read_text())
          except Exception:
              return {}


      def save_state(state):
          tmp = STATE_FILE.with_suffix(".tmp")
          tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
          tmp.replace(STATE_FILE)


      def get_json(url, timeout=5):
          req = urllib.request.Request(url, headers={"User-Agent": "productivity-coach/0.1"})
          with urllib.request.urlopen(req, timeout=timeout) as response:
              return json.loads(response.read().decode("utf-8"))


      def get_buckets():
          return get_json(f"{AW_URL}/api/0/buckets/")


      def find_bucket_id(bucket_type):
          buckets = get_buckets()
          candidates = []

          for bucket_id, data in buckets.items():
              if data.get("type") == bucket_type:
                  candidates.append((bucket_id, data))

          if not candidates:
              return None

          # Prefer buckets created by awatcher.
          awatcher_candidates = [
              (bucket_id, data)
              for bucket_id, data in candidates
              if data.get("client") == "awatcher"
          ]

          selected = awatcher_candidates or candidates

          # Pick the most recently updated-ish bucket.
          selected.sort(
              key=lambda item: (
                  item[1].get("metadata", {}).get("end")
                  or item[1].get("created")
                  or ""
              ),
              reverse=True,
          )

          return selected[0][0]


      def get_latest_event(bucket_id):
          if not bucket_id:
              return None

          quoted = urllib.parse.quote(bucket_id, safe="")
          url = f"{AW_URL}/api/0/buckets/{quoted}/events?limit=1"
          events = get_json(url)

          if not events:
              return None

          return events[0]


      def split_csv(value):
          return [
              item.strip()
              for item in value.split(",")
              if item.strip()
          ]


      def parse_current_task():
          created = False

          if not CURRENT_TASK_FILE.exists():
              CURRENT_TASK_FILE.write_text(DEFAULT_TASK_TEMPLATE)
              created = True

          result = {
              "exists": not created,
              "task": "Study / productive computer work",
              "mode": "study",
              "allowed_apps": ["Anki", "Obsidian", "kitty", "Zen", "Firefox", "Zathura", "mpv"],
              "distracting_apps": ["Discord", "Steam", "Telegram"],
              "allowed_title_keywords": [
                  "NixOS",
                  "Anki",
                  "Programming",
                  "Obsidian",
                  "modules/programs/ai",
                  "documentation",
                  "docs",
              ],
              "distracting_title_keywords": [
                  "YouTube",
                  "Reddit",
                  "Twitter",
                  "X.com",
                  "Twitch",
                  "Shorts",
              ],
          }

          try:
              text = CURRENT_TASK_FILE.read_text()
          except Exception:
              return result

          for raw_line in text.splitlines():
              line = raw_line.strip()

              if not line or line.startswith("#") or ":" not in line:
                  continue

              key, value = line.split(":", 1)
              key = key.strip().lower()
              value = value.strip()

              if key == "task":
                  result["task"] = value or result["task"]
              elif key == "mode":
                  result["mode"] = value or result["mode"]
              elif key == "allowed apps":
                  result["allowed_apps"] = split_csv(value)
              elif key == "distracting apps":
                  result["distracting_apps"] = split_csv(value)
              elif key == "allowed title keywords":
                  result["allowed_title_keywords"] = split_csv(value)
              elif key == "distracting title keywords":
                  result["distracting_title_keywords"] = split_csv(value)

          return result


      def lower_list(items):
          return [item.lower() for item in items]


      def app_matches(app, app_list):
          app_l = app.lower()
          for candidate in lower_list(app_list):
              if candidate == app_l:
                  return True
              if candidate and candidate in app_l:
                  return True
              if app_l and app_l in candidate:
                  return True
          return False


      def title_contains(title, keywords):
          title_l = title.lower()
          for keyword in lower_list(keywords):
              if keyword and keyword in title_l:
                  return True
          return False


      def classify(window_event, afk_event, task):
          if not task.get("exists", True):
              return {
                  "verdict": "no_plan",
                  "reason": "No current-task.md existed, so a template was created.",
              }

          afk_status = ""
          if afk_event:
              afk_status = afk_event.get("data", {}).get("status", "")

          if afk_status == "afk":
              return {
                  "verdict": "idle",
                  "reason": "ActivityWatch reports AFK.",
              }

          if not window_event:
              return {
                  "verdict": "unknown",
                  "reason": "No current window event available.",
              }

          data = window_event.get("data", {})
          app = data.get("app", "") or ""
          title = data.get("title", "") or ""

          if app_matches(app, task["distracting_apps"]):
              return {
                  "verdict": "off_task",
                  "reason": f"Current app '{app}' matches distracting apps.",
              }

          if title_contains(title, task["distracting_title_keywords"]):
              return {
                  "verdict": "off_task",
                  "reason": f"Window title matches distracting keywords.",
              }

          if app_matches(app, task["allowed_apps"]):
              return {
                  "verdict": "on_task",
                  "reason": f"Current app '{app}' matches allowed apps.",
              }

          if title_contains(title, task["allowed_title_keywords"]):
              return {
                  "verdict": "on_task",
                  "reason": "Window title matches allowed keywords.",
              }

          return {
              "verdict": "unknown",
              "reason": "Current activity matched neither allowed nor distracting rules.",
          }


      def send_notification(summary, body, urgency="normal"):
          try:
              subprocess.run(
                  [
                      NOTIFY_SEND,
                      "-a",
                      "Productivity Coach",
                      "-u",
                      urgency,
                      summary,
                      body,
                  ],
                  check=False,
              )
          except Exception as error:
              print(f"Failed to send notification: {error}", file=sys.stderr)


      def append_log(entry):
          date = now_local().strftime("%Y-%m-%d")
          log_file = LOG_DIR / f"{date}.md"

          if not log_file.exists():
              log_file.write_text(f"# Productivity Coach Log - {date}\n\n")

          with log_file.open("a", encoding="utf-8") as handle:
              handle.write(f"## {now_local().strftime('%H:%M:%S')}\n\n")
              handle.write(f"Verdict: {entry['verdict']}  \n")
              handle.write(f"Reason: {entry['reason']}  \n")
              handle.write(f"Task: {entry['task']}  \n")
              handle.write(f"Mode: {entry['mode']}  \n")
              handle.write(f"App: {entry['app']}  \n")
              handle.write(f"Title: {entry['title']}  \n")
              handle.write(f"AFK: {entry['afk']}  \n")
              handle.write(f"Action: {entry['action']}  \n\n")


      def should_notify(verdict, state):
          if verdict not in ["off_task", "no_plan"]:
              return False

          now_epoch = time.time()
          last_notification_epoch = float(state.get("last_notification_epoch", 0))

          return now_epoch - last_notification_epoch >= NOTIFICATION_COOLDOWN_SECONDS


      def should_log(entry, state):
          signature = "|".join([
              entry["verdict"],
              entry["app"],
              entry["title"],
              entry["afk"],
              entry["task"],
          ])

          last_signature = state.get("last_log_signature")
          last_log_epoch = float(state.get("last_log_epoch", 0))
          now_epoch = time.time()

          # Log on state changes, actions, or every 15 minutes as a heartbeat.
          if signature != last_signature:
              return True

          if entry["action"] != "none":
              return True

          if now_epoch - last_log_epoch >= 900:
              return True

          return False


      def tick():
          ensure_dirs()

          state = load_state()
          task = parse_current_task()

          window_bucket_id = find_bucket_id("currentwindow")
          afk_bucket_id = find_bucket_id("afkstatus")

          window_event = get_latest_event(window_bucket_id)
          afk_event = get_latest_event(afk_bucket_id)

          verdict_data = classify(window_event, afk_event, task)

          app = ""
          title = ""
          afk = ""

          if window_event:
              app = window_event.get("data", {}).get("app", "") or ""
              title = window_event.get("data", {}).get("title", "") or ""

          if afk_event:
              afk = afk_event.get("data", {}).get("status", "") or ""

          action = "none"

          if should_notify(verdict_data["verdict"], state):
              if verdict_data["verdict"] == "off_task":
                  send_notification(
                      "Off task?",
                      f"{app} — {title}\nReturn to: {task['task']}",
                      urgency="normal",
                  )
                  action = "notification sent"
              elif verdict_data["verdict"] == "no_plan":
                  send_notification(
                      "No current task",
                      f"I created {CURRENT_TASK_FILE}",
                      urgency="low",
                  )
                  action = "notification sent"

              state["last_notification_epoch"] = time.time()

          entry = {
              "verdict": verdict_data["verdict"],
              "reason": verdict_data["reason"],
              "task": task["task"],
              "mode": task["mode"],
              "app": app,
              "title": title,
              "afk": afk,
              "action": action,
          }

          if should_log(entry, state):
              append_log(entry)

              state["last_log_signature"] = "|".join([
                  entry["verdict"],
                  entry["app"],
                  entry["title"],
                  entry["afk"],
                  entry["task"],
              ])
              state["last_log_epoch"] = time.time()

          state["last_seen"] = {
              "timestamp": now_local().isoformat(),
              "verdict": entry["verdict"],
              "reason": entry["reason"],
              "task": entry["task"],
              "mode": entry["mode"],
              "app": entry["app"],
              "title": entry["title"],
              "afk": entry["afk"],
              "action": entry["action"],
              "window_bucket_id": window_bucket_id,
              "afk_bucket_id": afk_bucket_id,
          }

          save_state(state)


      def main():
          print("Productivity coach started", flush=True)
          print(f"AI_DIR={AI_DIR}", flush=True)
          print(f"ACTIVITYWATCH_URL={AW_URL}", flush=True)

          while True:
              try:
                  tick()
              except Exception as error:
                  print(f"coach tick failed: {error}", file=sys.stderr, flush=True)

              time.sleep(INTERVAL_SECONDS)


      if __name__ == "__main__":
          main()
    '';
  };
in
{
  options.my.ai.coachDaemon = {
    enable = lib.mkEnableOption "rule-based productivity coach daemon";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/Daniil/Sync/Perseverance.Gu/AI";
      description = "Directory where coach state, logs, and task files are stored.";
    };

    activityWatchUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:5600";
      description = "ActivityWatch server URL.";
    };

    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How often the coach checks ActivityWatch.";
    };

    notificationCooldownSeconds = lib.mkOption {
      type = lib.types.int;
      default = 600;
      description = "Minimum seconds between coach notifications.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      pkgs.libnotify
      coachScript
    ];

    systemd.user.services.productivity-coach = {
      description = "Rule-based productivity coach daemon";

      wantedBy = [ "default.target" ];

      after = [
        "aw-server-rust.service"
        "awatcher.service"
      ];

      wants = [
        "aw-server-rust.service"
        "awatcher.service"
      ];

      environment = {
        AI_DIR = cfg.aiDir;
        ACTIVITYWATCH_URL = cfg.activityWatchUrl;
        INTERVAL_SECONDS = toString cfg.intervalSeconds;
        NOTIFICATION_COOLDOWN_SECONDS = toString cfg.notificationCooldownSeconds;
        NOTIFY_SEND = "${pkgs.libnotify}/bin/notify-send";
        COACH_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        ExecStart = "${coachScript}/bin/productivity-coach";
        Restart = "always";
        RestartSec = 10;
      };
    };
  };
}
