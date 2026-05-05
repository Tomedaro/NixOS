#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from ai_system.recovery_targets import get_recovery_target


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TASKNOTES_DIR = Path(os.environ.get("TASKNOTES_DIR", "/home/daniil/Sync/Perseverance.Gu/TaskNotes")).expanduser()
AI_SESSION_BIN = os.environ.get("AI_SESSION_BIN", "/run/current-system/sw/bin/ai-session")
SYSTEMCTL = os.environ.get("SYSTEMCTL", "systemctl")

STABILITY_SECONDS = int(os.environ.get("ACTION_STABILITY_SECONDS", "2"))
AUTHORITY_LEVEL = int(os.environ.get("ACTION_AUTHORITY_LEVEL", "2"))
TRIGGER_HELP_NOW = os.environ.get("TRIGGER_HELP_NOW", "1") == "1"
TRIGGER_HELP_NOW_SERVICE = os.environ.get("TRIGGER_HELP_NOW_SERVICE", "llm-planner-help-now.service")

TIMEZONE = ZoneInfo(os.environ.get("ACTION_BRIDGE_TIMEZONE", "Europe/Paris"))

INBOX_DIR = AI_DIR / "inbox" / "actions"
PROCESSED_DIR = AI_DIR / "inbox" / "actions-processed"
FAILED_DIR = AI_DIR / "inbox" / "actions-failed"

STATE_DIR = AI_DIR / "state" / "action-bridge"
STATE_LLM_DIR = AI_DIR / "state" / "llm"
STATE_SESSION_DIR = AI_DIR / "state" / "session"

EVENTS_ACTIONS_DIR = AI_DIR / "events" / "actions"
EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"
EVENTS_PHONE_DIR = AI_DIR / "events" / "phone"
EVENTS_TASKNOTES_DIR = AI_DIR / "events" / "tasknotes"
EVENTS_PROOFS_DIR = AI_DIR / "events" / "proofs"

TEMPLATES_DIR = AI_DIR / "templates" / "actions"
SCHEMAS_DIR = AI_DIR / "schemas"
PROOFS_DIR = AI_DIR / "proofs"

RECOVERY_STATE_DIR = AI_DIR / "state" / "recovery"
RECOVERY_CURRENT_JSON = RECOVERY_STATE_DIR / "current.json"
RECOVERY_STATUS_MD = RECOVERY_STATE_DIR / "status.md"
EVENTS_RECOVERY_DIR = AI_DIR / "events" / "recovery"

STATUS_JSON = STATE_DIR / "status.json"
STATUS_MD = STATE_DIR / "status.md"
LAST_ANSWER_JSON = STATE_LLM_DIR / "last-answer.json"
PENDING_QUESTION_JSON = STATE_LLM_DIR / "pending-question.json"
CURRENT_SESSION_JSON = STATE_SESSION_DIR / "current.json"

OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"
CURRENT_NUDGE_JSON = OUTBOX_TO_PHONE_DIR / "current-nudge.json"
CURRENT_NUDGE_MD = OUTBOX_TO_PHONE_DIR / "current-nudge.md"
CURRENT_QUESTION_JSON = OUTBOX_TO_PHONE_DIR / "current-question.json"
CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"
INTERACTION_STATE_JSON = OUTBOX_TO_PHONE_DIR / "interaction-state.json"


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in [
        INBOX_DIR,
        PROCESSED_DIR,
        FAILED_DIR,
        STATE_DIR,
        STATE_LLM_DIR,
        STATE_SESSION_DIR,
        OUTBOX_TO_PHONE_DIR,
        EVENTS_ACTIONS_DIR,
        EVENTS_DESKTOP_DIR,
        EVENTS_PHONE_DIR,
        EVENTS_TASKNOTES_DIR,
        EVENTS_PROOFS_DIR,
        EVENTS_RECOVERY_DIR,
        RECOVERY_STATE_DIR,
        TEMPLATES_DIR,
        SCHEMAS_DIR,
        PROOFS_DIR,
        TASKNOTES_DIR,
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
            return json.loads(path.read_text(encoding="utf-8"))
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
        "# Action Bridge Status",
        "",
        f"Updated: {data['updated_at']}",
        f"Status: `{status}`",
        f"Message: {message}",
        "",
        "## Details",
        "",
        "```json",
        json.dumps(details, indent=2, ensure_ascii=False),
        "```",
        "",
    ]

    atomic_write_text(STATUS_MD, "\n".join(lines))


def is_stable(path):
    try:
        age = time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return False

    return age >= STABILITY_SECONDS


def move_unique(source, directory, prefix=""):
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{prefix}{source.name}"

    if not candidate.exists():
        shutil.move(str(source), str(candidate))
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    for index in range(1, 10000):
        alt = directory / f"{stem}-{index}{suffix}"
        if not alt.exists():
            shutil.move(str(source), str(alt))
            return alt

    raise RuntimeError(f"could not find unique destination for {source}")


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


def get_action_name(action):
    return str(action.get("action") or action.get("command") or "").strip().lower()


