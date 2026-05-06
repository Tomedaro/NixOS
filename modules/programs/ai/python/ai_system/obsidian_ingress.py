"""Obsidian intent ingress.

This module accepts text/button intents from Obsidian and writes normalized,
append-only JSON messages. It never executes actions directly.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json
from ai_system.obsidian_contracts import (
    DEFAULT_AI_DIR,
    PLANNER_EXECUTION_POLICY,
    bounded_text as contract_bounded_text,
    utc_now,
)

MAX_MESSAGE_CHARS = 2000
MAX_SELECTED_TEXT_CHARS = 1200
MAX_NOTE_PATH_CHARS = 300


def epoch_millis(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def clip_text(value: Any, limit: int) -> str:
    return contract_bounded_text(value, max_len=limit)


def normalize_ids(values: list[str] | None) -> list[str]:
    out: list[str] = []

    for value in values or []:
        for item in str(value).split(","):
            normalized = item.strip()
            if normalized and normalized not in out:
                out.append(normalized)

    return out


def read_input_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_intent(
    *,
    message: str = "",
    action: str = "",
    mode: str = "mentor",
    note_path: str = "",
    selected_text: str = "",
    goal_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
    surface: str = "obsidian",
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()

    message = clip_text(message, MAX_MESSAGE_CHARS)
    action = clip_text(action, 200)
    selected_text = clip_text(selected_text, MAX_SELECTED_TEXT_CHARS)
    note_path = clip_text(note_path, MAX_NOTE_PATH_CHARS)

    if not message and not action:
        raise ValueError("obsidian intent requires --message or --action")

    kind = "action_request" if action else "message"
    intent_id = f"obsidian-{epoch_millis(now)}-{kind}"

    intent = {
        "schema_version": "obsidian_intent.v1",
        "intent_id": intent_id,
        "kind": kind,
        "status": "pending",
        "source": "obsidian",
        "surface": surface,
        "created_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "mode": mode or "mentor",
        "note_path": note_path,
        "selected_text_preview": selected_text,
        "goal_ids": normalize_ids(goal_ids),
        "task_ids": normalize_ids(task_ids),
        "execution_policy": PLANNER_EXECUTION_POLICY,
    }

    if message:
        intent["message"] = message
        intent["message_preview"] = clip_text(message, 240)

    if action:
        intent["requested_action"] = action

    return intent


def write_intent(ai_dir: str | Path, intent: dict[str, Any]) -> Path:
    root = Path(ai_dir).expanduser()
    queue = root / "inbox" / "obsidian" / "messages"

    intent_id = str(intent.get("intent_id") or "obsidian-intent")
    kind = str(intent.get("kind") or "message")
    path = queue / f"{intent_id}_{kind}.json"

    atomic_write_json(path, intent)
    return path


def build_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_input_json(args.input)

    message = args.message or str(payload.get("message") or "")
    action = args.action or str(
        payload.get("action") or payload.get("requested_action") or ""
    )
    mode = args.mode or str(payload.get("mode") or "mentor")
    note_path = args.note_path or str(
        payload.get("note_path") or payload.get("active_note_path") or ""
    )
    selected_text = args.selected_text or str(
        payload.get("selected_text") or payload.get("selected_text_preview") or ""
    )
    surface = args.surface or str(payload.get("surface") or "obsidian")

    goal_ids = list(args.goal_id or [])
    goal_ids.extend(payload.get("goal_ids") or payload.get("current_goal_ids") or [])

    task_ids = list(args.task_id or [])
    task_ids.extend(payload.get("task_ids") or [])

    return build_intent(
        message=message,
        action=action,
        mode=mode,
        note_path=note_path,
        selected_text=selected_text,
        goal_ids=goal_ids,
        task_ids=task_ids,
        surface=surface,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write pending Obsidian user intents")
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument("--input", help="Optional JSON payload from Obsidian/Templater")
    parser.add_argument("--message", default="", help="User text message")
    parser.add_argument("--action", default="", help="Requested button/action intent")
    parser.add_argument("--mode", default="mentor")
    parser.add_argument("--surface", default="obsidian")
    parser.add_argument("--note-path", default="")
    parser.add_argument("--selected-text", default="")
    parser.add_argument("--goal-id", action="append", default=[])
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--write", action="store_true", help="Write to inbox")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    intent = build_from_args(args)

    if args.write and not args.dry_run:
        path = write_intent(args.ai_dir, intent)
        print(path)
        return 0

    print(json.dumps(intent, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
