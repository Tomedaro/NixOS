#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
AW_URL = os.environ.get("ACTIVITYWATCH_URL", "http://127.0.0.1:5600").rstrip("/")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
NOTIFICATION_COOLDOWN_SECONDS = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "600"))
EVENT_FRESHNESS_SECONDS = int(os.environ.get("EVENT_FRESHNESS_SECONDS", "180"))
STARTUP_GRACE_SECONDS = int(os.environ.get("STARTUP_GRACE_SECONDS", "30"))
NOTIFY_SEND = os.environ.get("NOTIFY_SEND", "notify-send")
TIMEZONE = ZoneInfo(os.environ.get("COACH_TIMEZONE", "Europe/Paris"))
SERVICE_STARTED_AT = time.time()

CONTROL_DIR = AI_DIR / "control"
CURRENT_TASK_FILE = CONTROL_DIR / "current-task.md"
LEGACY_CURRENT_TASK_FILE = AI_DIR / "current-task.md"

STATE_DIR = AI_DIR / "state" / "desktop"
LOG_DIR = AI_DIR / "logs" / "desktop"
EVENTS_DIR = AI_DIR / "events" / "desktop"

STATE_FILE = STATE_DIR / "coach-state.json"
NOW_JSON = STATE_DIR / "now.json"
NOW_MD = STATE_DIR / "now.md"


DEFAULT_TASK_TEMPLATE = """# Current Task

Task: Study / productive computer work
Mode: study

Allowed apps: Anki, Obsidian, kitty, Zen, Firefox, Zathura, mpv
Distracting apps: Discord, Steam, Telegram

Allowed title keywords: Anki, Language, General, Programming, Obsidian, modules/programs/ai, documentation, docs
Distracting title keywords: YouTube, Reddit, Twitter, X.com, Twitch, Shorts
"""


def now_local():
    return datetime.now(TIMEZONE)


def now_iso():
    return now_local().isoformat(timespec="seconds")