def slugify(value, fallback="item"):
    text = str(value or "").strip().lower()
    out = []
    dash = False

    for char in text:
        if char.isalnum() or char in ["_", "-"]:
            out.append(char)
            dash = False
        elif char.isspace() or char in [".", "/", ":"]:
            if not dash:
                out.append("-")
                dash = True

    result = "".join(out).strip("-")
    return result[:80] or fallback


def action_id_for(path, action):
    existing = str(action.get("action_id", "")).strip()
    if existing:
        return existing

    action_name = get_action_name(action) or "unknown"
    epoch = int(time.time())
    return f"action-{action_name}-{epoch}-{path.stem}"


def load_current_session():
    session = read_json(CURRENT_SESSION_JSON, {})
    if not isinstance(session, dict):
        return {}
    return session


def session_is_active(session):
    if not isinstance(session, dict):
        return False
    return str(session.get("status", "")).strip().lower() == "active"


def base_event(action, path, action_id):
    action_name = get_action_name(action)
    source = str(action.get("source", "action-bridge"))
    device = str(action.get("device", "desktop"))
    epoch = int(action.get("timestamp_epoch") or path.stat().st_mtime or time.time())
    dt = datetime.fromtimestamp(epoch, tz=TIMEZONE)

    event = dict(action)
    event["schema_version"] = "event.v1"
    event["event"] = action_name
    event["event_type"] = action_name
    event["action_id"] = action_id
    event["source"] = source
    event["device"] = device
    event["timestamp_epoch"] = epoch
    event["timestamp"] = str(action.get("timestamp") or action.get("created_at") or dt.isoformat(timespec="seconds"))
    event["date"] = str(action.get("date") or dt.strftime("%Y-%m-%d"))
    event["time"] = str(action.get("time") or dt.strftime("%H:%M:%S"))
    event["processed_at"] = now_iso()

    try:
        event["raw_file"] = str(path.relative_to(AI_DIR))
    except Exception:
        event["raw_file"] = str(path)

    session = load_current_session()
    if session_is_active(session):
        event.setdefault("session_id", session.get("session_id", ""))
        event.setdefault("mode", session.get("mode", ""))
        event.setdefault("task", session.get("task", ""))
        event.setdefault("project", session.get("project", ""))
    elif session:
        event.setdefault("inactive_session_id", session.get("session_id", ""))
        event.setdefault("inactive_session_status", session.get("status", ""))

    return event


def append_action_event(event):
    append_jsonl(EVENTS_ACTIONS_DIR / f"{today()}.jsonl", event)

    if event.get("device") == "phone":
        append_jsonl(EVENTS_PHONE_DIR / f"{today()}.jsonl", event)
    else:
        append_jsonl(EVENTS_DESKTOP_DIR / f"{today()}.jsonl", event)


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


