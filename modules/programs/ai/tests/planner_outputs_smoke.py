#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from datetime import timezone
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/llm-planner/python"))
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_planner.outputs import write_machine_outputs


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def config(ai_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        outbox_to_phone_dir=ai_dir / "outbox/to-phone",
        state_llm_dir=ai_dir / "state/llm",
        planner_mode="help-now",
        timezone=timezone.utc,
    )


def planner_result(*, generated_at: str, enabled: bool = True, message: str = "Do one tiny step.") -> dict:
    return {
        "_metadata": {
            "generated_at": generated_at,
            "model": "smoke",
        },
        "recommended_next_action": "Open Anki and do 5 cards.",
        "phone_nudge": {
            "enabled": enabled,
            "urgency": "normal",
            "message": message,
        },
        "ask_user": {
            "enabled": False,
        },
    }


def active_nudge(
    *,
    nudge_id: str,
    created_at: str,
    updated_at: str,
    message: str = "Do one tiny step.",
) -> dict:
    return {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "active",
        "nudge_id": nudge_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "source": "llm-planner",
        "planner_mode": "help-now",
        "urgency": "normal",
        "message": message,
        "recommended_next_action": "Open Anki and do 5 cards.",
        "actions": [
            {"action": "ack_nudge", "label": "Done"},
            {"action": "snooze_nudge", "label": "Not now", "snooze_minutes": 15},
        ],
    }


def write_existing_active_nudge(ai_dir: Path, nudge: dict, *, compact_missing_times: bool = False) -> None:
    write_json(ai_dir / "outbox/to-phone/current-nudge.json", nudge)

    compact = {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "nudge_id": nudge["nudge_id"],
        "status": "active",
        "source": "llm-planner",
        "planner_mode": "help-now",
        "urgency": "normal",
        "message": nudge["message"],
        "recommended_next_action": nudge["recommended_next_action"],
        "actions": nudge["actions"],
    }

    if not compact_missing_times:
        compact["created_at"] = nudge["created_at"]
        compact["updated_at"] = nudge["updated_at"]

    write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
        "schema_version": "phone_interaction_state.v1",
        "updated_at": nudge["updated_at"],
        "source": "llm-planner",
        "planner_mode": "help-now",
        "active_nudge": compact,
        "active_question": None,
    })


def test_fresh_active_nudge_is_reused() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-planner-outputs-fresh-") as tmp:
        ai_dir = Path(tmp) / "AI"
        old = active_nudge(
            nudge_id="n-fresh",
            created_at="2026-05-05T20:30:00+02:00",
            updated_at="2026-05-05T20:35:00+02:00",
        )
        write_existing_active_nudge(ai_dir, old)

        write_machine_outputs(
            config(ai_dir),
            planner_result(generated_at="2026-05-05T20:45:00+02:00"),
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")

        assert current["status"] == "active"
        assert current["nudge_id"] == "n-fresh"
        assert current["created_at"] == "2026-05-05T20:30:00+02:00"
        assert state["active_nudge"]["nudge_id"] == "n-fresh"
        assert state["active_nudge"]["created_at"] == "2026-05-05T20:30:00+02:00"
        assert "last_cleared_nudge" not in state


def test_stale_active_nudge_is_materialized_inactive_when_no_new_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-planner-outputs-stale-inactive-") as tmp:
        ai_dir = Path(tmp) / "AI"
        old = active_nudge(
            nudge_id="n-stale",
            created_at="2026-05-05T19:00:00+02:00",
            updated_at="2026-05-05T21:10:00+02:00",
        )
        write_existing_active_nudge(ai_dir, old, compact_missing_times=True)

        write_machine_outputs(
            config(ai_dir),
            planner_result(
                generated_at="2026-05-05T21:10:00+02:00",
                enabled=False,
            ),
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")

        assert current["status"] == "inactive"
        assert current["last_cleared_nudge"]["reason"] == "expired_help-now_nudge"
        assert state["active_nudge"] is None
        assert state["last_cleared_nudge"]["reason"] == "expired_help-now_nudge"
        assert state["last_cleared_nudge"]["cleared_at"] == "2026-05-05T21:10:00+02:00"


def test_stale_matching_nudge_is_not_reused_for_new_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-planner-outputs-stale-replace-") as tmp:
        ai_dir = Path(tmp) / "AI"
        old = active_nudge(
            nudge_id="n-stale",
            created_at="2026-05-05T19:00:00+02:00",
            updated_at="2026-05-05T21:10:00+02:00",
        )
        write_existing_active_nudge(ai_dir, old, compact_missing_times=True)

        write_machine_outputs(
            config(ai_dir),
            planner_result(generated_at="2026-05-05T21:10:00+02:00"),
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")

        assert current["status"] == "active"
        assert current["nudge_id"] != "n-stale"
        assert current["created_at"] == "2026-05-05T21:10:00+02:00"
        assert state["active_nudge"]["nudge_id"] == current["nudge_id"]
        assert state["active_nudge"]["created_at"] == "2026-05-05T21:10:00+02:00"
        assert state["last_cleared_nudge"]["reason"] == "expired_help-now_nudge"


def main() -> None:
    tests = [
        test_fresh_active_nudge_is_reused,
        test_stale_active_nudge_is_materialized_inactive_when_no_new_nudge,
        test_stale_matching_nudge_is_not_reused_for_new_nudge,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
