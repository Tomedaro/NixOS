#!/usr/bin/env python3
"""Inspect the phone-visible interaction surface.

This is intentionally read-only. It reports consistency and lifecycle freshness
for materialized phone outbox files without clearing or rewriting state.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_system.interaction_lifecycle import (
    clear_reason_for_active_nudge,
    parse_timestamp_epoch,
)


def read_json(file_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def age_text(value: Any, *, now_epoch: int) -> str:
    parsed = parse_timestamp_epoch(value)
    if parsed is None:
        return "unknown"

    age = max(0, now_epoch - parsed)
    return f"{age}s ({age // 60}m)"


def active_nudge_clear_reason(nudge: dict[str, Any]) -> str:
    if not isinstance(nudge, dict):
        return "none"

    if nudge.get("status") != "active":
        return "none"

    candidate = dict(nudge)
    candidate.setdefault("kind", "nudge")

    reason = clear_reason_for_active_nudge({"active_nudge": candidate})
    return reason or "none"


def status_from_compact(value: Any) -> str:
    if not isinstance(value, dict):
        return "none"

    return str(value.get("status") or "present")


def consistency(
    *,
    state_id: str,
    state_status: str,
    current_id: str,
    current_status: str,
) -> str:
    if state_status == "none" and current_status != "active":
        return "ok_none_active"

    if state_id == current_id and state_status == current_status:
        return "ok_current_matches_state"

    return "WARN_mismatch_current_vs_state"


def main() -> int:
    ai_dir = Path(
        sys.argv[1] if len(sys.argv) > 1 else "/home/daniil/Sync/Perseverance.Gu/AI"
    ).expanduser()
    outbox = ai_dir / "outbox" / "to-phone"

    state_file = outbox / "interaction-state.json"
    nudge_file = outbox / "current-nudge.json"
    question_file = outbox / "current-question.json"

    state = read_json(state_file)
    if not state:
        print(f"interaction_state missing or unreadable: {state_file}")
        return 0

    nudge = read_json(nudge_file)
    question = read_json(question_file)

    now_epoch = int(datetime.now(timezone.utc).timestamp())

    state_updated = state.get("updated_at", "unknown")
    print(
        "interaction_state "
        f"source={state.get('source', 'unknown')} "
        f"mode={state.get('planner_mode', 'unknown')} "
        f"updated_at={state_updated} "
        f"age={age_text(state_updated, now_epoch=now_epoch)}"
    )

    state_nudge = (
        state.get("active_nudge") if isinstance(state.get("active_nudge"), dict) else {}
    )
    state_nudge_id = str(state_nudge.get("nudge_id") or "")
    state_nudge_status = status_from_compact(state.get("active_nudge"))

    current_nudge_id = str(nudge.get("nudge_id") or "")
    current_nudge_status = str(
        nudge.get("status") or ("missing" if not nudge else "unknown")
    )
    current_nudge_created = nudge.get("created_at") or ""
    current_nudge_updated = nudge.get("updated_at") or "unknown"
    clear_reason = active_nudge_clear_reason(nudge)

    print(
        "active_nudge "
        f"state_status={state_nudge_status} "
        f"current_status={current_nudge_status} "
        f"id={current_nudge_id or state_nudge_id} "
        f"source={nudge.get('source', 'unknown' if nudge else 'missing')} "
        f"mode={nudge.get('planner_mode', 'unknown' if nudge else 'missing')} "
        f"created_at={current_nudge_created or 'unknown'} "
        f"age={age_text(current_nudge_created, now_epoch=now_epoch)} "
        f"updated_at={current_nudge_updated} "
        f"stale_reason={clear_reason} "
        f"consistency={consistency(state_id=state_nudge_id, state_status=state_nudge_status, current_id=current_nudge_id, current_status=current_nudge_status)}"
    )

    if clear_reason not in {"none", "unknown"}:
        print(
            "WARN: active_nudge is still materialized active but lifecycle says "
            f"it should clear: {clear_reason}"
        )

    state_question = (
        state.get("active_question")
        if isinstance(state.get("active_question"), dict)
        else {}
    )
    state_question_id = str(state_question.get("question_id") or "")
    state_question_status = status_from_compact(state.get("active_question"))

    current_question_id = str(question.get("question_id") or "")
    current_question_status = str(
        question.get("status") or ("missing" if not question else "unknown")
    )
    current_question_updated = question.get("updated_at") or "unknown"

    print(
        "active_question "
        f"state_status={state_question_status} "
        f"current_status={current_question_status} "
        f"id={current_question_id or state_question_id} "
        f"source={question.get('source', 'unknown' if question else 'missing')} "
        f"mode={question.get('planner_mode', 'unknown' if question else 'missing')} "
        f"updated_at={current_question_updated} "
        f"age={age_text(current_question_updated, now_epoch=now_epoch)} "
        f"consistency={consistency(state_id=state_question_id, state_status=state_question_status, current_id=current_question_id, current_status=current_question_status)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
