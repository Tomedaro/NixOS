#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.interaction_projection import refresh_interaction_projection


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def active_nudge(created_at: str = "2026-05-05T19:00:00+02:00") -> dict:
    return {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "active",
        "nudge_id": "n-stale",
        "created_at": created_at,
        "updated_at": created_at,
        "source": "llm-planner",
        "planner_mode": "help-now",
        "urgency": "normal",
        "message": "Do one tiny step.",
        "recommended_next_action": "Open Anki.",
        "actions": [
            {"action": "ack_nudge", "label": "Done"},
            {"action": "snooze_nudge", "label": "Not now", "snooze_minutes": 15},
        ],
    }


def write_projection(ai_dir: Path, nudge: dict) -> None:
    outbox = ai_dir / "outbox/to-phone"
    write_json(outbox / "current-nudge.json", nudge)
    write_json(
        outbox / "current-question.json",
        {
            "schema_version": "phone_interaction.v1",
            "kind": "question",
            "status": "inactive",
            "updated_at": nudge["updated_at"],
            "source": "llm-planner",
            "planner_mode": "help-now",
        },
    )
    write_json(
        outbox / "interaction-state.json",
        {
            "schema_version": "phone_interaction_state.v1",
            "updated_at": nudge["updated_at"],
            "source": "llm-planner",
            "planner_mode": "help-now",
            "active_nudge": nudge,
            "active_question": None,
        },
    )


def test_missing_projection_is_nonfatal() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-projection-missing-") as tmp:
        ai_dir = Path(tmp) / "AI"
        result = refresh_interaction_projection(
            ai_dir,
            now_value="2026-05-05T21:10:00+02:00",
        )
        assert result["changed"] is False
        assert result["reason"] == "no_active_nudge"


def test_fresh_active_nudge_is_unchanged() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-projection-fresh-") as tmp:
        ai_dir = Path(tmp) / "AI"
        write_projection(
            ai_dir,
            active_nudge(created_at="2026-05-05T20:45:00+02:00"),
        )

        result = refresh_interaction_projection(
            ai_dir,
            now_value="2026-05-05T21:10:00+02:00",
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert result["changed"] is False
        assert result["reason"] == "active_nudge_still_fresh"
        assert current["status"] == "active"
        assert current["nudge_id"] == "n-stale"


def test_stale_active_nudge_dry_run_does_not_write() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-projection-dry-run-") as tmp:
        ai_dir = Path(tmp) / "AI"
        write_projection(ai_dir, active_nudge())

        result = refresh_interaction_projection(
            ai_dir,
            now_value="2026-05-05T21:10:00+02:00",
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")

        assert result["changed"] is True
        assert result["dry_run"] is True
        assert result["status"] == "would_clear"
        assert result["reason"] == "expired_help-now_nudge"
        assert current["status"] == "active"
        assert state["active_nudge"]["status"] == "active"


def test_stale_active_nudge_write_materializes_inactive() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-projection-write-") as tmp:
        ai_dir = Path(tmp) / "AI"
        write_projection(ai_dir, active_nudge())

        result = refresh_interaction_projection(
            ai_dir,
            write=True,
            now_value="2026-05-05T21:10:00+02:00",
        )

        current = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")
        markdown = (ai_dir / "outbox/to-phone/current-nudge.md").read_text(
            encoding="utf-8"
        )

        assert result["changed"] is True
        assert result["dry_run"] is False
        assert result["status"] == "cleared"
        assert current["status"] == "inactive"
        assert current["last_cleared_nudge"]["reason"] == "expired_help-now_nudge"
        assert state["active_nudge"] is None
        assert state["last_cleared_nudge"]["nudge_id"] == "n-stale"
        assert "Status: inactive" in markdown
        assert "expired_help-now_nudge" in markdown


def main() -> None:
    tests = [
        test_missing_projection_is_nonfatal,
        test_fresh_active_nudge_is_unchanged,
        test_stale_active_nudge_dry_run_does_not_write,
        test_stale_active_nudge_write_materializes_inactive,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
