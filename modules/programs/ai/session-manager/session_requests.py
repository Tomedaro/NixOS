#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
AI_SESSION_BIN = os.environ.get("AI_SESSION_BIN", "ai-session")
STABILITY_SECONDS = int(os.environ.get("SESSION_REQUEST_STABILITY_SECONDS", "2"))
TIMEZONE = ZoneInfo(os.environ.get("AI_SESSION_TIMEZONE", "Europe/Paris"))

REQUEST_DIR = AI_DIR / "inbox" / "session-requests"
PROCESSED_DIR = AI_DIR / "inbox" / "session-requests-processed"
FAILED_DIR = AI_DIR / "inbox" / "session-requests-failed"
TEMPLATES_DIR = AI_DIR / "templates" / "session-requests"
STATE_DIR = AI_DIR / "state" / "session"
EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"

STATUS_JSON = STATE_DIR / "request-bridge-status.json"
STATUS_MD = STATE_DIR / "request-bridge-status.md"


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in [
        REQUEST_DIR,
        PROCESSED_DIR,
        FAILED_DIR,
        TEMPLATES_DIR,
        STATE_DIR,
        EVENTS_DESKTOP_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def append_jsonl(path: Path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def write_status(status, message="", request_path="", result=None):
    data = {
        "updated_at": now_iso(),
        "status": status,
        "message": message,
        "request_path": request_path,
        "result": result or {},
    }

    atomic_write_json(STATUS_JSON, data)

    lines = []
    lines.append("# Session Request Bridge Status")
    lines.append("")
    lines.append(f"Updated: {data['updated_at']}")
    lines.append(f"Status: `{status}`")
    lines.append(f"Message: {message}")
    if request_path:
        lines.append(f"Request: `{request_path}`")
    lines.append("")

    if result:
        lines.append("## Result")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    atomic_write_text(STATUS_MD, "\n".join(lines))


def event(kind, payload):
    data = {
        "source": "session-request-bridge",
        "device": "desktop",
        "event": kind,
        "timestamp": now_iso(),
        "timestamp_epoch": int(time.time()),
        "date": today(),
        "time": now().strftime("%H:%M:%S"),
    }
    data.update(payload)
    append_jsonl(EVENTS_DESKTOP_DIR / f"{today()}.jsonl", data)


def is_stable(path: Path):
    age = time.time() - path.stat().st_mtime
    return age >= STABILITY_SECONDS


def read_request(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]

    if isinstance(value, str):
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        if value.strip():
            return [value.strip()]

    return []


def add_optional(args, flag, value):
    if value is None:
        return

    if isinstance(value, str) and not value.strip():
        return

    args.extend([flag, str(value)])


def build_start_args(request):
    task = request.get("task") or request.get("title")
    if not task:
        raise ValueError("start request requires 'task' or 'title'")

    mode = request.get("mode", "study")

    args = [
        AI_SESSION_BIN,
        "start",
        "--task",
        str(task),
        "--mode",
        str(mode),
        "--source",
        str(request.get("source", "request-file")),
    ]

    add_optional(args, "--project", request.get("project"))
    add_optional(args, "--duration", request.get("duration", request.get("duration_minutes")))
    add_optional(args, "--strictness", request.get("strictness"))
    add_optional(args, "--language-level", request.get("language_level", request.get("languageLevel")))
    add_optional(args, "--proof", request.get("proof"))

    repeated_flags = [
        ("allow_app", "--allow-app"),
        ("distract_app", "--distract-app"),
        ("allow_domain", "--allow-domain"),
        ("distract_domain", "--distract-domain"),
        ("allow_title", "--allow-title"),
        ("distract_title", "--distract-title"),
    ]

    for key, flag in repeated_flags:
        for item in as_list(request.get(key)):
            args.extend([flag, item])

    return args


def build_end_args(request):
    args = [
        AI_SESSION_BIN,
        "end",
        "--status",
        str(request.get("status", "completed")),
    ]

    add_optional(args, "--reason", request.get("reason"))

    return args


def build_status_args(_request):
    return [AI_SESSION_BIN, "status"]


def command_args(request):
    command = str(request.get("command", "start")).strip().lower()

    if command == "start":
        return command, build_start_args(request)

    if command == "end":
        return command, build_end_args(request)

    if command == "status":
        return command, build_status_args(request)

    raise ValueError(f"unknown session request command: {command}")


def safe_destination(directory: Path, original: Path):
    stamp = now().strftime("%Y%m%d-%H%M%S")
    stem = original.stem
    suffix = original.suffix or ".json"

    candidate = directory / f"{stamp}-{stem}{suffix}"
    counter = 1

    while candidate.exists():
        candidate = directory / f"{stamp}-{stem}-{counter}{suffix}"
        counter += 1

    return candidate


def move_request(path: Path, directory: Path):
    destination = safe_destination(directory, path)
    shutil.move(str(path), str(destination))
    return destination


def process_request(path: Path):
    request = read_request(path)
    command, args = command_args(request)

    completed = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    result = {
        "command": command,
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

    if completed.returncode != 0:
        raise RuntimeError(json.dumps(result, indent=2, ensure_ascii=False))

    destination = move_request(path, PROCESSED_DIR)

    write_status(
        "processed",
        f"processed {command} request",
        str(destination),
        result,
    )

    event(
        "session_request_processed",
        {
            "command": command,
            "request": request,
            "processed_path": str(destination),
            "result": result,
        },
    )

    return result


def newest_unstable_wait_seconds(requests):
    wait_for = 0.0

    for path in requests:
        try:
            age = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            continue

        remaining = STABILITY_SECONDS - age
        if remaining > wait_for:
            wait_for = remaining

    return max(0.0, wait_for)


def process_all():
    ensure_dirs()
    create_templates()

    requests = sorted(REQUEST_DIR.glob("*.json"))

    if not requests:
        write_status("idle", "no pending session requests")
        print("no pending session requests")
        return

    wait_for = newest_unstable_wait_seconds(requests)
    if wait_for > 0:
        sleep_for = wait_for + 0.25
        write_status("waiting", f"waiting {sleep_for:.2f}s for request stability")
        print(f"waiting {sleep_for:.2f}s for request stability", flush=True)
        time.sleep(sleep_for)

    requests = sorted(REQUEST_DIR.glob("*.json"))

    processed = 0
    failed = 0

    for path in requests:
        try:
            result = process_request(path)
            processed += 1
            print(f"processed {path}: {result['command']}")
        except Exception as error:
            failed += 1
            try:
                destination = move_request(path, FAILED_DIR)
            except Exception:
                destination = path

            write_status(
                "failed",
                str(error),
                str(destination),
                {"error": str(error)},
            )

            event(
                "session_request_failed",
                {
                    "request_path": str(destination),
                    "error": str(error),
                },
            )

            print(f"failed {path}: {error}", file=sys.stderr)

    if processed == 0 and failed == 0:
        write_status("idle", "no processable session requests")


def create_templates():
    templates = {
        "start-anki.json": {
            "command": "start",
            "source": "obsidian-template",
            "task": "Anki Language recovery",
            "project": "Anki Recovery",
            "mode": "anki",
            "duration": 25,
            "strictness": 2,
            "language_level": 1
        },
        "start-coding.json": {
            "command": "start",
            "source": "obsidian-template",
            "task": "Work on NixOS AI module",
            "project": "NixOS AI setup",
            "mode": "coding",
            "duration": 45,
            "strictness": 2,
            "language_level": 1
        },
        "start-learning-video.json": {
            "command": "start",
            "source": "obsidian-template",
            "task": "Watch learning video and write reflection",
            "project": "Learning",
            "mode": "learning-video",
            "duration": 30,
            "strictness": 1,
            "language_level": 2,
            "allow_domain": ["youtube.com", "youtu.be"],
            "distract_domain": ["youtube.com/shorts"]
        },
        "end-completed.json": {
            "command": "end",
            "source": "obsidian-template",
            "status": "completed",
            "reason": "Ended from request file"
        },
        "end-paused.json": {
            "command": "end",
            "source": "obsidian-template",
            "status": "paused",
            "reason": "Paused from request file"
        }
    }

    for filename, data in templates.items():
        path = TEMPLATES_DIR / filename
        if not path.exists():
            atomic_write_json(path, data)

    readme = REQUEST_DIR / "README.md"
    if not readme.exists():
        atomic_write_text(
            readme,
            "\n".join([
                "# Session Requests",
                "",
                "Drop a JSON file here to start/end a session.",
                "",
                "Examples live in:",
                "",
                f"`{TEMPLATES_DIR}`",
                "",
                "A request is processed by `ai-session-requests.service`.",
                "",
                "Example start request:",
                "",
                "```json",
                json.dumps(templates["start-anki.json"], indent=2, ensure_ascii=False),
                "```",
                "",
            ]),
        )


def main():
    try:
        process_all()
    except Exception as error:
        write_status("crashed", str(error))
        print(f"ai-session-requests failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
