#!/usr/bin/env python3

import json
import os
import sys
import time
from pathlib import Path

from ai_system.events import append_event, normalize_event
from ai_system.io_utils import atomic_write_json, atomic_write_text
from ai_system.queue import is_stable, move_unique
from ai_system.time_utils import get_timezone, now_iso, today


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
STABILITY_SECONDS = int(os.environ.get("STABILITY_SECONDS", "10"))
PROCESSED_RETENTION_DAYS = int(os.environ.get("PROCESSED_RETENTION_DAYS", "14"))
CREATE_TEMPLATES = os.environ.get("CREATE_TEMPLATES", "1") == "1"
TIMEZONE = get_timezone(os.environ.get("PHONE_BRIDGE_TIMEZONE", "Europe/Paris"))

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

AI/proofs/phone/YYYY-MM-DD/<proof-id>/

Expected files:

- proof.jpg or proof.png
- metadata.json

Expected event shape:

{
  "source": "tasker",
  "event": "proof_submitted",
  "proof_id": "anki-2026-04-30-1215",
  "file": "AI/proofs/phone/2026-04-30/anki-2026-04-30-1215/proof.jpg",
  "timestamp_epoch": "1714470000"
}

For Anki, prefer objective Anki progress proof over photos when possible.
"""


RETENTION_POLICY_TEMPLATE = """# Retention Policy

Raw phone events are temporary queue files.

Recommended lifecycle:

1. Tasker writes one raw event file into AI/inbox/from-phone/events/.
2. phone-bridge validates it.
3. phone-bridge appends it to AI/events/phone/YYYY-MM-DD.jsonl.
4. phone-bridge appends a readable line to AI/logs/phone/YYYY-MM-DD.md.
5. phone-bridge moves the raw file to processed/YYYY-MM-DD/.
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
        atomic_write_text(path, text.strip() + "\n")


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


def normalize_phone_event(raw, source_file):
    event = normalize_event(
        raw,
        source_file=source_file,
        ai_dir=AI_DIR,
        tz=TIMEZONE,
        default_source="tasker",
        default_device="phone",
        session=None,
    )

    if "message" not in event:
        event["message"] = ""

    return event


def append_markdown_log(event):
    path = PHONE_LOGS_DIR / f"{event['date']}.md"

    if not path.exists():
        atomic_write_text(path, f"# Phone Log - {event['date']}\n\n")

    message = event.get("message", "")
    proof_id = event.get("proof_id", "")
    file_ref = event.get("file", "")

    line = f"- {event['time']} - `{event['event']}`"

    if message:
        line += f" - {message}"

    if proof_id:
        line += f" - proof: `{proof_id}`"

    if file_ref:
        line += f" - file: `{file_ref}`"

    line += "\n"

    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def write_latest(event):
    atomic_write_json(LATEST_JSON, event)

    event_name = event.get("event", "")
    event_time = event.get("timestamp", "")
    device = event.get("device", "")
    message = event.get("message", "")
    proof_id = event.get("proof_id", "")
    file_ref = event.get("file", "")

    lines = [
        "# Latest Phone Event",
        "",
        f"Last updated: {now_iso(TIMEZONE)}",
        f"Event: `{event_name}`",
        f"Time: {event_time}",
        f"Device: {device}",
        f"Message: {message}",
    ]

    if proof_id:
        lines.append(f"Proof ID: `{proof_id}`")

    if file_ref:
        lines.append(f"File: `{file_ref}`")

    lines.append("")

    atomic_write_text(LATEST_MD, "\n".join(lines))


def move_to_processed(source_file, event):
    return move_unique(source_file, PROCESSED_DIR / event["date"])


def move_to_failed(source_file, reason):
    date_dir = FAILED_DIR / today(TIMEZONE)

    try:
        destination = move_unique(source_file, date_dir)
        atomic_write_text(destination.with_suffix(destination.suffix + ".error.txt"), str(reason) + "\n")
        return destination
    except Exception as error:
        print(f"failed to move bad event {source_file}: {error}", file=sys.stderr, flush=True)
        return source_file


def process_event_file(path):
    if not is_stable(path, STABILITY_SECONDS):
        return False

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        event = normalize_phone_event(raw, path)
        append_event(PHONE_EVENTS_DIR, event)
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

    for path in sorted(PROCESSED_DIR.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def pending_event_files():
    return sorted(
        [path for path in RAW_EVENTS_DIR.glob("*.json") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def tick():
    ensure_dirs()
    ensure_templates()

    processed_count = 0

    for path in pending_event_files():
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
