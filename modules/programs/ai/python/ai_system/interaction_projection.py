"""Deterministic phone interaction projection refresh.

Materialized phone outbox files are projections/views. This module detects when
an active nudge is stale according to shared lifecycle rules and can rewrite the
phone-visible projection to inactive state.

Default CLI mode is dry-run. Use --write for explicit mutation.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ai_system.interaction_lifecycle import (
    clear_reason_for_active_nudge,
    current_epoch,
)
from ai_system.io_utils import atomic_write_json, atomic_write_text, read_json


DEFAULT_AI_DIR = os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")
DEFAULT_TIMEZONE = os.environ.get("AI_TIMEZONE", "Europe/Paris")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_iso(timezone_name: str = DEFAULT_TIMEZONE) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat(timespec="seconds")


def _candidate_active_nudge(
    current_nudge: dict[str, Any],
    interaction_state: dict[str, Any],
) -> dict[str, Any]:
    current = _as_dict(current_nudge)
    if current.get("status") == "active":
        candidate = dict(current)
        candidate.setdefault("kind", "nudge")
        return candidate

    state_nudge = _as_dict(interaction_state.get("active_nudge"))
    if state_nudge.get("status") == "active":
        candidate = dict(state_nudge)
        candidate.setdefault("kind", "nudge")
        return candidate

    return {}


def _compact_question_from_current(current_question: dict[str, Any]) -> dict[str, Any] | None:
    question = _as_dict(current_question)
    if question.get("status") != "active":
        return None

    return {
        "question_id": question.get("question_id", ""),
        "status": question.get("status", "active"),
        "question": question.get("question", ""),
        "answer_options": question.get("answer_options", []),
        "free_text_allowed": question.get("free_text_allowed", True),
        "response_action": question.get("response_action", "answer_question"),
        "dismiss_action": question.get("dismiss_action", "dismiss_question"),
    }


def _inactive_nudge_payload(
    *,
    candidate: dict[str, Any],
    reason: str,
    generated_at: str,
) -> dict[str, Any]:
    marker = {
        "reason": reason,
        "cleared_at": generated_at,
        "nudge_id": candidate.get("nudge_id", ""),
    }

    return {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "inactive",
        "updated_at": generated_at,
        "source": "interaction-projection",
        "previous_source": candidate.get("source", ""),
        "planner_mode": candidate.get("planner_mode", "unknown"),
        "message": "No current nudge.",
        "recommended_next_action": "",
        "last_cleared_nudge": marker,
    }


def _inactive_nudge_markdown(payload: dict[str, Any]) -> str:
    marker = _as_dict(payload.get("last_cleared_nudge"))
    lines = [
        "# Current Nudge",
        "",
        "Status: inactive",
        "Message: No current nudge.",
        f"Updated: {payload.get('updated_at', '')}",
        f"Planner mode: {payload.get('planner_mode', 'unknown')}",
        "",
    ]

    if marker:
        lines.extend(
            [
                "## Last cleared nudge",
                "",
                f"Reason: `{marker.get('reason', '')}`",
                f"Nudge ID: `{marker.get('nudge_id', '')}`",
                f"Cleared at: {marker.get('cleared_at', '')}",
                "",
            ]
        )

    return "\n".join(lines)


def build_refreshed_projection(
    *,
    current_nudge: dict[str, Any],
    current_question: dict[str, Any],
    interaction_state: dict[str, Any],
    now_value: Any | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or (
        str(now_value) if isinstance(now_value, str) else _now_iso()
    )

    candidate = _candidate_active_nudge(current_nudge, interaction_state)
    if not candidate:
        return {
            "schema_version": "interaction_projection_refresh.v1",
            "status": "unchanged",
            "reason": "no_active_nudge",
            "changed": False,
            "generated_at": generated_at,
        }

    clear_reason = clear_reason_for_active_nudge(
        {"active_nudge": candidate},
        now=now_value or generated_at,
    )
    if not clear_reason:
        return {
            "schema_version": "interaction_projection_refresh.v1",
            "status": "unchanged",
            "reason": "active_nudge_still_fresh",
            "changed": False,
            "generated_at": generated_at,
            "nudge_id": candidate.get("nudge_id", ""),
        }

    inactive_nudge = _inactive_nudge_payload(
        candidate=candidate,
        reason=clear_reason,
        generated_at=generated_at,
    )

    state = dict(_as_dict(interaction_state))
    state.setdefault("schema_version", "phone_interaction_state.v1")
    state["updated_at"] = generated_at
    state["source"] = "interaction-projection"
    state["previous_source"] = interaction_state.get("source", "")
    state["planner_mode"] = (
        interaction_state.get("planner_mode")
        or candidate.get("planner_mode")
        or "unknown"
    )
    state["active_nudge"] = None

    if "active_question" not in state:
        state["active_question"] = _compact_question_from_current(current_question)

    state["last_cleared_nudge"] = inactive_nudge["last_cleared_nudge"]

    return {
        "schema_version": "interaction_projection_refresh.v1",
        "status": "would_clear",
        "reason": clear_reason,
        "changed": True,
        "generated_at": generated_at,
        "nudge_id": candidate.get("nudge_id", ""),
        "current_nudge": inactive_nudge,
        "current_nudge_md": _inactive_nudge_markdown(inactive_nudge),
        "interaction_state": state,
        "cleared_at_epoch": current_epoch(now_value or generated_at),
    }


def refresh_interaction_projection(
    ai_dir: Path,
    *,
    write: bool = False,
    now_value: Any | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ai_dir = Path(ai_dir)
    outbox = ai_dir / "outbox" / "to-phone"

    current_nudge_path = outbox / "current-nudge.json"
    current_nudge_md_path = outbox / "current-nudge.md"
    current_question_path = outbox / "current-question.json"
    interaction_state_path = outbox / "interaction-state.json"

    result = build_refreshed_projection(
        current_nudge=_as_dict(read_json(current_nudge_path, {})),
        current_question=_as_dict(read_json(current_question_path, {})),
        interaction_state=_as_dict(read_json(interaction_state_path, {})),
        now_value=now_value,
        generated_at=generated_at,
    )

    result["dry_run"] = not write
    result["paths"] = {
        "current_nudge": str(current_nudge_path),
        "current_nudge_md": str(current_nudge_md_path),
        "interaction_state": str(interaction_state_path),
    }

    if not result.get("changed"):
        return result

    if write:
        atomic_write_json(current_nudge_path, result["current_nudge"])
        atomic_write_text(current_nudge_md_path, result["current_nudge_md"])
        atomic_write_json(interaction_state_path, result["interaction_state"])
        result["status"] = "cleared"

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh stale phone interaction materialized projections."
    )
    parser.add_argument("--ai-dir", default=DEFAULT_AI_DIR)
    parser.add_argument("--write", action="store_true", help="write refreshed projection")
    parser.add_argument(
        "--now",
        default=None,
        help="timestamp used for deterministic tests/debugging; defaults to current time",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = refresh_interaction_projection(
        Path(args.ai_dir),
        write=args.write,
        now_value=args.now,
        generated_at=args.now,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