def today():
    return now_local().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in [CONTROL_DIR, STATE_DIR, LOG_DIR, EVENTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def atomic_write_text(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    atomic_write_json(STATE_FILE, state)


def get_json(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "productivity-coach/0.3"})
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

    awatcher_candidates = [
        (bucket_id, data)
        for bucket_id, data in candidates
        if data.get("client") == "awatcher"
    ]

    selected = awatcher_candidates or candidates
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
    events = get_json(f"{AW_URL}/api/0/buckets/{quoted}/events?limit=1")

    if not events:
        return None

    return events[0]


def parse_aw_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def event_end_time(event):
    if not event:
        return None

    ts = parse_aw_timestamp(event.get("timestamp"))
    if ts is None:
        return None

    duration = event.get("duration", 0) or 0

    try:
        duration = float(duration)
    except Exception:
        duration = 0

    return ts + timedelta(seconds=duration)


def event_is_fresh(event):
    end = event_end_time(event)

    if end is None:
        return False

    age = (datetime.now(timezone.utc) - end).total_seconds()
    return age <= EVENT_FRESHNESS_SECONDS


def in_startup_grace_period():
    return time.time() - SERVICE_STARTED_AT < STARTUP_GRACE_SECONDS


def split_csv(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def ensure_current_task_file():
    if CURRENT_TASK_FILE.exists():
        return True

    if LEGACY_CURRENT_TASK_FILE.exists():
        CURRENT_TASK_FILE.write_text(
            LEGACY_CURRENT_TASK_FILE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return True

    CURRENT_TASK_FILE.write_text(DEFAULT_TASK_TEMPLATE, encoding="utf-8")
    return False


def parse_current_task():
    existed = ensure_current_task_file()

    result = {
        "exists": existed,
        "task": "Study / productive computer work",
        "mode": "study",
        "allowed_apps": ["Anki", "Obsidian", "kitty", "Zen", "Firefox", "Zathura", "mpv"],
        "distracting_apps": ["Discord", "Steam", "Telegram"],
        "allowed_title_keywords": [
            "Anki",
            "Language",
            "General",
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
        text = CURRENT_TASK_FILE.read_text(encoding="utf-8")
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


def classify(window_event, afk_event, task, stale_reasons):
    if stale_reasons:
        return {
            "verdict": "unknown",
            "reason": "ActivityWatch event is stale or unavailable: " + ", ".join(stale_reasons),
        }

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
            "reason": "No fresh current window event available.",
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
            "reason": "Window title matches distracting keywords.",
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
        print(f"Failed to send notification: {error}", file=sys.stderr, flush=True)


def append_markdown_log(entry):
    log_file = LOG_DIR / f"{today()}.md"

    if not log_file.exists():
        log_file.write_text(f"# Desktop Coach Log - {today()}\n\n", encoding="utf-8")

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"## {now_local().strftime('%H:%M:%S')}\n\n")
        handle.write(f"Verdict: {entry['verdict']}  \n")
        handle.write(f"Reason: {entry['reason']}  \n")
        handle.write(f"Task: {entry['task']}  \n")
        handle.write(f"Mode: {entry['mode']}  \n")
        handle.write(f"App: {entry['app']}  \n")
        handle.write(f"Title: {entry['title']}  \n")
        handle.write(f"AFK: {entry['afk']}  \n")
        handle.write(f"Action: {entry['action']}  \n")
        handle.write(f"Startup grace: {entry['startup_grace']}  \n")
        handle.write(f"Window stale: {entry['window_event_stale']}  \n")
        handle.write(f"AFK stale: {entry['afk_event_stale']}  \n\n")


def append_jsonl_event(entry):
    event_file = EVENTS_DIR / f"{today()}.jsonl"

    event = {
        "source": "desktop-coach",
        "timestamp": now_iso(),
        "event": "coach_tick",
        **entry,
    }

    with event_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def write_now(entry):
    now_data = {
        "updated_at": now_iso(),
        **entry,
    }

    atomic_write_json(NOW_JSON, now_data)

    lines = [
        "# Current Desktop Coach Status",
        "",
        f"Last check: {now_data['updated_at']}",
        f"Verdict: `{entry['verdict']}`",
        f"Reason: {entry['reason']}",
        f"Task: {entry['task']}",
        f"Mode: {entry['mode']}",
        f"App: `{entry['app']}`",
        f"Title: `{entry['title']}`",
        f"AFK: `{entry['afk']}`",
        f"Action: `{entry['action']}`",
        f"Startup grace: `{entry['startup_grace']}`",
        f"Window event stale: `{entry['window_event_stale']}`",
        f"AFK event stale: `{entry['afk_event_stale']}`",
        "",
    ]

    atomic_write_text(NOW_MD, "\n".join(lines))


def should_notify(verdict, state, entry):
    if in_startup_grace_period():
        return False

    if entry.get("window_event_stale") or entry.get("afk_event_stale"):
        return False

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
        str(entry["window_event_stale"]),
        str(entry["afk_event_stale"]),
    ])

    last_signature = state.get("last_log_signature")
    last_log_epoch = float(state.get("last_log_epoch", 0))
    now_epoch = time.time()

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

    window_event_is_stale = False
    afk_event_is_stale = False
    stale_reasons = []

    if window_event and not event_is_fresh(window_event):
        window_event_is_stale = True
        stale_reasons.append("window")
        window_event = None

    if afk_event and not event_is_fresh(afk_event):
        afk_event_is_stale = True
        stale_reasons.append("afk")
        afk_event = None

    verdict_data = classify(window_event, afk_event, task, stale_reasons)

    app = ""
    title = ""
    afk = ""

    if window_event:
        app = window_event.get("data", {}).get("app", "") or ""
        title = window_event.get("data", {}).get("title", "") or ""

    if afk_event:
        afk = afk_event.get("data", {}).get("status", "") or ""

    entry = {
        "verdict": verdict_data["verdict"],
        "reason": verdict_data["reason"],
        "task": task["task"],
        "mode": task["mode"],
        "app": app,
        "title": title,
        "afk": afk,
        "action": "none",
        "window_bucket_id": window_bucket_id or "",
        "afk_bucket_id": afk_bucket_id or "",
        "window_event_stale": window_event_is_stale,
        "afk_event_stale": afk_event_is_stale,
        "startup_grace": in_startup_grace_period(),
    }

    if should_notify(verdict_data["verdict"], state, entry):
        if verdict_data["verdict"] == "off_task":
            send_notification(
                "Off task?",
                f"{app} — {title}\nReturn to: {task['task']}",
                urgency="normal",
            )
            entry["action"] = "notification sent"
        elif verdict_data["verdict"] == "no_plan":
            send_notification(
                "No current task",
                f"I created {CURRENT_TASK_FILE}",
                urgency="low",
            )
            entry["action"] = "notification sent"

        state["last_notification_epoch"] = time.time()

    write_now(entry)

    if should_log(entry, state):
        append_markdown_log(entry)
        append_jsonl_event(entry)

        state["last_log_signature"] = "|".join([
            entry["verdict"],
            entry["app"],
            entry["title"],
            entry["afk"],
            entry["task"],
            str(entry["window_event_stale"]),
            str(entry["afk_event_stale"]),
        ])
        state["last_log_epoch"] = time.time()

    state["last_seen"] = {
        "timestamp": now_iso(),
        **entry,
    }

    save_state(state)


def main():
    print("Productivity coach started", flush=True)
    print(f"AI_DIR={AI_DIR}", flush=True)
    print(f"ACTIVITYWATCH_URL={AW_URL}", flush=True)
    print(f"CURRENT_TASK_FILE={CURRENT_TASK_FILE}", flush=True)
    print(f"EVENT_FRESHNESS_SECONDS={EVENT_FRESHNESS_SECONDS}", flush=True)
    print(f"STARTUP_GRACE_SECONDS={STARTUP_GRACE_SECONDS}", flush=True)

    while True:
        try:
            tick()
        except Exception as error:
            print(f"coach tick failed: {error}", file=sys.stderr, flush=True)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
