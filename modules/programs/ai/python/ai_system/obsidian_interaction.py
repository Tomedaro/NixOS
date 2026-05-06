"""Obsidian-facing interaction helpers.

This module is intentionally pure except for explicit write_current_interaction.
It defines the stable Obsidian interaction contract used by future Templater,
TaskNotes, and desktop/phone bridge clients.

Design boundary:
- build/normalize/render interactions here
- do not execute user actions here
- do not edit arbitrary vault notes here
- route user commands through inbox files and action bridges
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text

SCHEMA_INTERACTION = "obsidian_interaction.v1"
SCHEMA_MESSAGE = "obsidian_message.v1"
SCHEMA_ACTION = "obsidian_action.v1"

DEFAULT_SOURCE = "local-ai"
DEFAULT_SURFACE = "obsidian"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str, *, now_epoch: int | None = None) -> str:
    now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
    return f"{prefix}-{now_epoch}"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_action(action: Any) -> dict[str, Any]:
    action = _as_dict(action)
    name = _clean_text(action.get("action"))
    label = _clean_text(action.get("label")) or name

    normalized = {
        "action": name,
        "label": label,
    }

    for key in (
        "interaction_id",
        "nudge_id",
        "question_id",
        "snooze_minutes",
        "target_id",
        "target_name",
        "requires_approval",
    ):
        if key in action:
            normalized[key] = action.get(key)

    return normalized


def normalize_interaction(
    payload: Any, *, generated_at: str | None = None
) -> dict[str, Any]:
    payload = _as_dict(payload)
    generated_at = generated_at or now_iso()

    status = _clean_text(payload.get("status")) or "inactive"
    kind = _clean_text(payload.get("kind")) or (
        "inactive" if status != "active" else "message"
    )

    interaction_id = _clean_text(payload.get("interaction_id"))
    if status == "active" and not interaction_id:
        interaction_id = new_id("oi")

    actions = [
        normalized
        for normalized in (
            normalize_action(item) for item in _as_list(payload.get("actions"))
        )
        if normalized.get("action")
    ]

    return {
        "schema_version": SCHEMA_INTERACTION,
        "kind": kind,
        "status": status,
        "interaction_id": interaction_id,
        "created_at": payload.get("created_at") or generated_at,
        "updated_at": payload.get("updated_at") or generated_at,
        "source": _clean_text(payload.get("source")) or DEFAULT_SOURCE,
        "planner_mode": _clean_text(payload.get("planner_mode")) or "conversation",
        "urgency": _clean_text(payload.get("urgency")) or "normal",
        "title": _clean_text(payload.get("title")),
        "body": _clean_text(payload.get("body") or payload.get("message")),
        "recommended_next_action": _clean_text(payload.get("recommended_next_action")),
        "reason": _clean_text(payload.get("reason")),
        "answer_options": _as_list(payload.get("answer_options")),
        "free_text_allowed": bool(payload.get("free_text_allowed", True)),
        "actions": actions,
        "response_targets": {
            "messages_dir": "AI/inbox/from-obsidian/messages",
            "actions_dir": "AI/inbox/from-obsidian/actions",
        },
    }


def inactive_interaction(
    *, generated_at: str | None = None, source: str = DEFAULT_SOURCE
) -> dict[str, Any]:
    generated_at = generated_at or now_iso()
    return normalize_interaction(
        {
            "kind": "inactive",
            "status": "inactive",
            "source": source,
            "title": "No active interaction",
            "body": "",
            "free_text_allowed": True,
            "actions": [],
            "created_at": generated_at,
            "updated_at": generated_at,
        },
        generated_at=generated_at,
    )


def interaction_from_phone_nudge(
    nudge: Any, *, generated_at: str | None = None
) -> dict[str, Any]:
    nudge = _as_dict(nudge)
    generated_at = generated_at or now_iso()

    return normalize_interaction(
        {
            "kind": "nudge",
            "status": nudge.get("status", "active"),
            "interaction_id": nudge.get("nudge_id") or nudge.get("interaction_id"),
            "created_at": nudge.get("created_at") or generated_at,
            "updated_at": nudge.get("updated_at") or generated_at,
            "source": nudge.get("source", "phone-interaction"),
            "planner_mode": nudge.get("planner_mode", "unknown"),
            "urgency": nudge.get("urgency", "normal"),
            "title": "Nudge",
            "body": nudge.get("message", ""),
            "recommended_next_action": nudge.get("recommended_next_action", ""),
            "actions": nudge.get("actions", []),
            "free_text_allowed": True,
        },
        generated_at=generated_at,
    )


def markdown_for_interaction(interaction: Any) -> str:
    data = normalize_interaction(interaction)

    lines: list[str] = [
        "---",
        f"schema_version: {data['schema_version']}",
        f"interaction_id: {data['interaction_id']}",
        f"kind: {data['kind']}",
        f"status: {data['status']}",
        f"source: {data['source']}",
        f"planner_mode: {data['planner_mode']}",
        f"updated_at: {data['updated_at']}",
        "---",
        "",
        "# Current AI Interaction",
        "",
        f"Status: `{data['status']}`",
        f"Kind: `{data['kind']}`",
        f"Urgency: `{data['urgency']}`",
        "",
    ]

    if data["title"]:
        lines.extend(["## Title", "", data["title"], ""])

    if data["body"]:
        lines.extend(["## Message", "", data["body"], ""])

    if data["recommended_next_action"]:
        lines.extend(
            [
                "## Recommended next action",
                "",
                data["recommended_next_action"],
                "",
            ]
        )

    if data["reason"]:
        lines.extend(["## Reason", "", data["reason"], ""])

    if data["answer_options"]:
        lines.extend(["## Answer options", ""])
        for option in data["answer_options"]:
            option = _as_dict(option)
            option_id = _clean_text(option.get("id"))
            label = _clean_text(option.get("label"))
            lines.append(f"- `{option_id}` — {label}")
        lines.append("")

    if data["actions"]:
        lines.extend(["## Actions", ""])
        for action in data["actions"]:
            lines.append(f"- `{action.get('action', '')}` — {action.get('label', '')}")
        lines.append("")

    lines.extend(
        [
            "## Reply",
            "",
            f"Free text allowed: `{str(data['free_text_allowed']).lower()}`",
            "",
            "Write text messages to `AI/inbox/from-obsidian/messages/*.json`.",
            "Write button/action responses to `AI/inbox/from-obsidian/actions/*.json`.",
            "",
        ]
    )

    return "\n".join(lines)


def write_current_interaction(ai_dir: Path, interaction: Any) -> dict[str, Any]:
    ai_dir = Path(ai_dir).expanduser()
    outbox = ai_dir / "outbox" / "to-obsidian"
    outbox.mkdir(parents=True, exist_ok=True)

    data = normalize_interaction(interaction)
    atomic_write_json(outbox / "current-interaction.json", data)
    atomic_write_text(outbox / "current-interaction.md", markdown_for_interaction(data))
    return data


def make_message_payload(
    text: str,
    *,
    conversation_id: str = "default",
    source: str = DEFAULT_SURFACE,
    created_at: str | None = None,
) -> dict[str, Any]:
    created_at = created_at or now_iso()
    return {
        "schema_version": SCHEMA_MESSAGE,
        "message_id": new_id("om"),
        "created_at": created_at,
        "source": source,
        "surface": DEFAULT_SURFACE,
        "conversation_id": conversation_id,
        "text": _clean_text(text),
    }


def make_action_payload(
    action: str,
    *,
    interaction_id: str = "",
    source: str = DEFAULT_SURFACE,
    created_at: str | None = None,
    **payload: Any,
) -> dict[str, Any]:
    created_at = created_at or now_iso()
    return {
        "schema_version": SCHEMA_ACTION,
        "action_id": new_id("oa"),
        "created_at": created_at,
        "source": source,
        "surface": DEFAULT_SURFACE,
        "interaction_id": interaction_id,
        "action": _clean_text(action),
        "payload": payload,
    }
