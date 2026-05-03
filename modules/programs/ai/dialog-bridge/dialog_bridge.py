#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()

NOTIFY_SEND = os.environ.get("NOTIFY_SEND", "notify-send")
TIMEOUT_BIN = os.environ.get("TIMEOUT_BIN", "timeout")
SYSTEMCTL = os.environ.get("SYSTEMCTL", "systemctl")

NOTIFICATION_TIMEOUT_SECONDS = int(os.environ.get("NOTIFICATION_TIMEOUT_SECONDS", "60"))
NOTIFICATION_COOLDOWN_SECONDS = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "600"))
MAX_QUESTION_AGE_SECONDS = int(os.environ.get("MAX_QUESTION_AGE_SECONDS", "14400"))
TRIGGER_PLANNER_ON_ANSWER = os.environ.get("TRIGGER_PLANNER_ON_ANSWER", "1") == "1"
TRIGGER_PLANNER_SERVICE = os.environ.get("TRIGGER_PLANNER_SERVICE", "llm-planner-help-now.service")

TIMEZONE = ZoneInfo(os.environ.get("DIALOG_BRIDGE_TIMEZONE", "Europe/Paris"))

STATE_LLM_DIR = AI_DIR / "state" / "llm"
STATE_DESKTOP_DIR = AI_DIR / "state" / "desktop"
OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"

PENDING_QUESTION_JSON = STATE_LLM_DIR / "pending-question.json"
CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"
LAST_ANSWER_JSON = STATE_LLM_DIR / "last-answer.json"
DIALOG_STATE_JSON = STATE_DESKTOP_DIR / "dialog-bridge-state.json"

QUESTION_ARCHIVE_DIR = STATE_LLM_DIR / "questions" / "archive"

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
        QUESTION_ARCHIVE_DIR,
        INBOX_FROM_DESKTOP_EVENTS,
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


def read_json(path: Path, default=None):
    if default is None:
        default = {}

    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"_error": str(error)}

    return default


def load_state():
    state = read_json(DIALOG_STATE_JSON, {})

    if not isinstance(state, dict):
        state = {}

    state.setdefault("questions", {})
    state.setdefault("last_seen_question_id", "")
    state.setdefault("last_answer", {})

    return state


def save_state(state):
    atomic_write_json(DIALOG_STATE_JSON, state)


