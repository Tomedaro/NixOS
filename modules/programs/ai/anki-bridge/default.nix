# modules/programs/ai/anki-bridge/default.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.my.ai.ankiBridge;

  decksJson = builtins.toJSON cfg.decks;

  ankiBridgeScript = pkgs.writeTextFile {
    name = "anki-bridge";
    destination = "/bin/anki-bridge";
    executable = true;

    text = ''
      #!${pkgs.python3}/bin/python3

      import json
      import os
      import re
      import sys
      import time
      import urllib.request
      from datetime import datetime
      from pathlib import Path
      from zoneinfo import ZoneInfo


      AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
      TASKNOTES_DIR = Path(os.environ.get("TASKNOTES_DIR", "/home/daniil/Sync/Perseverance.Gu/TaskNotes")).expanduser()
      ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765").rstrip("/")
      INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "300"))
      CREATE_TASKNOTE = os.environ.get("CREATE_TASKNOTE", "1") == "1"
      TIMEZONE = ZoneInfo(os.environ.get("ANKI_BRIDGE_TIMEZONE", "Europe/Paris"))

      DECKS = json.loads(os.environ.get("ANKI_DECKS_JSON", "[]"))


      ANKI_DIR = AI_DIR / "anki"
      STATUS_JSON = ANKI_DIR / "status.json"
      STATUS_MD = ANKI_DIR / "status.md"

      TASKNOTE_AI_DIR = TASKNOTES_DIR / "AI"
      RECOVERY_TASK = TASKNOTE_AI_DIR / "anki-due-recovery.md"


      def now():
          return datetime.now(TIMEZONE)


      def now_iso():
          return now().isoformat(timespec="seconds")


      def today_iso_date():
          return now().strftime("%Y-%m-%d")


      def ensure_dirs():
          ANKI_DIR.mkdir(parents=True, exist_ok=True)
          TASKNOTE_AI_DIR.mkdir(parents=True, exist_ok=True)


      def anki_request(action, params=None, timeout=8):
          payload = {
              "action": action,
              "version": 6,
          }

          if params is not None:
              payload["params"] = params

          data = json.dumps(payload).encode("utf-8")

          request = urllib.request.Request(
              ANKI_CONNECT_URL,
              data=data,
              headers={
                  "Content-Type": "application/json",
                  "User-Agent": "anki-bridge/0.1",
              },
              method="POST",
          )

          with urllib.request.urlopen(request, timeout=timeout) as response:
              body = response.read().decode("utf-8")

          parsed = json.loads(body)

          if parsed.get("error") is not None:
              raise RuntimeError(f"AnkiConnect action {action} failed: {parsed.get('error')}")

          return parsed.get("result")


      def quote_deck(deck):
          escaped = deck.replace('"', '\\"')
          return f'deck:"{escaped}"'


      def find_cards_count(query):
          result = anki_request("findCards", {"query": query})
          if result is None:
              return 0
          return len(result)


      def safe_count(query):
          try:
              return find_cards_count(query)
          except Exception as error:
              return {
                  "error": str(error),
                  "query": query,
              }


      def collect_deck(deck):
          prefix = quote_deck(deck)

          counts = {
              "due": safe_count(f"{prefix} is:due"),
              "new": safe_count(f"{prefix} is:new"),
              "learning": safe_count(f"{prefix} is:learn"),
              "review_due": safe_count(f"{prefix} is:review is:due"),
              "reviewed_today": safe_count(f"{prefix} rated:1"),
              "again_today": safe_count(f"{prefix} rated:1:1"),
              "hard_today": safe_count(f"{prefix} rated:1:2"),
              "good_today": safe_count(f"{prefix} rated:1:3"),
              "easy_today": safe_count(f"{prefix} rated:1:4"),
              "suspended": safe_count(f"{prefix} is:suspended"),
          }

          due = counts.get("due")
          new = counts.get("new")
          learning = counts.get("learning")
          review_due = counts.get("review_due")
          reviewed_today = counts.get("reviewed_today")
          again_today = counts.get("again_today")

          numeric_due = due if isinstance(due, int) else 0
          numeric_new = new if isinstance(new, int) else 0
          numeric_learning = learning if isinstance(learning, int) else 0
          numeric_review_due = review_due if isinstance(review_due, int) else 0
          numeric_reviewed_today = reviewed_today if isinstance(reviewed_today, int) else 0
          numeric_again_today = again_today if isinstance(again_today, int) else 0

          if numeric_due >= 300:
              priority = "urgent"
          elif numeric_due >= 100:
              priority = "high"
          elif numeric_due >= 30:
              priority = "medium"
          elif numeric_due > 0:
              priority = "normal"
          else:
              priority = "low"

          if numeric_due > 0:
              if numeric_due >= 100:
                  suggested_goal = "Do a 15-minute recovery block. Aim for 25 reviews, not the whole backlog at once."
              elif numeric_due >= 30:
                  suggested_goal = "Do a 12-minute recovery block. Aim for 20 reviews."
              else:
                  suggested_goal = "Do a short cleanup block. Aim to finish the due cards."
          else:
              suggested_goal = "No due cards. Maintain streak or relearn weak cards."

          return {
              "deck": deck,
              "counts": counts,
              "derived": {
                  "due": numeric_due,
                  "new": numeric_new,
                  "learning": numeric_learning,
                  "review_due": numeric_review_due,
                  "reviewed_today": numeric_reviewed_today,
                  "again_today": numeric_again_today,
                  "priority": priority,
                  "suggested_goal": suggested_goal,
              },
          }


      def collect_status():
          version = anki_request("version")

          try:
              deck_names = anki_request("deckNames")
          except Exception:
              deck_names = None

          selected_decks = DECKS

          if not selected_decks:
              selected_decks = deck_names or []

          deck_statuses = []

          for deck in selected_decks:
              deck_statuses.append(collect_deck(deck))

          totals = {
              "due": sum(item["derived"]["due"] for item in deck_statuses),
              "new": sum(item["derived"]["new"] for item in deck_statuses),
              "learning": sum(item["derived"]["learning"] for item in deck_statuses),
              "review_due": sum(item["derived"]["review_due"] for item in deck_statuses),
              "reviewed_today": sum(item["derived"]["reviewed_today"] for item in deck_statuses),
              "again_today": sum(item["derived"]["again_today"] for item in deck_statuses),
          }

          if totals["due"] >= 300:
              overall_priority = "urgent"
          elif totals["due"] >= 100:
              overall_priority = "high"
          elif totals["due"] >= 30:
              overall_priority = "medium"
          elif totals["due"] > 0:
              overall_priority = "normal"
          else:
              overall_priority = "low"

          return {
              "available": True,
              "timestamp": now_iso(),
              "anki_connect_url": ANKI_CONNECT_URL,
              "anki_connect_version": version,
              "configured_decks": selected_decks,
              "available_decks": deck_names,
              "decks": deck_statuses,
              "totals": totals,
              "overall_priority": overall_priority,
          }


      def unavailable_status(error):
          return {
              "available": False,
              "timestamp": now_iso(),
              "anki_connect_url": ANKI_CONNECT_URL,
              "error": str(error),
              "configured_decks": DECKS,
              "decks": [],
              "totals": {
                  "due": 0,
                  "new": 0,
                  "learning": 0,
                  "review_due": 0,
                  "reviewed_today": 0,
                  "again_today": 0,
              },
              "overall_priority": "unknown",
          }


      def write_json(status):
          tmp = STATUS_JSON.with_suffix(".tmp")
          tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False))
          tmp.replace(STATUS_JSON)


      def write_markdown(status):
          lines = []

          lines.append("# Anki Status")
          lines.append("")
          lines.append(f"Last updated: {status['timestamp']}")
          lines.append(f"Anki available: {str(status['available']).lower()}")
          lines.append("")

          if not status["available"]:
              lines.append("## Error")
              lines.append("")
              lines.append(f"`{status.get('error', 'unknown error')}`")
              lines.append("")
              lines.append("Open Anki and make sure Anki-Connect-Plus is enabled.")
              lines.append("")
              STATUS_MD.write_text("\n".join(lines))
              return

          totals = status["totals"]

          lines.append("## Total")
          lines.append("")
          lines.append(f"- Due: **{totals['due']}**")
          lines.append(f"- Review due: **{totals['review_due']}**")
          lines.append(f"- Learning: **{totals['learning']}**")
          lines.append(f"- New: **{totals['new']}**")
          lines.append(f"- Reviewed today: **{totals['reviewed_today']}**")
          lines.append(f"- Again today: **{totals['again_today']}**")
          lines.append(f"- Priority: **{status['overall_priority']}**")
          lines.append("")

          lines.append("## Decks")
          lines.append("")

          for item in status["decks"]:
              deck = item["deck"]
              d = item["derived"]
              lines.append(f"### {deck}")
              lines.append("")
              lines.append(f"- Due: **{d['due']}**")
              lines.append(f"- Review due: **{d['review_due']}**")
              lines.append(f"- Learning: **{d['learning']}**")
              lines.append(f"- New: **{d['new']}**")
              lines.append(f"- Reviewed today: **{d['reviewed_today']}**")
              lines.append(f"- Again today: **{d['again_today']}**")
              lines.append(f"- Priority: **{d['priority']}**")
              lines.append(f"- Suggested goal: {d['suggested_goal']}")
              lines.append("")

          lines.append("## Coach interpretation")
          lines.append("")

          if totals["due"] > 0:
              lines.append("You have an Anki backlog. The recommended approach is repeated small recovery blocks, not attempting the entire backlog in one sitting.")
              lines.append("")
              lines.append("Suggested next block:")
              lines.append("")
              lines.append("- Open Anki")
              lines.append("- Start with the highest-due deck")
              lines.append("- Do 12–15 minutes")
              lines.append("- Stop and reflect briefly")
          else:
              lines.append("No due cards in the configured decks.")
              lines.append("")

          lines.append("")

          STATUS_MD.write_text("\n".join(lines))


      def sanitize_filename(text):
          text = text.strip().lower()
          text = re.sub(r"[^a-z0-9а-яёA-ZА-ЯЁ._ -]+", "", text)
          text = re.sub(r"\s+", "-", text)
          text = text.strip("-")
          return text or "task"


      def write_tasknote(status):
          if not CREATE_TASKNOTE:
              return

          if not status["available"]:
              return

          totals = status["totals"]
          due = totals["due"]

          title = "Recover Anki backlog"
          priority = "high" if due >= 100 else "medium" if due >= 30 else "normal"

          if due == 0:
              status_value = "done"
              priority = "low"
          else:
              status_value = "todo"

          today = today_iso_date()

          body = []

          body.append("---")
          body.append("tags:")
          body.append("  - task")
          body.append("  - ai")
          body.append("  - anki")
          body.append(f'title: "{title}"')
          body.append(f"status: {status_value}")
          body.append(f"priority: {priority}")
          body.append(f"scheduled: {today}")
          body.append(f"due: {today}")
          body.append("contexts:")
          body.append("  - \"@computer\"")
          body.append("projects:")
          body.append("  - \"[[Anki Recovery]]\"")
          body.append("---")
          body.append("")
          body.append("# Recover Anki backlog")
          body.append("")
          body.append("> Managed by the local AI Anki bridge. Edit carefully; this file may be updated by the bridge.")
          body.append("")
          body.append("## Current status")
          body.append("")
          body.append(f"- Last updated: {status['timestamp']}")
          body.append(f"- Total due: **{totals['due']}**")
          body.append(f"- Review due: **{totals['review_due']}**")
          body.append(f"- Learning: **{totals['learning']}**")
          body.append(f"- New: **{totals['new']}**")
          body.append(f"- Reviewed today: **{totals['reviewed_today']}**")
          body.append(f"- Again today: **{totals['again_today']}**")
          body.append("")
          body.append("## Deck breakdown")
          body.append("")

          for item in status["decks"]:
              d = item["derived"]
              body.append(f"### {item['deck']}")
              body.append("")
              body.append(f"- Due: **{d['due']}**")
              body.append(f"- Review due: **{d['review_due']}**")
              body.append(f"- Learning: **{d['learning']}**")
              body.append(f"- New: **{d['new']}**")
              body.append(f"- Reviewed today: **{d['reviewed_today']}**")
              body.append(f"- Again today: **{d['again_today']}**")
              body.append(f"- Suggested goal: {d['suggested_goal']}")
              body.append("")

          body.append("## Recovery plan")
          body.append("")
          body.append("- [ ] Do one 12–15 minute Anki recovery block")
          body.append("- [ ] Prioritize due review cards before adding new cards")
          body.append("- [ ] After the block, write one sentence about what felt weak")
          body.append("")
          body.append("## Reflection")
          body.append("")
          body.append("- What did I relearn?")
          body.append("- What is still unclear?")
          body.append("- Which cards felt badly written or confusing?")
          body.append("- What should tomorrow's Anki block focus on?")
          body.append("")

          tmp = RECOVERY_TASK.with_suffix(".tmp")
          tmp.write_text("\n".join(body))
          tmp.replace(RECOVERY_TASK)


      def tick():
          ensure_dirs()

          try:
              status = collect_status()
          except Exception as error:
              status = unavailable_status(error)

          write_json(status)
          write_markdown(status)
          write_tasknote(status)


      def main():
          print("Anki bridge started", flush=True)
          print(f"AI_DIR={AI_DIR}", flush=True)
          print(f"TASKNOTES_DIR={TASKNOTES_DIR}", flush=True)
          print(f"ANKI_CONNECT_URL={ANKI_CONNECT_URL}", flush=True)
          print(f"DECKS={DECKS}", flush=True)

          while True:
              try:
                  tick()
              except Exception as error:
                  print(f"anki bridge tick failed: {error}", file=sys.stderr, flush=True)

              time.sleep(INTERVAL_SECONDS)


      if __name__ == "__main__":
          main()
    '';
  };
in
{
  options.my.ai.ankiBridge = {
    enable = lib.mkEnableOption "read-only Anki status bridge for the productivity system";

    aiDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/AI";
      description = "Directory where AI Anki status files are written.";
    };

    taskNotesDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/daniil/Sync/Perseverance.Gu/TaskNotes";
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
      description = "Whether to create/update a TaskNotes task for Anki recovery.";
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