def run_command(args):
    completed = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    result = {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

    if completed.returncode != 0:
        raise RuntimeError(json.dumps(result, indent=2, ensure_ascii=False))

    return result


def handle_start_session(action):
    task = action.get("task") or action.get("title")
    if not task:
        raise ValueError("start_session requires task or title")

    args = [
        AI_SESSION_BIN,
        "start",
        "--task",
        str(task),
        "--mode",
        str(action.get("mode", "study")),
        "--source",
        str(action.get("source", "action-bridge")),
    ]

    add_optional(args, "--project", action.get("project"))
    add_optional(args, "--duration", action.get("duration", action.get("duration_minutes")))
    add_optional(args, "--strictness", action.get("strictness"))
    add_optional(args, "--language-level", action.get("language_level", action.get("languageLevel")))
    add_optional(args, "--proof", action.get("proof"))

    repeated_flags = [
        ("allow_app", "--allow-app"),
        ("distract_app", "--distract-app"),
        ("allow_domain", "--allow-domain"),
        ("distract_domain", "--distract-domain"),
        ("allow_title", "--allow-title"),
        ("distract_title", "--distract-title"),
    ]

    for key, flag in repeated_flags:
        for item in as_list(action.get(key)):
            args.extend([flag, item])

    return run_command(args)


def handle_end_session(action):
    args = [
        AI_SESSION_BIN,
        "end",
        "--status",
        str(action.get("status", "completed")),
    ]

    add_optional(args, "--reason", action.get("reason"))

    return run_command(args)


def handle_check_in(action, path, action_id):
    event = base_event(action, path, action_id)
    event["event"] = "check_in"
    event["event_type"] = "check_in"
    event["answer"] = str(action.get("answer", "")).strip()
    event["answer_label"] = str(action.get("answer_label") or action.get("label") or event.get("answer", "")).strip()
    event["free_text"] = str(action.get("free_text") or action.get("note") or "")

    atomic_write_json(LAST_ANSWER_JSON, event)
    append_action_event(event)

    return {
        "event": event,
        "triggered_help_now": trigger_help_now(),
    }


def title_from_markdown(text, fallback):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def priority_from_text(text):
    lower = text.lower()
    if "priority: **urgent**" in lower or "priority: urgent" in lower:
        return "urgent"
    if "priority: **high**" in lower or "priority: high" in lower:
        return "high"
    if "priority: **medium**" in lower or "priority: medium" in lower:
        return "medium"
    return "normal"


def ensure_tasknotes_target(target):
    base = TASKNOTES_DIR.resolve()
    parent = target.parent.resolve()

    if not str(parent).startswith(str(base)):
        raise ValueError(f"target must be inside TaskNotes directory: {target}")


def target_for_proposal(action, proposal_name):
    explicit = str(action.get("target") or action.get("target_path") or "").strip()

    if explicit:
        target = Path(explicit)
        if not target.is_absolute():
            target = TASKNOTES_DIR / target
        return target

    if proposal_name == "anki-recovery":
        return TASKNOTES_DIR / "AI" / "anki-due-recovery.md"

    return TASKNOTES_DIR / "AI" / f"{proposal_name}.md"


def handle_promote_task_proposal(action, path, action_id):
    if AUTHORITY_LEVEL < 2:
        raise PermissionError("promote_task_proposal requires ACTION_AUTHORITY_LEVEL >= 2")

    proposal_name = slugify(action.get("proposal") or action.get("proposal_id") or "anki-recovery", "proposal")
    proposal_path = AI_DIR / "proposed-tasks" / f"{proposal_name}.md"

    if not proposal_path.exists():
        raise FileNotFoundError(f"proposal not found: {proposal_path}")

    proposal_text = proposal_path.read_text(encoding="utf-8")
    target = target_for_proposal(action, proposal_name)
    ensure_tasknotes_target(target)

    overwrite = bool(action.get("overwrite", False))

    if target.exists() and not overwrite:
        raise FileExistsError(f"target exists and overwrite is false: {target}")

    title = str(action.get("title") or title_from_markdown(proposal_text, proposal_name.replace("-", " ").title()))
    priority = str(action.get("priority") or priority_from_text(proposal_text))
    status = str(action.get("status", "todo"))
    project = str(action.get("project", "Anki Recovery" if proposal_name == "anki-recovery" else "AI Proposals"))
    scheduled = str(action.get("scheduled", today()))

    body = []
    body.append("---")
    body.append("tags:")
    body.append("  - task")
    body.append("  - ai")
    body.append("  - promoted")
    body.append(f'title: "{title}"')
    body.append(f"status: {status}")
    body.append(f"priority: {priority}")
    body.append(f"scheduled: {scheduled}")
    body.append("contexts:")
    body.append('  - "@computer"')
    body.append("projects:")
    body.append(f'  - "[[{project}]]"')
    body.append("---")
    body.append("")
    body.append(f"# {title}")
    body.append("")
    body.append(f"> Promoted from `{proposal_path.relative_to(AI_DIR)}` by action `{action_id}`.")
    body.append("")
    body.append(proposal_text)

    atomic_write_text(target, "\n".join(body))

    event = base_event(action, path, action_id)
    event["event"] = "task_proposal_promoted"
    event["event_type"] = "task_proposal_promoted"
    event["proposal"] = proposal_name
    event["proposal_path"] = str(proposal_path)
    event["target_path"] = str(target)
    event["overwrite"] = overwrite
    event["authority_level"] = AUTHORITY_LEVEL

    append_jsonl(EVENTS_TASKNOTES_DIR / f"{today()}.jsonl", event)
    append_jsonl(EVENTS_ACTIONS_DIR / f"{today()}.jsonl", event)

    return {
        "proposal": proposal_name,
        "proposal_path": str(proposal_path),
        "target_path": str(target),
        "event": event,
    }


def handle_submit_proof(action, path, action_id):
    if AUTHORITY_LEVEL < 1:
        raise PermissionError("submit_proof requires ACTION_AUTHORITY_LEVEL >= 1")

    proof_id = slugify(action.get("proof_id") or action_id, "proof")
    proof_day_dir = PROOFS_DIR / today() / proof_id
    proof_day_dir.mkdir(parents=True, exist_ok=True)

    event = base_event(action, path, action_id)
    event["event"] = "proof_submitted"
    event["event_type"] = "proof_submitted"
    event["proof_id"] = proof_id
    event["proof_dir"] = str(proof_day_dir)

    atomic_write_json(proof_day_dir / "metadata.json", event)
    append_jsonl(EVENTS_PROOFS_DIR / f"{today()}.jsonl", event)
    append_jsonl(EVENTS_ACTIONS_DIR / f"{today()}.jsonl", event)

    return {
        "proof_id": proof_id,
        "proof_dir": str(proof_day_dir),
        "event": event,
    }



def compact_question(payload):
    if not isinstance(payload, dict) or payload.get("status") != "active":
        return None

    return {
        "question_id": payload.get("question_id", ""),
        "status": payload.get("status", "active"),
        "question": payload.get("question", ""),
        "answer_options": payload.get("answer_options", []),
        "free_text_allowed": payload.get("free_text_allowed", True),
        "response_action": payload.get("response_action", "answer_question"),
        "dismiss_action": payload.get("dismiss_action", "dismiss_question"),
    }


def compact_nudge(payload):
    if not isinstance(payload, dict) or payload.get("status") != "active":
        return None

    return {
        "nudge_id": payload.get("nudge_id", ""),
        "status": payload.get("status", "active"),
        "urgency": payload.get("urgency", "normal"),
        "message": payload.get("message", ""),
        "recommended_next_action": payload.get("recommended_next_action", ""),
        "actions": payload.get("actions", []),
    }



def intervention_id_from_action_or_nudge(action, current_nudge):
    values = [
        action.get("intervention_id"),
        action.get("intervention"),
        current_nudge.get("intervention_id"),
        current_nudge.get("intervention"),
    ]

    for value in values:
        if isinstance(value, dict):
            value = value.get("intervention_id")
        text = str(value or "").strip()
        if text:
            return text

    return ""


def attach_intervention_ref(event, action, current_nudge, *, kind="recovery_nudge"):
    intervention_id = intervention_id_from_action_or_nudge(action, current_nudge)

    if intervention_id:
        event["intervention_id"] = intervention_id
        event["intervention_kind"] = str(
            action.get("intervention_kind")
            or current_nudge.get("intervention_kind")
            or kind
        )

    return intervention_id


def write_interaction_state_from_current(
    *,
    source="action-bridge",
    last_question_response=None,
    last_nudge_ack=None,
    last_nudge_snooze=None,
):
    nudge = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(nudge, dict):
        nudge = {}

    question = read_json(CURRENT_QUESTION_JSON, {})
    if not isinstance(question, dict):
        question = {}

    existing = read_json(INTERACTION_STATE_JSON, {})
    if not isinstance(existing, dict):
        existing = {}

    state = {
        "schema_version": "phone_interaction_state.v1",
        "updated_at": now_iso(),
        "source": source,
        "planner_mode": question.get("planner_mode") or nudge.get("planner_mode") or existing.get("planner_mode", "unknown"),
        "active_nudge": compact_nudge(nudge),
        "active_question": compact_question(question),
    }

    if last_question_response is not None:
        state["last_question_response"] = last_question_response
    elif existing.get("last_question_response") is not None:
        state["last_question_response"] = existing.get("last_question_response")

    if last_nudge_ack is not None:
        state["last_nudge_ack"] = last_nudge_ack
    elif existing.get("last_nudge_ack") is not None:
        state["last_nudge_ack"] = existing.get("last_nudge_ack")

    if last_nudge_snooze is not None:
        state["last_nudge_snooze"] = last_nudge_snooze
    elif existing.get("last_nudge_snooze") is not None:
        state["last_nudge_snooze"] = existing.get("last_nudge_snooze")

    atomic_write_json(INTERACTION_STATE_JSON, state)
    return state


def remove_pending_question():
    if PENDING_QUESTION_JSON.exists():
        try:
            PENDING_QUESTION_JSON.unlink()
        except Exception:
            pass


def option_label_for_answer(question, answer):
    if not isinstance(question, dict):
        return ""

    for option in question.get("answer_options", []) or []:
        if not isinstance(option, dict):
            continue
        if str(option.get("id", "")).strip() == answer:
            return str(option.get("label", "")).strip()

    return ""


def write_question_inactive(status, event):
    existing = read_json(CURRENT_QUESTION_JSON, {})
    if not isinstance(existing, dict):
        existing = {}

    payload = {
        "schema_version": "phone_interaction.v1",
        "kind": "question",
        "status": "inactive",
        "last_status": status,
        "updated_at": now_iso(),
        "source": "action-bridge",
        "planner_mode": existing.get("planner_mode", ""),
        "question": "",
        "answer_options": [],
        "free_text_allowed": True,
        "response_action": "answer_question",
        "last_response": {
            "action_id": event.get("action_id", ""),
            "event_type": event.get("event_type", ""),
            "question_id": event.get("question_id", ""),
            "answer": event.get("answer", ""),
            "answer_label": event.get("answer_label", ""),
            "free_text": event.get("free_text", ""),
            "processed_at": event.get("processed_at", ""),
        },
    }

    atomic_write_json(CURRENT_QUESTION_JSON, payload)

    lines = [
        "# Current Question",
        "",
        "Status: inactive",
        f"Last status: {status}",
        f"Question ID: {event.get('question_id', '')}",
        f"Answer: {event.get('answer_label') or event.get('answer', '')}",
        f"Updated: {payload['updated_at']}",
        "",
    ]

    if event.get("free_text"):
        lines.extend([
            "## Free text",
            "",
            event.get("free_text", ""),
            "",
        ])

    atomic_write_text(CURRENT_QUESTION_MD, "\n".join(lines))


def write_nudge_inactive(status, event):
    existing = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(existing, dict):
        existing = {}

    payload = {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "inactive",
        "last_status": status,
        "updated_at": now_iso(),
        "source": "action-bridge",
        "planner_mode": existing.get("planner_mode", ""),
        "urgency": existing.get("urgency", "normal"),
        "message": "",
        "recommended_next_action": existing.get("recommended_next_action", ""),
        "actions": [],
        "last_ack": {
            "action_id": event.get("action_id", ""),
            "nudge_id": event.get("nudge_id", ""),
            "intervention_id": event.get("intervention_id", ""),
            "processed_at": event.get("processed_at", ""),
        },
    }

    atomic_write_json(CURRENT_NUDGE_JSON, payload)

    atomic_write_text(
        CURRENT_NUDGE_MD,
        "\n".join([
            "# Current Nudge",
            "",
            "Status: inactive",
            f"Last status: {status}",
            f"Nudge ID: {event.get('nudge_id', '')}",
            f"Message: {existing.get('message', '')}",
            f"Recommended next action: {existing.get('recommended_next_action', '')}",
            f"Updated: {payload['updated_at']}",
            "",
        ]),
    )


def write_nudge_snoozed(event):
    existing = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(existing, dict):
        existing = {}

    payload = {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "inactive",
        "last_status": "snoozed",
        "updated_at": now_iso(),
        "source": "action-bridge",
        "planner_mode": existing.get("planner_mode", ""),
        "urgency": existing.get("urgency", "normal"),
        "message": "",
        "recommended_next_action": existing.get("recommended_next_action", ""),
        "actions": [],
        "snooze_minutes": event.get("snooze_minutes", 15),
        "snoozed_until": event.get("snoozed_until", ""),
        "last_snooze": {
            "action_id": event.get("action_id", ""),
            "nudge_id": event.get("nudge_id", ""),
            "reason": event.get("reason", ""),
            "snooze_minutes": event.get("snooze_minutes", 15),
            "snoozed_until": event.get("snoozed_until", ""),
            "intervention_id": event.get("intervention_id", ""),
            "processed_at": event.get("processed_at", ""),
        },
    }

    atomic_write_json(CURRENT_NUDGE_JSON, payload)

    atomic_write_text(
        CURRENT_NUDGE_MD,
        "\n".join([
            "# Current Nudge",
            "",
            "Status: inactive",
            "Last status: snoozed",
            f"Nudge ID: {event.get('nudge_id', '')}",
            f"Snooze minutes: {event.get('snooze_minutes', 15)}",
            f"Snoozed until: {event.get('snoozed_until', '')}",
            f"Message: {existing.get('message', '')}",
            f"Recommended next action: {existing.get('recommended_next_action', '')}",
            f"Updated: {payload['updated_at']}",
            "",
        ]),
    )


def handle_answer_question(action, path, action_id):
    current_question = read_json(CURRENT_QUESTION_JSON, {})
    if not isinstance(current_question, dict):
        current_question = {}

    pending_question = read_json(PENDING_QUESTION_JSON, {})
    if not isinstance(pending_question, dict):
        pending_question = {}

    known_question_id = str(
        current_question.get("question_id")
        or pending_question.get("question_id")
        or ""
    ).strip()

    provided_question_id = str(action.get("question_id") or action.get("interaction_id") or "").strip()
    question_id = provided_question_id or known_question_id

    answer = str(action.get("answer") or action.get("answer_id") or "").strip()
    if not answer and not str(action.get("free_text") or action.get("note") or "").strip():
        raise ValueError("answer_question requires answer or free_text")

    answer_label = str(
        action.get("answer_label")
        or action.get("label")
        or option_label_for_answer(current_question or pending_question, answer)
        or answer
    ).strip()

    event = base_event(action, path, action_id)
    event["event"] = "answer_question"
    event["event_type"] = "answer_question"
    event["question_id"] = question_id
    event["known_question_id"] = known_question_id
    event["question_id_mismatch"] = bool(provided_question_id and known_question_id and provided_question_id != known_question_id)
    event["question"] = str(current_question.get("question") or pending_question.get("question") or "")
    event["answer"] = answer
    event["answer_label"] = answer_label
    event["free_text"] = str(action.get("free_text") or action.get("note") or "")

    atomic_write_json(LAST_ANSWER_JSON, event)
    append_action_event(event)

    remove_pending_question()
    write_question_inactive("answered", event)

    interaction_state = write_interaction_state_from_current(
        source="action-bridge",
        last_question_response={
            "action_id": event.get("action_id", ""),
            "question_id": event.get("question_id", ""),
            "answer": event.get("answer", ""),
            "answer_label": event.get("answer_label", ""),
            "free_text": event.get("free_text", ""),
            "processed_at": event.get("processed_at", ""),
        },
    )

    return {
        "event": event,
        "interaction_state": interaction_state,
        "triggered_help_now": trigger_help_now(),
    }


def handle_ack_nudge(action, path, action_id):
    current_nudge = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(current_nudge, dict):
        current_nudge = {}

    nudge_id = str(action.get("nudge_id") or action.get("interaction_id") or current_nudge.get("nudge_id") or "").strip()

    event = base_event(action, path, action_id)
    event["event"] = "ack_nudge"
    event["event_type"] = "ack_nudge"
    event["nudge_id"] = nudge_id
    event["message"] = str(current_nudge.get("message") or action.get("message") or "")
    event["recommended_next_action"] = str(current_nudge.get("recommended_next_action") or "")
    attach_intervention_ref(event, action, current_nudge)

    append_action_event(event)
    write_nudge_inactive("acknowledged", event)

    interaction_state = write_interaction_state_from_current(
        source="action-bridge",
        last_nudge_ack={
            "action_id": event.get("action_id", ""),
            "nudge_id": event.get("nudge_id", ""),
            "intervention_id": event.get("intervention_id", ""),
            "processed_at": event.get("processed_at", ""),
        },
    )

    return {
        "event": event,
        "interaction_state": interaction_state,
        "triggered_help_now": False,
    }


def _bounded_snooze_minutes(value):
    try:
        minutes = int(value)
    except Exception:
        minutes = 15

    return max(1, min(minutes, 24 * 60))


def handle_snooze_nudge(action, path, action_id):
    current_nudge = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(current_nudge, dict):
        current_nudge = {}

    nudge_id = str(
        action.get("nudge_id")
        or action.get("interaction_id")
        or current_nudge.get("nudge_id")
        or ""
    ).strip()

    snooze_minutes = _bounded_snooze_minutes(
        action.get("snooze_minutes")
        or action.get("minutes")
        or 15
    )

    snoozed_until = (now() + timedelta(minutes=snooze_minutes)).isoformat(timespec="seconds")

    event = base_event(action, path, action_id)
    event["event"] = "snooze_nudge"
    event["event_type"] = "snooze_nudge"
    event["nudge_id"] = nudge_id
    event["reason"] = str(action.get("reason") or "not_now")
    event["snooze_minutes"] = snooze_minutes
    event["snoozed_until"] = snoozed_until
    event["message"] = str(current_nudge.get("message") or action.get("message") or "")
    event["recommended_next_action"] = str(
        current_nudge.get("recommended_next_action")
        or action.get("recommended_next_action")
        or ""
    )
    attach_intervention_ref(event, action, current_nudge)

    append_action_event(event)
    write_nudge_snoozed(event)

    interaction_state = write_interaction_state_from_current(
        source="action-bridge",
        last_nudge_snooze={
            "action_id": event.get("action_id", ""),
            "nudge_id": event.get("nudge_id", ""),
            "reason": event.get("reason", ""),
            "snooze_minutes": event.get("snooze_minutes", 15),
            "snoozed_until": event.get("snoozed_until", ""),
            "intervention_id": event.get("intervention_id", ""),
            "processed_at": event.get("processed_at", ""),
        },
    )

    return {
        "event": event,
        "interaction_state": interaction_state,
        "triggered_help_now": False,
    }


def handle_dismiss_question(action, path, action_id):
    current_question = read_json(CURRENT_QUESTION_JSON, {})
    if not isinstance(current_question, dict):
        current_question = {}

    pending_question = read_json(PENDING_QUESTION_JSON, {})
    if not isinstance(pending_question, dict):
        pending_question = {}

    known_question_id = str(
        current_question.get("question_id")
        or pending_question.get("question_id")
        or ""
    ).strip()

    provided_question_id = str(action.get("question_id") or action.get("interaction_id") or "").strip()
    question_id = provided_question_id or known_question_id

    event = base_event(action, path, action_id)
    event["event"] = "dismiss_question"
    event["event_type"] = "dismiss_question"
    event["question_id"] = question_id
    event["known_question_id"] = known_question_id
    event["question_id_mismatch"] = bool(provided_question_id and known_question_id and provided_question_id != known_question_id)
    event["question"] = str(current_question.get("question") or pending_question.get("question") or "")
    event["reason"] = str(action.get("reason") or "")

    append_action_event(event)

    remove_pending_question()
    write_question_inactive("dismissed", event)

    interaction_state = write_interaction_state_from_current(
        source="action-bridge",
        last_question_response={
            "action_id": event.get("action_id", ""),
            "question_id": event.get("question_id", ""),
            "dismissed": True,
            "reason": event.get("reason", ""),
            "processed_at": event.get("processed_at", ""),
        },
    )

    return {
        "event": event,
        "interaction_state": interaction_state,
        "triggered_help_now": False,
    }


def write_nudge_recovery_started(event):
    nudge_id = str(event.get("nudge_id") or "").strip()
    if not nudge_id:
        return None

    existing = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(existing, dict):
        existing = {}

    payload = {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "inactive",
        "last_status": "recovery_started",
        "updated_at": now_iso(),
        "source": "action-bridge",
        "planner_mode": existing.get("planner_mode", ""),
        "urgency": existing.get("urgency", "normal"),
        "message": "",
        "recommended_next_action": existing.get("recommended_next_action", ""),
        "actions": [],
        "last_recovery_start": {
            "action_id": event.get("action_id", ""),
            "nudge_id": nudge_id,
            "recovery_id": event.get("recovery_id", ""),
            "target_id": event.get("target_id", ""),
            "intervention_id": event.get("intervention_id", ""),
            "processed_at": event.get("processed_at", ""),
        },
    }

    atomic_write_json(CURRENT_NUDGE_JSON, payload)

    atomic_write_text(
        CURRENT_NUDGE_MD,
        "\n".join([
            "# Current Nudge",
            "",
            "Status: inactive",
            "Last status: recovery_started",
            f"Nudge ID: {nudge_id}",
            f"Recovery ID: {event.get('recovery_id', '')}",
            f"Target: {event.get('target_name') or event.get('target_id', '')}",
            f"Message: {existing.get('message', '')}",
            f"Recommended next action: {existing.get('recommended_next_action', '')}",
            f"Updated: {payload['updated_at']}",
            "",
        ]),
    )

    return payload



def known_recovery_target(target_id):
    return get_recovery_target(target_id)


def handle_start_recovery_target(action, path, action_id):
    target_id = str(action.get("target_id") or action.get("target") or "anki").strip().lower()
    target = known_recovery_target(target_id)
    current_nudge = read_json(CURRENT_NUDGE_JSON, {})
    if not isinstance(current_nudge, dict):
        current_nudge = {}

    goal_text = str(
        action.get("goal_text")
        or action.get("goal")
        or target.get("default_goal")
        or "5 minutes"
    ).strip()

    recovery_id = str(action.get("recovery_id") or f"recovery-{target['target_id']}-{int(time.time())}")

    event = base_event(action, path, action_id)
    event["event"] = "recovery_started"
    event["event_type"] = "recovery_started"
    event["recovery_id"] = recovery_id
    event["target_id"] = target["target_id"]
    event["target_name"] = str(action.get("target_name") or target.get("display_name") or target["target_id"])
    event["goal_text"] = goal_text
    event["android_package"] = str(action.get("android_package") or target.get("android_package") or "")
    event["started_at"] = event.get("processed_at", now_iso())
    intervention_id = attach_intervention_ref(event, action, current_nudge)

    recovery_state = {
        "schema_version": "recovery_session.v1",
        "recovery_id": recovery_id,
        "status": "active",
        "started_at": event["started_at"],
        "updated_at": now_iso(),
        "source": event.get("source", ""),
        "device": event.get("device", ""),
        "action_id": action_id,
        "intervention": {
            "schema_version": "intervention_ref.v1",
            "intervention_id": intervention_id,
            "kind": event.get("intervention_kind", ""),
            "source": "action-bridge",
            "nudge_id": event.get("nudge_id", ""),
        },
        "target": {
            "target_id": event["target_id"],
            "name": event["target_name"],
            "kind": target.get("kind", "unknown"),
            "android_package": event["android_package"],
        },
        "goal": {
            "text": goal_text,
            "stop_condition": str(action.get("stop_condition") or goal_text),
        },
        "launch": {
            "requested": bool(event["android_package"]),
            "android_package": event["android_package"],
            "handled_by": "tasker" if event.get("device") == "phone" else "external-ui",
        },
        "last_event": event,
    }

    atomic_write_json(RECOVERY_CURRENT_JSON, recovery_state)

    atomic_write_text(
        RECOVERY_STATUS_MD,
        "\n".join([
            "# Recovery Status",
            "",
            f"Updated: {recovery_state['updated_at']}",
            "Status: `active`",
            f"Recovery ID: `{recovery_id}`",
            f"Target: {event['target_name']}",
            f"Goal: {goal_text}",
            f"Android package: `{event['android_package']}`",
            "",
        ]),
    )

    append_jsonl(EVENTS_RECOVERY_DIR / f"{today()}.jsonl", event)
    append_jsonl(EVENTS_ACTIONS_DIR / f"{today()}.jsonl", event)

    consumed_nudge = write_nudge_recovery_started(event)
    interaction_state = write_interaction_state_from_current(source="action-bridge")

    return {
        "event": event,
        "recovery_state": recovery_state,
        "consumed_nudge": consumed_nudge,
        "interaction_state": interaction_state,
        "triggered_help_now": False,
    }


def handle_action(path):
    action = json.loads(path.read_text(encoding="utf-8"))
    action_name = get_action_name(action)

    if not action_name:
        raise ValueError("action file requires action or command")

    action_id = action_id_for(path, action)
    result = {
        "action_id": action_id,
        "action": action_name,
    }

    if action_name in {"start_session", "start"}:
        result["command_result"] = handle_start_session(action)
    elif action_name in {"end_session", "end"}:
        result["command_result"] = handle_end_session(action)
    elif action_name in {"check_in", "manual_checkin"}:
        result["check_in_result"] = handle_check_in(action, path, action_id)
    elif action_name in {"answer_question", "question_answered"}:
        result["answer_result"] = handle_answer_question(action, path, action_id)
    elif action_name in {"ack_nudge", "nudge_acknowledged"}:
        result["ack_result"] = handle_ack_nudge(action, path, action_id)
    elif action_name in {"snooze_nudge", "defer_nudge", "nudge_snoozed"}:
        result["snooze_result"] = handle_snooze_nudge(action, path, action_id)
    elif action_name in {"dismiss_question", "question_dismissed"}:
        result["dismiss_result"] = handle_dismiss_question(action, path, action_id)
    elif action_name in {"start_recovery_target", "start_recovery", "recovery_start"}:
        result["recovery_result"] = handle_start_recovery_target(action, path, action_id)
    elif action_name in {"promote_task_proposal", "promote_proposal"}:
        result["promotion_result"] = handle_promote_task_proposal(action, path, action_id)
    elif action_name in {"submit_proof", "proof_submitted"}:
        result["proof_result"] = handle_submit_proof(action, path, action_id)
    else:
        raise ValueError(f"unknown action: {action_name}")

    return result


def process_all():
    ensure_dirs()
    create_templates()

    paths = sorted([p for p in INBOX_DIR.glob("*.json") if p.is_file()], key=lambda p: p.stat().st_mtime)

    if not paths:
        write_status("idle", "no pending actions")
        print("no pending actions")
        return

    processed = []
    failed = []
    unstable = []

    for path in paths:
        if not is_stable(path):
            unstable.append(str(path))
            continue

        try:
            result = handle_action(path)
            destination = move_unique(path, PROCESSED_DIR / today())
            result["processed_path"] = str(destination)
            processed.append(result)
            print(f"processed action {result.get('action')} from {path.name}", flush=True)
        except Exception as error:
            try:
                destination = move_unique(path, FAILED_DIR / today())
            except Exception:
                destination = path

            atomic_write_text(Path(str(destination) + ".error.txt"), str(error) + "\n")

            failed.append({
                "path": str(destination),
                "error": str(error),
            })

            print(f"failed action {path}: {error}", file=sys.stderr, flush=True)

    if failed:
        status = "failed"
    elif unstable and not processed:
        status = "waiting"
    else:
        status = "processed"

    write_status(
        status,
        f"processed={len(processed)} failed={len(failed)} unstable={len(unstable)}",
        {
            "processed": processed,
            "failed": failed,
            "unstable": unstable,
            "authority_level": AUTHORITY_LEVEL,
        },
    )


def create_templates():
    templates = {
        "start-anki.json": {
            "schema_version": "action.v1",
            "action": "start_session",
            "source": "action-template",
            "device": "desktop",
            "task": "Anki Language recovery",
            "project": "Anki Recovery",
            "mode": "anki",
            "duration": 25,
            "strictness": 2,
            "language_level": 1
        },
        "end-completed.json": {
            "schema_version": "action.v1",
            "action": "end_session",
            "source": "action-template",
            "device": "desktop",
            "status": "completed",
            "reason": "Ended from action template"
        },
        "check-in-overwhelmed.json": {
            "schema_version": "action.v1",
            "action": "check_in",
            "source": "action-template",
            "device": "desktop",
            "answer": "overwhelmed",
            "answer_label": "Overwhelmed",
            "free_text": ""
        },
        "promote-anki-recovery.json": {
            "schema_version": "action.v1",
            "action": "promote_task_proposal",
            "source": "action-template",
            "device": "desktop",
            "proposal": "anki-recovery",
            "target": "AI/anki-due-recovery.md",
            "overwrite": True,
            "project": "Anki Recovery"
        },
        "submit-proof.json": {
            "schema_version": "action.v1",
            "action": "submit_proof",
            "source": "action-template",
            "device": "phone",
            "proof_id": "example-proof",
            "message": "Proof submitted"
        },
        "answer-question.json": {
            "schema_version": "action.v1",
            "action": "answer_question",
            "source": "action-template",
            "device": "phone",
            "question_id": "",
            "answer": "overwhelmed",
            "answer_label": "Overwhelmed",
            "free_text": ""
        },
        "ack-nudge.json": {
            "schema_version": "action.v1",
            "action": "ack_nudge",
            "source": "action-template",
            "device": "phone",
            "nudge_id": ""
        },
        "dismiss-question.json": {
            "schema_version": "action.v1",
            "action": "dismiss_question",
            "source": "action-template",
            "device": "phone",
            "question_id": "",
            "reason": "Dismissed from template"
        }
    }

    for filename, data in templates.items():
        path = TEMPLATES_DIR / filename
        if not path.exists():
            atomic_write_json(path, data)

    schema_path = SCHEMAS_DIR / "action.v1.example.json"
    if not schema_path.exists():
        atomic_write_json(schema_path, {
            "schema_version": "action.v1",
            "action": "start_session|end_session|check_in|answer_question|ack_nudge|dismiss_question|promote_task_proposal|submit_proof",
            "source": "obsidian|tasker|desktop-panel|llm-proposal|manual",
            "device": "desktop|phone",
            "created_at": "ISO-8601 timestamp",
            "notes": "Drop action JSON files into AI/inbox/actions/."
        })


def main():
    try:
        process_all()
    except Exception as error:
        write_status("crashed", str(error), {"error": str(error)})
        print(f"action-bridge failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
