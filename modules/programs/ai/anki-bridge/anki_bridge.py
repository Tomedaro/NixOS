#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from ai_system.io_utils import atomic_write_json, atomic_write_text, append_jsonl
from ai_system.time_utils import get_timezone, now_iso, today


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TASKNOTES_DIR = Path(os.environ.get("TASKNOTES_DIR", "/home/daniil/Sync/Perseverance.Gu/TaskNotes")).expanduser()
ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765").rstrip("/")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "300"))
CREATE_TASKNOTE = os.environ.get("CREATE_TASKNOTE", "1") == "1"
TASKNOTE_MODE = os.environ.get("TASKNOTE_MODE", "propose").strip().lower()
TIMEZONE = get_timezone(os.environ.get("ANKI_BRIDGE_TIMEZONE", "Europe/Paris"))

if not CREATE_TASKNOTE:
    TASKNOTE_MODE = "off"

if TASKNOTE_MODE not in {"off", "propose", "direct"}:
    TASKNOTE_MODE = "propose"

DECKS = json.loads(os.environ.get("ANKI_DECKS_JSON", "[]"))

ANKI_DIR = AI_DIR / "anki"
STATUS_JSON = ANKI_DIR / "status.json"
STATUS_MD = ANKI_DIR / "status.md"
ANKI_EVENTS_DIR = AI_DIR / "events" / "anki"

PROPOSED_TASKS_DIR = AI_DIR / "proposed-tasks"
PROPOSED_RECOVERY_TASK = PROPOSED_TASKS_DIR / "anki-recovery.md"

TASKNOTE_AI_DIR = TASKNOTES_DIR / "AI"
DIRECT_RECOVERY_TASK = TASKNOTE_AI_DIR / "anki-due-recovery.md"


