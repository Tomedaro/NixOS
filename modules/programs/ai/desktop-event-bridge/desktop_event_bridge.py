#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ai_system.events import append_event, normalize_event
from ai_system.io_utils import atomic_write_json, read_json
from ai_system.queue import move_unique
from ai_system.status import write_status_pair
from ai_system.time_utils import get_timezone, now_iso, today


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = get_timezone(os.environ.get("DESKTOP_EVENT_BRIDGE_TIMEZONE", "Europe/Paris"))

STABILITY_SECONDS = int(os.environ.get("DESKTOP_EVENT_STABILITY_SECONDS", "2"))
TRIGGER_HELP_NOW = os.environ.get("TRIGGER_HELP_NOW", "1") == "1"
TRIGGER_HELP_NOW_SERVICE = os.environ.get("TRIGGER_HELP_NOW_SERVICE", "llm-planner-help-now.service")
SYSTEMCTL = os.environ.get("SYSTEMCTL", "systemctl")

RAW_EVENTS_DIR = AI_DIR / "inbox" / "from-desktop" / "events"
PROCESSED_DIR = AI_DIR / "inbox" / "from-desktop" / "processed"
FAILED_DIR = AI_DIR / "inbox" / "from-desktop" / "failed"

EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"

STATE_DESKTOP_DIR = AI_DIR / "state" / "desktop"
STATE_LLM_DIR = AI_DIR / "state" / "llm"
STATE_SESSION_DIR = AI_DIR / "state" / "session"

STATUS_JSON = STATE_DESKTOP_DIR / "desktop-event-bridge-status.json"
STATUS_MD = STATE_DESKTOP_DIR / "desktop-event-bridge-status.md"

LAST_ANSWER_JSON = STATE_LLM_DIR / "last-answer.json"
CURRENT_SESSION_JSON = STATE_SESSION_DIR / "current.json"

HELP_NOW_EVENT_TYPES = {
    "manual_checkin",
    "question_answered",
    "too_hard",
    "stuck",
    "need_smaller_step",
    "overwhelmed",
}


def ensure_dirs():
    for path in [
        RAW_EVENTS_DIR,
        PROCESSED_DIR,
        FAILED_DIR,
        EVENTS_DESKTOP_DIR,
        STATE_DESKTOP_DIR,
        STATE_LLM_DIR,
        STATE_SESSION_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_status(status, message="", details=None):
    write_status_pair(
        STATUS_JSON,
        STATUS_MD,
        updated_at=now_iso(TIMEZONE),
        status=status,
        message=message,
        details=details or {},
        title="Desktop Event Bridge Status",
    )


def newest_unstable_wait_seconds(paths):
    wait_for = 0.0

    for path in paths:
        try:
            age = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            continue

        remaining = STABILITY_SECONDS - age
        if remaining > wait_for:
            wait_for = remaining

    return max(0.0, wait_for)


def should_skip_raw_copy(raw):
    source = str(raw.get("source", "")).strip()
    event = str(raw.get("event") or raw.get("type") or "").strip()

    return source == "dialog-bridge" and event == "question_answered"


def should_trigger_help_now(event):
    event_type = str(event.get("event") or event.get("event_type") or "")
    if event_type in HELP_NOW_EVENT_TYPES:
        return True

    return bool(str(event.get("answer") or "").strip())


def trigger_help_now():
    if not TRIGGER_HELP_NOW:
        return False

    completed = subprocess.run(
        [SYSTEMCTL, "--user", "start", "--no-block", TRIGGER_HELP_NOW_SERVICE],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    return completed.returncode == 0


def process_one(path):
    raw = json.loads(path.read_text(encoding="utf-8"))

    if should_skip_raw_copy(raw):
        destination = move_unique(path, PROCESSED_DIR / today(TIMEZONE), prefix="skipped-")
        return "skipped", False, {
            "reason": "dialog-bridge question_answered copy already processed",
            "processed_path": str(destination),
        }

    session = read_json(CURRENT_SESSION_JSON, {})
    event = normalize_event(
        raw,
        source_file=path,
        ai_dir=AI_DIR,
        tz=TIMEZONE,
        default_source="desktop-event-bridge",
        default_device="desktop",
        session=session,
    )

    event_path = append_event(EVENTS_DESKTOP_DIR, event)

    if event.get("answer") or event.get("answer_label"):
        atomic_write_json(LAST_ANSWER_JSON, event)

    trigger = should_trigger_help_now(event)
    destination = move_unique(path, PROCESSED_DIR / today(TIMEZONE))

    return "processed", trigger, {
        "event_id": event.get("event_id"),
        "event": event.get("event"),
        "source": event.get("source"),
        "answer": event.get("answer", ""),
        "answer_label": event.get("answer_label", ""),
        "event_path": str(event_path),
        "processed_path": str(destination),
    }


def pending_paths():
    return sorted(
        [path for path in RAW_EVENTS_DIR.glob("*.json") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def process_all():
    ensure_dirs()

    paths = pending_paths()

    if not paths:
        write_status("idle", "no pending desktop events")
        print("no pending desktop events")
        return

    wait_for = newest_unstable_wait_seconds(paths)
    if wait_for > 0:
        sleep_for = wait_for + 0.25
        write_status("waiting", f"waiting {sleep_for:.2f}s for desktop event stability")
        print(f"waiting {sleep_for:.2f}s for desktop event stability", flush=True)
        time.sleep(sleep_for)

    paths = pending_paths()

    processed = []
    skipped = []
    failed = []
    needs_help_now = False

    for path in paths:
        try:
            status, trigger, details = process_one(path)

            if status == "processed":
                processed.append(details)
                needs_help_now = needs_help_now or trigger
                print(f"processed desktop event: {details.get('event')} from {path.name}", flush=True)
            elif status == "skipped":
                skipped.append(details)
                print(f"skipped desktop event copy: {path.name}", flush=True)

        except Exception as error:
            try:
                destination = move_unique(path, FAILED_DIR / today(TIMEZONE))
            except Exception:
                destination = path

            failed.append({"path": str(destination), "error": str(error)})
            print(f"failed desktop event {path}: {error}", file=sys.stderr, flush=True)

    triggered = trigger_help_now() if needs_help_now else False

    status = "processed"
    if failed:
        status = "failed"
    elif not processed and not skipped:
        status = "idle"

    write_status(
        status,
        f"processed={len(processed)} skipped={len(skipped)} failed={len(failed)}",
        {
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "triggered_help_now": triggered,
        },
    )


def main():
    try:
        process_all()
    except Exception as error:
        write_status("crashed", str(error), {"error": str(error)})
        print(f"desktop-event-bridge failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