def parse_created_at(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def question_age_seconds(question):
    created = parse_created_at(question.get("created_at"))
    if created is None:
        return 0

    return now().timestamp() - created.timestamp()


def question_is_expired(question):
    age = question_age_seconds(question)
    return age > MAX_QUESTION_AGE_SECONDS


def valid_question(question):
    if not isinstance(question, dict):
        return False, "question is not an object"

    if question.get("_error"):
        return False, f"read error: {question['_error']}"

    if not question.get("question_id"):
        return False, "missing question_id"

    if not question.get("question"):
        return False, "missing question text"

    options = question.get("answer_options", [])
    if not isinstance(options, list) or not options:
        return False, "missing answer options"

    return True, "ok"


def sanitize_action_id(value):
    value = str(value or "").strip().lower()
    cleaned = []

    for char in value:
        if char.isalnum() or char in ["_", "-"]:
            cleaned.append(char)
        elif char.isspace():
            cleaned.append("_")

    result = "".join(cleaned).strip("_")
    return result or "other"


def trim_options(options):
    cleaned = []
    seen = set()

    for opt in options:
        if not isinstance(opt, dict):
            continue

        opt_id = sanitize_action_id(opt.get("id"))
        label = str(opt.get("label", opt_id)).strip()

        if not opt_id or not label:
            continue

        if opt_id in seen:
            continue

        seen.add(opt_id)
        cleaned.append({"id": opt_id, "label": label[:40]})

    return cleaned[:3]


def write_current_question_inactive(reason="none"):
    atomic_write_text(
        CURRENT_QUESTION_MD,
        "\n".join([
            "# Current Question",
            "",
            "Status: inactive",
            f"Reason: {reason}",
            "Question: none",
            f"Updated: {now_iso()}",
            "",
        ]),
    )


def write_current_question_active(question, status="active"):
    lines = []
    lines.append("# Current Question")
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append(f"Question ID: {question.get('question_id', '')}")
    lines.append(f"Created: {question.get('created_at', '')}")
    lines.append("")
    lines.append(f"Question: {question.get('question', '')}")
    lines.append("")
    lines.append(f"Reason: {question.get('reason', '')}")
    lines.append("")
    lines.append("Options:")

    for opt in trim_options(question.get("answer_options", [])):
        lines.append(f"- `{opt['id']}` — {opt['label']}")

    lines.append("")
    lines.append(f"Free text allowed: {str(question.get('free_text_allowed', True)).lower()}")
    lines.append(f"Updated: {now_iso()}")
    lines.append("")

    atomic_write_text(CURRENT_QUESTION_MD, "\n".join(lines))


def archive_question(question, status, state=None, event=None, reason=""):
    question_id = question.get("question_id", f"unknown-{int(time.time())}")
    archive_day_dir = QUESTION_ARCHIVE_DIR / today()
    archive_day_dir.mkdir(parents=True, exist_ok=True)

    archive = {
        "question": question,
        "status": status,
        "archived_at": now_iso(),
        "reason": reason,
        "event": event or {},
        "dialog_state": (state or {}).get("questions", {}).get(question_id, {}),
    }

    archive_path = archive_day_dir / f"{question_id}.json"
    atomic_write_json(archive_path, archive)

    if PENDING_QUESTION_JSON.exists():
        current = read_json(PENDING_QUESTION_JSON, {})
        if current.get("question_id") == question_id:
            try:
                PENDING_QUESTION_JSON.unlink()
            except Exception:
                pass

    return archive_path


def mark_question_seen(state, question):
    question_id = question["question_id"]

    qstate = state["questions"].setdefault(question_id, {})
    qstate.setdefault("created_at", question.get("created_at", ""))
    qstate["question"] = question.get("question", "")
    qstate["last_seen_at"] = now_iso()
    qstate["status"] = qstate.get("status", "pending")

    state["last_seen_question_id"] = question_id

    save_state(state)


def mark_question_shown(state, question):
    question_id = question["question_id"]
    qstate = state["questions"].setdefault(question_id, {})

    now_epoch = time.time()

    qstate.setdefault("first_shown_at", now_iso())
    qstate["last_shown_at"] = now_iso()
    qstate["last_notified_epoch"] = now_epoch
    qstate["shown_count"] = int(qstate.get("shown_count", 0)) + 1
    qstate["status"] = "shown"

    state["last_shown_question_id"] = question_id

    save_state(state)


def mark_question_answered(state, question, event):
    question_id = question["question_id"]
    qstate = state["questions"].setdefault(question_id, {})

    qstate["answered_at"] = event.get("timestamp")
    qstate["answer"] = event.get("answer")
    qstate["answer_label"] = event.get("answer_label")
    qstate["status"] = "answered"

    state["last_answer"] = event
    state["last_answered_question_id"] = question_id

    save_state(state)


def should_show_question(state, question):
    question_id = question.get("question_id")
    qstate = state.get("questions", {}).get(question_id, {})

    if qstate.get("status") == "answered":
        return False, "already answered"

    if question_is_expired(question):
        return False, "expired"

    last_notified_epoch = float(qstate.get("last_notified_epoch", 0))
    if time.time() - last_notified_epoch < NOTIFICATION_COOLDOWN_SECONDS:
        return False, "cooldown active"

    return True, "ok"


def show_notification(question):
    options = trim_options(question.get("answer_options", []))
    if not options:
        return None

    body_lines = []
    body_lines.append(question.get("question", ""))

    reason = question.get("reason", "")
    if reason:
        body_lines.append("")
        body_lines.append(f"Reason: {reason}")

    if question.get("free_text_allowed"):
        body_lines.append("")
        body_lines.append("Desktop v0 supports buttons only; choose the closest option.")

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

    cmd.extend(["AI question", "\n".join(body_lines)])

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

    for line in completed.stdout.splitlines():
        line = line.strip()
        if line:
            return line

    return None


def answer_label(question, answer_id):
    answer_id = sanitize_action_id(answer_id)

    for opt in trim_options(question.get("answer_options", [])):
        if opt["id"] == answer_id:
            return opt["label"]

    return answer_id


def write_answer_event(question, answer_id):
    answer_id = sanitize_action_id(answer_id)
    label = answer_label(question, answer_id)
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
    atomic_write_json(raw_path, event)

    jsonl_path = EVENTS_DESKTOP_DIR / f"{today()}.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")

    atomic_write_json(LAST_ANSWER_JSON, event)

    return event


def trigger_planner():
    if not TRIGGER_PLANNER_ON_ANSWER:
        return

    try:
        subprocess.run(
            [
                SYSTEMCTL,
                "--user",
                "start",
                "--no-block",
                TRIGGER_PLANNER_SERVICE,
            ],
            check=False,
        )
    except Exception as error:
        print(f"failed to trigger planner: {error}", file=sys.stderr, flush=True)


def handle_no_pending():
    write_current_question_inactive("no pending question")
    print("no pending question", flush=True)


def run_once():
    ensure_dirs()

    state = load_state()
    question = read_json(PENDING_QUESTION_JSON, {})

    if not question:
        handle_no_pending()
        return

    ok, reason = valid_question(question)
    if not ok:
        print(f"invalid pending question: {reason}", flush=True)
        write_current_question_inactive(f"invalid pending question: {reason}")
        return

    mark_question_seen(state, question)
    write_current_question_active(question, status="active")

    if question_is_expired(question):
        archive_question(question, "expired", state=state, reason="question expired")
        write_current_question_inactive("question expired")
        print("question expired and archived", flush=True)
        return

    show, reason = should_show_question(state, question)
    if not show:
        print(f"no dialog shown: {reason}", flush=True)
        return

    mark_question_shown(state, question)

    answer_id = show_notification(question)
    if not answer_id:
        print("no answer selected", flush=True)
        return

    event = write_answer_event(question, answer_id)
    mark_question_answered(state, question, event)

    archive_path = archive_question(question, "answered", state=state, event=event)
    write_current_question_inactive(f"answered: {event.get('answer_label', event.get('answer'))}")

    print(
        f"answered question {question.get('question_id')} with {event.get('answer')}; archived={archive_path}",
        flush=True,
    )

    trigger_planner()


def main():
    try:
        run_once()
    except Exception as error:
        print(f"dialog-bridge failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
