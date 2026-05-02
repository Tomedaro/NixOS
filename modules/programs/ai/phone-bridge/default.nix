# modules/programs/ai/phone-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.phoneBridge;

  phoneBridgeScript = pkgs.writeTextFile {
    name = "phone-bridge";
    destination = "/bin/phone-bridge";
    executable = true;

    text = ''
      #!${pkgs.python3}/bin/python3

      import json
      import os
      import shutil
      import sys
      import time
      from datetime import datetime, timezone
      from pathlib import Path
      from zoneinfo import ZoneInfo


      AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
      INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
      STABILITY_SECONDS = int(os.environ.get("STABILITY_SECONDS", "10"))
      PROCESSED_RETENTION_DAYS = int(os.environ.get("PROCESSED_RETENTION_DAYS", "14"))
      CREATE_TEMPLATES = os.environ.get("CREATE_TEMPLATES", "1") == "1"
      TIMEZONE = ZoneInfo(os.environ.get("PHONE_BRIDGE_TIMEZONE", "Europe/Paris"))


      RAW_EVENTS_DIR = AI_DIR / "inbox" / "from-phone" / "events"
      PROCESSED_DIR = AI_DIR / "inbox" / "from-phone" / "processed"
      FAILED_DIR = AI_DIR / "inbox" / "from-phone" / "failed"

      PHONE_EVENTS_DIR = AI_DIR / "events" / "phone"
      PHONE_LOGS_DIR = AI_DIR / "logs" / "phone"
      PHONE_STATE_DIR = AI_DIR / "state" / "phone"

      POLICY_DIR = AI_DIR / "policy"
      OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"
      PROOFS_PHONE_DIR = AI_DIR / "proofs" / "phone"

      LATEST_JSON = PHONE_STATE_DIR / "latest.json"
      LATEST_MD = PHONE_STATE_DIR / "latest.md"


      APP_POLICY_TEMPLATE = """# App Policy

      This file is for human-readable policy notes.
      The phone bridge does not enforce this yet.

      ## Productive apps

      - AnkiDroid
      - Obsidian
      - TaskForge
      - Syncthing-Fork

      ## Distracting apps

      - YouTube
      - Discord
      - Telegram
      - Reddit
      - Instagram
      - TikTok

      ## Notes

      On phone, app-level data is usually easier to capture than website-level data.
      Treat browsers as ambiguous unless a URL is shared explicitly.
      """


      DOMAIN_POLICY_TEMPLATE = """# Domain Policy

      Desktop browser classification should prefer domains/URLs over browser app names.

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

      ## Principle

      Browser app = neutral.
      Domain and current task decide whether it is productive.
      """


      PROOF_POLICY_TEMPLATE = """# Proof Policy

      Proof files should be request-ID based, not random "last image" based.

      Preferred proof folder:

      `AI/proofs/phone/YYYY-MM-DD/<proof-id>/`

      Expected files:

      - `proof.jpg` or `proof.png`
      - `metadata.json`

      Expected event:

      ```json
      {
        "source": "tasker",
        "event": "proof_submitted",
        "proof_id": "anki-2026-04-30-1215",
        "file": "AI/proofs/phone/2026-04-30/anki-2026-04-30-1215/proof.jpg",
        "timestamp_epoch": "1714470000"
      }
      ```

      For Anki, prefer objective Anki progress proof over photos when possible.
      """


      RETENTION_POLICY_TEMPLATE = """# Retention Policy

      Raw phone events are temporary queue files.

      Recommended lifecycle:

      1. Tasker writes one raw event file into `AI/inbox/from-phone/events/`.
      2. phone-bridge validates it.
      3. phone-bridge appends it to `AI/events/phone/YYYY-MM-DD.jsonl`.
      4. phone-bridge appends a readable line to `AI/logs/phone/YYYY-MM-DD.md`.
      5. phone-bridge moves the raw file to `processed/YYYY-MM-DD/`.
      6. Processed raw files are deleted after the retention window.

      Defaults:

      - Processed raw event retention: 14 days
      - Daily JSONL logs: keep
      - Daily Markdown logs: keep
      - Daily reports: keep
      - Proof images: keep only if useful
      """


      PROOF_REQUEST_TEMPLATE = """# Current Proof Request

      Status: inactive
      Proof ID:
      Task:
      Request:
      Deadline:

      When active, Tasker can use this file to ask for a photo/screenshot proof.
      """


      CURRENT_NUDGE_TEMPLATE = """# Current Nudge

      Status: inactive
      Message: No current nudge.
      Action: none
      """


      PHONE_TASK_TEMPLATE = """# Current Phone Task

      Status: inactive
      Task: none
      """


      def now_local():
          return datetime.now(TIMEZONE)


      def now_iso():
          return now_local().isoformat(timespec="seconds")


      def ensure_dirs():
          for path in [
              RAW_EVENTS_DIR,
              PROCESSED_DIR,
              FAILED_DIR,
              PHONE_EVENTS_DIR,
              PHONE_LOGS_DIR,
              PHONE_STATE_DIR,
              POLICY_DIR,
              OUTBOX_TO_PHONE_DIR,
              PROOFS_PHONE_DIR,
          ]:
              path.mkdir(parents=True, exist_ok=True)


      def write_if_missing(path, text):
          if not path.exists():
              path.write_text(text.strip() + "\n", encoding="utf-8")


      def ensure_templates():
          if not CREATE_TEMPLATES:
              return

          write_if_missing(POLICY_DIR / "apps.md", APP_POLICY_TEMPLATE)
          write_if_missing(POLICY_DIR / "domains.md", DOMAIN_POLICY_TEMPLATE)
          write_if_missing(POLICY_DIR / "proof.md", PROOF_POLICY_TEMPLATE)
          write_if_missing(POLICY_DIR / "retention.md", RETENTION_POLICY_TEMPLATE)

          write_if_missing(OUTBOX_TO_PHONE_DIR / "proof-request.md", PROOF_REQUEST_TEMPLATE)
          write_if_missing(OUTBOX_TO_PHONE_DIR / "current-nudge.md", CURRENT_NUDGE_TEMPLATE)
          write_if_missing(OUTBOX_TO_PHONE_DIR / "current-task.md", PHONE_TASK_TEMPLATE)


      def file_is_stable(path):
          try:
              age = time.time() - path.stat().st_mtime
          except FileNotFoundError:
              return False

          return age >= STABILITY_SECONDS


      def normalize_event(raw, source_file):
          if not isinstance(raw, dict):
              raise ValueError("event JSON is not an object")

          event = raw.get("event") or raw.get("type") or "unknown"
          event = str(event).strip() or "unknown"

          source = str(raw.get("source", "tasker"))
          device = str(raw.get("device", "phone"))

          message = str(raw.get("message", ""))
          timestamp_epoch = raw.get("timestamp_epoch")

          if timestamp_epoch is not None:
              try:
                  timestamp_epoch = int(float(timestamp_epoch))
              except Exception:
                  timestamp_epoch = None

          if timestamp_epoch is None:
              timestamp_epoch = int(source_file.stat().st_mtime)

          dt = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc).astimezone(TIMEZONE)

          normalized = dict(raw)
          normalized["source"] = source
          normalized["device"] = device
          normalized["event"] = event
          normalized["message"] = message
          normalized["timestamp_epoch"] = timestamp_epoch
          normalized["timestamp"] = dt.isoformat(timespec="seconds")
          normalized["date"] = dt.strftime("%Y-%m-%d")
          normalized["time"] = dt.strftime("%H:%M:%S")
          normalized["raw_file"] = str(source_file.relative_to(AI_DIR))
          normalized["processed_at"] = now_iso()

          return normalized


      def append_jsonl(event):
          date = event["date"]
          path = PHONE_EVENTS_DIR / f"{date}.jsonl"

          with path.open("a", encoding="utf-8") as handle:
              handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
              handle.write("\n")


      def append_markdown_log(event):
          date = event["date"]
          path = PHONE_LOGS_DIR / f"{date}.md"

          if not path.exists():
              path.write_text(f"# Phone Log - {date}\n\n", encoding="utf-8")

          message = event.get("message", "")
          proof_id = event.get("proof_id", "")
          file_ref = event.get("file", "")

          line = f"- {event['time']} — `{event['event']}`"

          if message:
              line += f" — {message}"

          if proof_id:
              line += f" — proof: `{proof_id}`"

          if file_ref:
              line += f" — file: `{file_ref}`"

          line += "\n"

          with path.open("a", encoding="utf-8") as handle:
              handle.write(line)


      def write_latest(event):
          tmp = LATEST_JSON.with_suffix(".tmp")
          tmp.write_text(json.dumps(event, indent=2, ensure_ascii=False), encoding="utf-8")
          tmp.replace(LATEST_JSON)

          lines = [
              "# Latest Phone Event",
              "",
              f"Last updated: {now_iso()}",
              f"Event: `{event.get('event', '')}`",
              f"Time: {event.get('timestamp', '')}",
              f"Device: {event.get('device', '')}",
              f"Message: {event.get('message', '')}",
          ]

          if event.get("proof_id"):
              lines.append(f"Proof ID: `{event.get('proof_id')}`")

          if event.get("file"):
              lines.append(f"File: `{event.get('file')}`")

          LATEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


      def unique_destination(path):
          if not path.exists():
              return path

          stem = path.stem
          suffix = path.suffix
          parent = path.parent

          for i in range(1, 10000):
              candidate = parent / f"{stem}-{i}{suffix}"
              if not candidate.exists():
                  return candidate

          raise RuntimeError(f"could not find unique destination for {path}")


      def move_to_processed(source_file, event):
          date_dir = PROCESSED_DIR / event["date"]
          date_dir.mkdir(parents=True, exist_ok=True)

          dest = unique_destination(date_dir / source_file.name)
          shutil.move(str(source_file), str(dest))


      def move_to_failed(source_file, reason):
          date = now_local().strftime("%Y-%m-%d")
          date_dir = FAILED_DIR / date
          date_dir.mkdir(parents=True, exist_ok=True)

          dest = unique_destination(date_dir / source_file.name)

          try:
              shutil.move(str(source_file), str(dest))
              error_file = dest.with_suffix(dest.suffix + ".error.txt")
              error_file.write_text(str(reason) + "\n", encoding="utf-8")
          except Exception as error:
              print(f"failed to move bad event {source_file}: {error}", file=sys.stderr, flush=True)


      def process_event_file(path):
          if not file_is_stable(path):
              return False

          try:
              raw = json.loads(path.read_text(encoding="utf-8"))
              event = normalize_event(raw, path)
              append_jsonl(event)
              append_markdown_log(event)
              write_latest(event)
              move_to_processed(path, event)
              print(f"processed phone event: {event['event']} from {path.name}", flush=True)
              return True
          except Exception as error:
              print(f"failed phone event {path}: {error}", file=sys.stderr, flush=True)
              move_to_failed(path, error)
              return False


      def cleanup_processed():
          if PROCESSED_RETENTION_DAYS <= 0:
              return

          cutoff = time.time() - PROCESSED_RETENTION_DAYS * 86400

          for path in PROCESSED_DIR.rglob("*"):
              if not path.is_file():
                  continue

              try:
                  if path.stat().st_mtime < cutoff:
                      path.unlink()
              except Exception as error:
                  print(f"failed to cleanup processed file {path}: {error}", file=sys.stderr, flush=True)

          # Best-effort empty directory cleanup.
          for path in sorted(PROCESSED_DIR.rglob("*"), reverse=True):
              if path.is_dir():
                  try:
                      path.rmdir()
                  except OSError:
                      pass


      def tick():
          ensure_dirs()
          ensure_templates()

          event_files = sorted(
              [
                  path
                  for path in RAW_EVENTS_DIR.glob("*.json")
                  if path.is_file()
              ],
              key=lambda p: p.stat().st_mtime,
          )

          processed_count = 0

          for path in event_files:
              if process_event_file(path):
                  processed_count += 1

          cleanup_processed()

          return processed_count


      def main():
          print("Phone bridge started", flush=True)
          print(f"AI_DIR={AI_DIR}", flush=True)
          print(f"RAW_EVENTS_DIR={RAW_EVENTS_DIR}", flush=True)

          while True:
              try:
                  count = tick()
                  if count:
                      print(f"processed {count} phone event(s)", flush=True)
              except Exception as error:
                  print(f"phone bridge tick failed: {error}", file=sys.stderr, flush=True)

              time.sleep(INTERVAL_SECONDS)


      if __name__ == "__main__":
          main()
    '';
  };