def ensure_dirs():
    for path in [
        ANKI_DIR,
        ANKI_EVENTS_DIR,
        PROPOSED_TASKS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    if TASKNOTE_MODE == "direct":
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
            "User-Agent": "anki-bridge/0.2",
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


def numeric(value, default=0):
    if isinstance(value, int):
        return value
    return default


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

    due = numeric(counts.get("due"))
    new = numeric(counts.get("new"))
    learning = numeric(counts.get("learning"))
    review_due = numeric(counts.get("review_due"))
    reviewed_today = numeric(counts.get("reviewed_today"))
    again_today = numeric(counts.get("again_today"))

    if due >= 300:
        priority = "urgent"
    elif due >= 100:
        priority = "high"
    elif due >= 30:
        priority = "medium"
    elif due > 0:
        priority = "normal"
    else:
        priority = "low"

    if due > 0:
        if due >= 100:
            suggested_goal = "Do a 15-minute recovery block. Aim for 25 reviews, not the whole backlog."
        elif due >= 30:
            suggested_goal = "Do a 12-minute recovery block. Aim for 20 reviews."
        else:
            suggested_goal = "Do a short cleanup block. Aim to finish the due cards."
    else:
        suggested_goal = "No due cards. Maintain streak or relearn weak cards."

    return {
        "deck": deck,
        "counts": counts,
        "derived": {
            "due": due,
            "new": new,
            "learning": learning,
            "review_due": review_due,
            "reviewed_today": reviewed_today,
            "again_today": again_today,
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

    deck_statuses = [collect_deck(deck) for deck in selected_decks]

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
        "schema_version": "anki-status.v1",
        "available": True,
        "timestamp": now_iso(TIMEZONE),
        "date": today(TIMEZONE),
        "anki_connect_url": ANKI_CONNECT_URL,
        "anki_connect_version": version,
        "configured_decks": selected_decks,
        "available_decks": deck_names,
        "decks": deck_statuses,
        "totals": totals,
        "overall_priority": overall_priority,
        "authority": {
            "tasknote_mode": TASKNOTE_MODE,
            "direct_tasknotes_enabled": TASKNOTE_MODE == "direct",
            "proposal_path": str(PROPOSED_RECOVERY_TASK),
            "direct_tasknote_path": str(DIRECT_RECOVERY_TASK),
        },
    }


def unavailable_status(error):
    return {
        "schema_version": "anki-status.v1",
        "available": False,
        "timestamp": now_iso(TIMEZONE),
        "date": today(TIMEZONE),
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
        "authority": {
            "tasknote_mode": TASKNOTE_MODE,
            "direct_tasknotes_enabled": TASKNOTE_MODE == "direct",
            "proposal_path": str(PROPOSED_RECOVERY_TASK),
            "direct_tasknote_path": str(DIRECT_RECOVERY_TASK),
        },
    }


def write_status_json(status):
    atomic_write_json(STATUS_JSON, status)


def write_status_markdown(status):
    lines = []

    lines.append("# Anki Status")
    lines.append("")
    lines.append(f"Last updated: {status['timestamp']}")
    lines.append(f"Anki available: {str(status['available']).lower()}")
    lines.append(f"TaskNote authority mode: `{TASKNOTE_MODE}`")
    lines.append("")

    if not status["available"]:
        lines.append("## Error")
        lines.append("")
        lines.append(f"`{status.get('error', 'unknown error')}`")
        lines.append("")
        lines.append("Open Anki and make sure Anki-Connect-Plus is enabled.")
        lines.append("")
        atomic_write_text(STATUS_MD, "\n".join(lines))
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
        lines.append("You have an Anki backlog. Use repeated small recovery blocks, not a full catch-up attempt.")
        lines.append("")
        lines.append("Suggested next block:")
        lines.append("")
        lines.append("- Open Anki")
        lines.append("- Start with the highest-due deck")
        lines.append("- Do 12 to 15 minutes")
        lines.append("- Stop and reflect briefly")
    else:
        lines.append("No due cards in the configured decks.")

    lines.append("")
    lines.append("## Authority")
    lines.append("")
    lines.append(f"- Mode: `{TASKNOTE_MODE}`")
    lines.append(f"- Proposal path: `{PROPOSED_RECOVERY_TASK}`")
    lines.append(f"- Direct TaskNote path: `{DIRECT_RECOVERY_TASK}`")
    lines.append("")

    atomic_write_text(STATUS_MD, "\n".join(lines))


def priority_for_due(due):
    if due >= 100:
        return "high"
    if due >= 30:
        return "medium"
    if due > 0:
        return "normal"
    return "low"


def task_status_for_due(due):
    if due == 0:
        return "done"
    return "todo"


def recovery_markdown(status, destination_kind):
    totals = status["totals"]
    due = totals["due"]
    priority = priority_for_due(due)
    status_value = task_status_for_due(due)
    today_value = today(TIMEZONE)

    body = []

    if destination_kind == "direct":
        body.append("---")
        body.append("tags:")
        body.append("  - task")
        body.append("  - ai")
        body.append("  - anki")
        body.append('title: "Recover Anki backlog"')
        body.append(f"status: {status_value}")
        body.append(f"priority: {priority}")
        body.append(f"scheduled: {today_value}")
        body.append(f"due: {today_value}")
        body.append("contexts:")
        body.append('  - "@computer"')
        body.append("projects:")
        body.append('  - "[[Anki Recovery]]"')
        body.append("---")
        body.append("")

    body.append("# Recover Anki backlog")
    body.append("")

    if destination_kind == "direct":
        body.append("> Managed by the local AI Anki bridge in direct mode.")
    else:
        body.append("> Proposed by the local AI Anki bridge. Review before turning into a real TaskNote.")

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
    body.append(f"- Priority: **{priority}**")
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
    body.append("- [ ] Do one 12 to 15 minute Anki recovery block")
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

    return "\n".join(body)


def write_recovery_task_or_proposal(status):
    if not status["available"]:
        return None

    if TASKNOTE_MODE == "off":
        return None

    if TASKNOTE_MODE == "direct":
        atomic_write_text(DIRECT_RECOVERY_TASK, recovery_markdown(status, "direct"))
        return {
            "mode": "direct",
            "path": str(DIRECT_RECOVERY_TASK),
        }

    atomic_write_text(PROPOSED_RECOVERY_TASK, recovery_markdown(status, "propose"))
    return {
        "mode": "propose",
        "path": str(PROPOSED_RECOVERY_TASK),
    }


def write_event(status, task_output):
    event = {
        "schema_version": "event.v1",
        "source": "anki-bridge",
        "device": "desktop",
        "event": "anki_status_updated",
        "event_type": "anki_status_updated",
        "timestamp": status["timestamp"],
        "date": status["date"],
        "time": status["timestamp"].split("T", 1)[-1].split("+", 1)[0],
        "available": status["available"],
        "overall_priority": status.get("overall_priority", "unknown"),
        "totals": status.get("totals", {}),
        "tasknote_mode": TASKNOTE_MODE,
        "task_output": task_output or {},
    }

    append_jsonl(ANKI_EVENTS_DIR / f"{status['date']}.jsonl", event)


def tick():
    ensure_dirs()

    try:
        status = collect_status()
    except Exception as error:
        status = unavailable_status(error)

    write_status_json(status)
    write_status_markdown(status)
    task_output = write_recovery_task_or_proposal(status)
    write_event(status, task_output)


def main():
    print("Anki bridge started", flush=True)
    print(f"AI_DIR={AI_DIR}", flush=True)
    print(f"TASKNOTES_DIR={TASKNOTES_DIR}", flush=True)
    print(f"ANKI_CONNECT_URL={ANKI_CONNECT_URL}", flush=True)
    print(f"DECKS={DECKS}", flush=True)
    print(f"TASKNOTE_MODE={TASKNOTE_MODE}", flush=True)

    while True:
        try:
            tick()
        except Exception as error:
            print(f"anki bridge tick failed: {error}", file=sys.stderr, flush=True)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
