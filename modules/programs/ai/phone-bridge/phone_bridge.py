#!/usr/bin/env python3

import json
import re
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


RAW_EVENT_FILENAME_RE = re.compile(
    r"^(?:[0-9]{10,13}|[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2})_[A-Za-z0-9][A-Za-z0-9_-]*[.]json$"
)
TASKER_LITERAL_RE = re.compile(r"%[A-Za-z0-9_]+")


APP_POLICY_TEMPLATE = """# App Policy

Phone protocol:

- Intentional commands/check-ins go to `AI/inbox/actions/*.json`.
- Passive phone telemetry goes to `AI/inbox/from-phone/events/*.json`.

The phone bridge processes passive telemetry only.
The action bridge processes intentional commands.
"""


DOMAIN_POLICY_TEMPLATE = """# Domain Policy

Browser app = neutral.
Domain and current task decide whether it is productive.
"""


PROOF_POLICY_TEMPLATE = """# Proof Policy

Proof files should be request-ID based.

Preferred proof folder:

`AI/proofs/phone/YYYY-MM-DD/<proof-id>/`

For Anki, prefer objective Anki progress proof over photos when possible.
"""


RETENTION_POLICY_TEMPLATE = """# Retention Policy

Telemetry lifecycle:

1. Tasker writes passive telemetry into `AI/inbox/from-phone/events/`.
2. phone-bridge validates it.
3. phone-bridge appends it to `AI/events/phone/YYYY-MM-DD.jsonl`.
4. phone-bridge moves the raw file to `processed/YYYY-MM-DD/`.

Command lifecycle:

1. Tasker writes intentional commands into `AI/inbox/actions/`.
2. ai-action-bridge validates and executes them.
3. ai-action-bridge moves the raw action to `actions-processed/YYYY-MM-DD/`.

Strict rule:

Action-shaped files in `from-phone/events` are treated as misrouted errors.
"""


PROOF_REQUEST_TEMPLATE = """# Current Proof Request

Status: inactive
Proof ID:
Task:
Request:
Deadline:
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


def raw_is_action(raw):
    if not isinstance(raw, dict):
        return False

    schema = str(raw.get("schema_version", "")).strip().lower()

    return (
        schema.startswith("action.")
        or bool(str(raw.get("action", "")).strip())
        or bool(str(raw.get("command", "")).strip())
    )



def _safe_text(value):
    return str(value if value is not None else "").strip()


def _has_tasker_literal(value):
    return bool(TASKER_LITERAL_RE.search(_safe_text(value)))


def validate_raw_event_contract(raw, source_file):
    """Reject malformed Tasker phone telemetry before normalization.

    During development, do not preserve compatibility with broken Tasker
    exports. Bad raw files belong in from-phone/failed, not events/phone.
    """

    if not isinstance(raw, dict):
        raise ValueError("raw phone event must be a JSON object")

    filename = source_file.name

    if _has_tasker_literal(filename):
        raise ValueError("unexpanded Tasker variable in phone event filename")

    if not RAW_EVENT_FILENAME_RE.match(filename):
        raise ValueError(
            "invalid phone event filename: expected '<epoch>_<event>.json' or 'YYYY-MM-DDTHH-MM-SS_<event>.json'"
        )

    event_name = _safe_text(raw.get("event") or raw.get("event_type"))
    if not event_name:
        raise ValueError("missing phone event name")

    if _has_tasker_literal(event_name):
        raise ValueError("unexpanded Tasker variable in phone event name")

    timestamp_epoch = raw.get("timestamp_epoch")
    if timestamp_epoch is None:
        raise ValueError("missing timestamp_epoch")

    if _has_tasker_literal(timestamp_epoch):
        raise ValueError("unexpanded Tasker variable in timestamp_epoch")

    try:
        epoch = int(float(_safe_text(timestamp_epoch)))
    except Exception as error:
        raise ValueError("invalid timestamp_epoch") from error

    if epoch <= 0:
        raise ValueError("timestamp_epoch must be positive")

def normalize_phone_event(raw, source_file):
    validate_raw_event_contract(raw, source_file)

    if raw_is_action(raw):
        raise ValueError(
            "misrouted action file: phone commands/check-ins must be written to AI/inbox/actions, not AI/inbox/from-phone/events"
        )

    event = normalize_event(
        raw,
        source_file=source_file,
        ai_dir=AI_DIR,
        tz=TIMEZONE,
        default_source="tasker",
        default_device="phone",
        session=None,
    )

    event.setdefault("message", "")
    return event


def append_markdown_log(event):
    path = PHONE_LOGS_DIR / f"{event['date']}.md"

    if not path.exists():
        atomic_write_text(path, f"# Phone Log - {event['date']}\n\n")

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
    atomic_write_json(LATEST_JSON, event)

    lines = [
        "# Latest Phone Event",
        "",
        f"Last updated: {now_iso(TIMEZONE)}",
        f"Event: `{event.get('event', '')}`",
        f"Time: {event.get('timestamp', '')}",
        f"Device: {event.get('device', '')}",
        f"Message: {event.get('message', '')}",
    ]

    if event.get("proof_id"):
        lines.append(f"Proof ID: `{event.get('proof_id')}`")

    if event.get("file"):
        lines.append(f"File: `{event.get('file')}`")

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