in
{
  options.my.ai.phoneBridge = {
    enable = lib.mkEnableOption "phone event bridge for Tasker/Syncthing events";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "AI system directory inside the Obsidian vault.";
    };

    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How often the phone bridge scans for new phone event files.";
    };

    stabilitySeconds = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Minimum file age before processing a raw event, to avoid reading partially synced files.";
    };

    processedRetentionDays = lib.mkOption {
      type = lib.types.int;
      default = 14;
      description = "How many days to retain raw processed phone event files.";
    };

    createTemplates = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to create missing AI policy and phone outbox template files.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      phoneBridgeScript
    ];

    systemd.user.services.phone-bridge = {
      description = "Phone event bridge for local AI productivity system";

      wantedBy = [ "default.target" ];

      environment = {
        AI_DIR = cfg.aiDir;
        INTERVAL_SECONDS = toString cfg.intervalSeconds;
        STABILITY_SECONDS = toString cfg.stabilitySeconds;
        PROCESSED_RETENTION_DAYS = toString cfg.processedRetentionDays;
        CREATE_TEMPLATES = if cfg.createTemplates then "1" else "0";
        PHONE_BRIDGE_TIMEZONE = "Europe/Paris";
        PYTHONUNBUFFERED = "1";
      };

      serviceConfig = {
        ExecStart = "${phoneBridgeScript}/bin/phone-bridge";
        Restart = "always";
        RestartSec = 20;
      };
    };
  };
}
