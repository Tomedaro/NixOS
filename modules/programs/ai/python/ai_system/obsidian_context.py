"""Bounded Obsidian context snapshots for the local AI context hub.

This module is intentionally observational. It lets Obsidian, Templater, buttons,
or future UI surfaces publish current workspace facts into state/obsidian without
enqueuing actions or mutating plans.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text

DEFAULT_AI_DIR = Path(
    os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")
).expanduser()

MAX_TEXT_PREVIEW_CHARS = 1200
MAX_TASKS = 25
MAX_RECENT_NOTES = 25
MAX_TAGS = 32
MAX_GOAL_IDS = 32


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bounded_str(value: Any, *, max_chars: int = 300) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def bounded_str_list(value: Any, *, limit: int, max_chars: int = 160) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value:
        text = bounded_str(item, max_chars=max_chars)
        if text:
            out.append(text)
        if len(out) >= limit:
            break

    return out


def compact_task(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"text": bounded_str(value, max_chars=300)}

    if not isinstance(value, dict):
        return {}

    allowed = [
        "id",
        "text",
        "content",
        "path",
        "status",
        "priority",
        "due",
        "scheduled",
        "project",
        "goal_id",
        "area",
    ]

    task: dict[str, Any] = {}
    for key in allowed:
        if key not in value:
            continue
        item = value[key]
        if isinstance(item, (int, float, bool)) or item is None:
            task[key] = item
        else:
            task[key] = bounded_str(item, max_chars=300)

    if "text" not in task and "content" in task:
        task["text"] = task["content"]

    return task


def compact_tasks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    out: list[dict[str, Any]] = []
    for item in value:
        task = compact_task(item)
        if task:
            out.append(task)
        if len(out) >= MAX_TASKS:
            break

    return out


def compact_recent_note(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        return {"path": bounded_str(value, max_chars=240)}

    if not isinstance(value, dict):
        return {}

    return {
        key: bounded_str(value.get(key), max_chars=240)
        for key in ("path", "title", "reason", "updated_at")
        if value.get(key)
    }


def compact_recent_notes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    out: list[dict[str, str]] = []
    for item in value:
        note = compact_recent_note(item)
        if note:
            out.append(note)
        if len(out) >= MAX_RECENT_NOTES:
            break

    return out


def normalize_obsidian_context(payload: dict[str, Any]) -> dict[str, Any]:
    active_note = payload.get("active_note")
    active_note_dict = active_note if isinstance(active_note, dict) else {}

    active_note_path = (
        payload.get("active_note_path")
        or payload.get("path")
        or active_note_dict.get("path")
        or active_note_dict.get("file")
        or ""
    )
    active_note_title = (
        payload.get("active_note_title")
        or payload.get("title")
        or active_note_dict.get("title")
        or ""
    )

    tags = (
        payload.get("active_note_tags")
        or payload.get("tags")
        or active_note_dict.get("tags")
        or []
    )

    selected_text = (
        payload.get("selected_text")
        or payload.get("selection")
        or payload.get("selected_text_preview")
        or ""
    )

    open_tasks = payload.get("open_tasks") or payload.get("tasks") or []
    recent_notes = payload.get("recent_notes") or []
    goal_ids = payload.get("current_goal_ids") or payload.get("goal_ids") or []

    return {
        "schema_version": "obsidian_context.v1",
        "updated_at": bounded_str(payload.get("updated_at") or now_iso(), max_chars=80),
        "source": bounded_str(payload.get("source") or "obsidian", max_chars=80),
        "surface": "obsidian",
        "mode": bounded_str(
            payload.get("mode") or payload.get("communication_mode") or "",
            max_chars=80,
        ),
        "active_note_path": bounded_str(active_note_path, max_chars=300),
        "active_note_title": bounded_str(active_note_title, max_chars=200),
        "active_note_tags": bounded_str_list(tags, limit=MAX_TAGS, max_chars=80),
        "selected_text_preview": bounded_str(
            selected_text,
            max_chars=MAX_TEXT_PREVIEW_CHARS,
        ),
        "open_tasks": compact_tasks(open_tasks),
        "recent_notes": compact_recent_notes(recent_notes),
        "current_goal_ids": bounded_str_list(
            goal_ids,
            limit=MAX_GOAL_IDS,
            max_chars=120,
        ),
        "latest_user_message_preview": bounded_str(
            payload.get("latest_user_message") or payload.get("message") or "",
            max_chars=600,
        ),
    }


def render_status_markdown(context: dict[str, Any]) -> str:
    lines = [
        "# Obsidian Context",
        "",
        f"Updated: `{context.get('updated_at', '')}`",
        f"Mode: `{context.get('mode') or 'unknown'}`",
        f"Active note: `{context.get('active_note_path') or 'unknown'}`",
        f"Open tasks: `{len(context.get('open_tasks') or [])}`",
        f"Recent notes: `{len(context.get('recent_notes') or [])}`",
        "",
    ]

    tags = context.get("active_note_tags") or []
    if tags:
        lines.extend(["## Tags", "", *[f"- `{tag}`" for tag in tags], ""])

    message = context.get("latest_user_message_preview") or ""
    if message:
        lines.extend(["## Latest user message preview", "", message, ""])

    return "\n".join(lines)


def write_obsidian_context(
    ai_dir: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    root = Path(ai_dir).expanduser()
    state_dir = root / "state" / "obsidian"
    context = normalize_obsidian_context(payload)

    atomic_write_json(state_dir / "context.json", context)
    atomic_write_json(state_dir / "latest.json", context)
    atomic_write_text(state_dir / "status.md", render_status_markdown(context))

    return context


def read_payload(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).expanduser().read_text(encoding="utf-8")

    if not raw.strip():
        return {}

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("Obsidian context payload must be a JSON object")

    return data


def example_payload() -> dict[str, Any]:
    return {
        "mode": "mentor",
        "active_note_path": "Goals/Today.md",
        "active_note_title": "Today",
        "tags": ["study", "planning"],
        "selected_text": "Work on one small proof exercise.",
        "open_tasks": [
            {
                "text": "Review linear algebra notes",
                "status": "todo",
                "goal_id": "stem-study",
                "priority": "high",
            }
        ],
        "recent_notes": [{"path": "STEM/Linear algebra.md", "reason": "active study"}],
        "current_goal_ids": ["stem-study", "neovim-cli"],
        "latest_user_message": "Help me choose the next useful study action.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write bounded Obsidian context")
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument("--input", default="-", help="JSON file, or - for stdin")
    parser.add_argument("--write", action="store_true", help="Write state files")
    parser.add_argument("--dry-run", action="store_true", help="Print normalized JSON")
    parser.add_argument("--example", action="store_true", help="Print example payload")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.example:
        print(json.dumps(example_payload(), indent=2, ensure_ascii=False))
        return 0

    payload = read_payload(args.input)
    context = normalize_obsidian_context(payload)

    if args.write:
        context = write_obsidian_context(args.ai_dir, payload)

    if args.dry_run or not args.write:
        print(json.dumps(context, indent=2, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
