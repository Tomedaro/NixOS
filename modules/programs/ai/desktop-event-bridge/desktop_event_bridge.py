#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = ZoneInfo(os.environ.get("DESKTOP_EVENT_BRIDGE_TIMEZONE", "Europe/Paris"))

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


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


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


def atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path, default=None):
    if default is None:
        default = {}

    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as error:
        return {"error": str(error)}

    return default


def append_jsonl(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def write_status(status, message="", details=None):
    details = details or {}

    data = {
        "updated_at": now_iso(),
        "status": status,
        "message": message,
        "details": details,
    }

    atomic_write_json(STATUS_JSON, data)

    lines = [
        "# Desktop Event Bridge Status",
        "",
        f"Updated: {data['updated_at']}",
        f"Status: `{status}`",
        f"Message: {message}",
        "",
    ]

    if details:
        lines.extend([
            "## Details",
            "",
            "```json",
            json.dumps(details, indent=2, ensure_ascii=False),
            "```",
            "",
        ])

    atomic_write_text(STATUS_MD, "\n".join(lines))


def file_is_stable(path):
    try:
        return time.time() - path.stat().st_mtime >= STABILITY_SECONDS
    except FileNotFoundError:
        return False


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


def unique_destination(path):
    if not path.exists():
        return path

    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"could not find unique destination for {path}")


def move_to_dir(path, root_dir, prefix=""):
    date_dir = root_dir / today()
    date_dir.mkdir(parents=True, exist_ok=True)

    name = f"{prefix}{path.name}" if prefix else path.name
    destination = unique_destination(date_dir / name)
    shutil.move(str(path), str(destination))
    return destination


def parse_event_time(raw, source_file):
    epoch = raw.get("timestamp_epoch")

    if epoch is not None:
        try:
            epoch = int(float(epoch))
            dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(TIMEZONE)
            return dt, epoch
        except Exception:
            pass

    timestamp = raw.get("timestamp") or raw.get("created_at") or raw.get("observed_at")
    if timestamp:
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).astimezone(TIMEZONE)
            return dt, int(dt.timestamp())
        except Exception:
            pass

    epoch = int(source_file.stat().st_mtime)
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(TIMEZONE)
    return dt, epoch


def should_skip_raw_copy(raw):
    source = str(raw.get("source", "")).strip()
    event = str(raw.get("event") or raw.get("type") or "").strip()

    # dialog-bridge already appends these to events/desktop and updates last-answer.
    # It also keeps a raw inbox copy for audit, so desktop-event-bridge should not duplicate it.
    return source == "dialog-bridge" and event == "question_answered"


def normalize_event(raw, source_file, session):
    if not isinstance(raw, dict):
        raise ValueError("event JSON is not an object")

    dt, epoch = parse_event_time(raw, source_file)
    event_type = str(raw.get("event") or raw.get("type") or "unknown").strip() or "unknown"

    event = dict(raw)
    event["schema_version"] = str(event.get("schema_version") or "event.v1")
    event["event"] = event_type
    event["event_type"] = event_type
    event["source"] = str(event.get("source") or "desktop-event-bridge")
    event["device"] = str(event.get("device") or "desktop")
    event["timestamp_epoch"] = epoch
    event["timestamp"] = dt.isoformat(timespec="seconds")
    event["date"] = dt.strftime("%Y-%m-%d")
    event["time"] = dt.strftime("%H:%M:%S")
    event["processed_at"] = now_iso()

    try:
        event["raw_file"] = str(source_file.relative_to(AI_DIR))
    except Exception:
        event["raw_file"] = str(source_file)

    if not event.get("event_id"):
        event["event_id"] = f"{event['device']}-{event_type}-{epoch}-{source_file.stem}"

    if isinstance(session, dict):
        for key in ["session_id", "mode", "task", "project"]:
            if key not in event and session.get(key):
                event[key] = session.get(key)

    return event


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
    if not file_is_stable(path):
        return "unstable", False, {"path": str(path)}

    raw = json.loads(path.read_text(encoding="utf-8"))

    if should_skip_raw_copy(raw):
        destination = move_to_dir(path, PROCESSED_DIR, prefix="skipped-")
        return "skipped", False, {
            "reason": "dialog-bridge question_answered copy already processed",
            "processed_path": str(destination),
        }

    session = read_json(CURRENT_SESSION_JSON, {})
    event = normalize_event(raw, path, session)

    event_path = EVENTS_DESKTOP_DIR / f"{event['date']}.jsonl"
    append_jsonl(event_path, event)

    if event.get("answer") or event.get("answer_label"):
        atomic_write_json(LAST_ANSWER_JSON, event)

    trigger = should_trigger_help_now(event)
    destination = move_to_dir(path, PROCESSED_DIR)

    return "processed", trigger, {
        "event_id": event.get("event_id"),
        "event": event.get("event"),
        "source": event.get("source"),
        "answer": event.get("answer", ""),
        "answer_label": event.get("answer_label", ""),
        "event_path": str(event_path),
        "processed_path": str(destination),
    }


def process_all():
    ensure_dirs()

    paths = sorted(
        [path for path in RAW_EVENTS_DIR.glob("*.json") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
    )

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

    paths = sorted(
        [path for path in RAW_EVENTS_DIR.glob("*.json") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
    )

    processed = []
    skipped = []
    failed = []
    unstable = []
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
            else:
                unstable.append(str(path))
                print(f"waiting for stable desktop event: {path.name}", flush=True)

        except Exception as error:
            try:
                destination = move_to_dir(path, FAILED_DIR)
            except Exception:
                destination = path

            failed.append({"path": str(destination), "error": str(error)})
            print(f"failed desktop event {path}: {error}", file=sys.stderr, flush=True)

    triggered = trigger_help_now() if needs_help_now else False

    status = "processed"
    if failed:
        status = "failed"
    elif not processed and not skipped:
        status = "waiting"

    write_status(
        status,
        f"processed={len(processed)} skipped={len(skipped)} failed={len(failed)} unstable={len(unstable)}",
        {
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "unstable": unstable,
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
