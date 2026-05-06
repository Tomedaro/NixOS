#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HELPER = REPO_ROOT / "modules/programs/ai/dev/interaction_surface.py"
PYTHON_LIB = REPO_ROOT / "modules/programs/ai/python"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_helper(ai_dir: Path) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{PYTHON_LIB}{os.pathsep}{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(PYTHON_LIB)
    )

    result = subprocess.run(
        [sys.executable, str(HELPER), str(ai_dir)],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return result.stdout


def test_stale_active_nudge_is_reported() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-surface-") as tmp:
        ai_dir = Path(tmp) / "AI"
        outbox = ai_dir / "outbox/to-phone"

        now = datetime.now(timezone.utc).replace(microsecond=0)
        stale_created = (now - timedelta(hours=2)).isoformat()

        nudge = {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-stale",
            "created_at": stale_created,
            "updated_at": stale_created,
            "source": "llm-planner",
            "planner_mode": "help-now",
            "urgency": "normal",
            "message": "Do one tiny step.",
            "recommended_next_action": "Open Anki.",
            "actions": [],
        }

        write_json(outbox / "current-nudge.json", nudge)
        write_json(
            outbox / "current-question.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "question",
                "status": "inactive",
                "updated_at": now.isoformat(),
                "source": "llm-planner",
                "planner_mode": "help-now",
            },
        )
        write_json(
            outbox / "interaction-state.json",
            {
                "schema_version": "phone_interaction_state.v1",
                "updated_at": now.isoformat(),
                "source": "llm-planner",
                "planner_mode": "help-now",
                "active_nudge": nudge,
                "active_question": None,
            },
        )

        output = run_helper(ai_dir)

        assert "interaction_state source=llm-planner mode=help-now" in output
        assert (
            "active_nudge state_status=active current_status=active id=n-stale"
            in output
        )
        assert "stale_reason=expired_help-now_nudge" in output
        assert "WARN: active_nudge is still materialized active" in output
        assert "active_question state_status=none current_status=inactive" in output


def test_missing_interaction_state_is_nonfatal() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-interaction-surface-missing-") as tmp:
        ai_dir = Path(tmp) / "AI"
        output = run_helper(ai_dir)
        assert "interaction_state missing or unreadable:" in output


def test_active_nudge_missing_state_id_warns() -> None:
    with tempfile.TemporaryDirectory(
        prefix="ai-interaction-surface-missing-id-"
    ) as tmp:
        ai_dir = Path(tmp) / "AI"
        outbox = ai_dir / "outbox/to-phone"

        now = datetime.now(timezone.utc).replace(microsecond=0)
        nudge = {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-current",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "source": "llm-planner",
            "planner_mode": "help-now",
            "urgency": "normal",
            "message": "Do one tiny step.",
            "recommended_next_action": "Open Anki.",
            "actions": [],
        }

        write_json(outbox / "current-nudge.json", nudge)
        write_json(
            outbox / "current-question.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "question",
                "status": "inactive",
                "updated_at": now.isoformat(),
                "source": "llm-planner",
                "planner_mode": "help-now",
            },
        )
        write_json(
            outbox / "interaction-state.json",
            {
                "schema_version": "phone_interaction_state.v1",
                "updated_at": now.isoformat(),
                "source": "llm-planner",
                "planner_mode": "help-now",
                "active_nudge": {
                    "schema_version": "phone_interaction.v1",
                    "kind": "nudge",
                    "status": "active",
                },
                "active_question": None,
            },
        )

        output = run_helper(ai_dir)

        assert "active_nudge state_status=active current_status=active" in output
        assert "consistency=WARN_mismatch_current_vs_state" in output


def run_all() -> None:
    tests = [
        test_stale_active_nudge_is_reported,
        test_missing_interaction_state_is_nonfatal,
        test_active_nudge_missing_state_id_warns,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
