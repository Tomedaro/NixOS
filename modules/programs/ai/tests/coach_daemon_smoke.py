#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
COACH = REPO / "modules/programs/ai/coach-daemon/coach.py"


def load_coach(ai_dir: Path):
    os.environ["AI_DIR"] = str(ai_dir)
    os.environ["NOTIFY_SEND"] = "false"
    os.environ["STARTUP_GRACE_SECONDS"] = "0"

    python_lib = str(REPO / "modules/programs/ai/python")
    if python_lib not in sys.path:
        sys.path.insert(0, python_lib)

    name = f"coach_under_test_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, COACH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fresh_aw_event(app: str, title: str) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration": 0,
        "data": {
            "app": app,
            "title": title,
        },
    }


def test_tick_writes_now_logs_events_and_state_from_active_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-coach-smoke-") as tmp:
        ai_dir = Path(tmp) / "AI"
        coach = load_coach(ai_dir)

        write_json(
            ai_dir / "state/session/current.json",
            {
                "session_id": "session-smoke",
                "status": "active",
                "task": "Review Anki",
                "mode": "anki",
            },
        )
        write_json(
            ai_dir / "state/session/current-policy.json",
            {
                "task": "Review Anki",
                "mode": "anki",
                "allowed_apps": ["Anki"],
                "distracting_apps": ["Steam"],
                "allowed_title_keywords": ["Review"],
                "distracting_title_keywords": ["Shorts"],
                "intervention": {"level": 2, "cooldown_seconds": 600},
            },
        )

        coach.find_bucket_id = lambda bucket_type: {
            "currentwindow": "window-bucket",
            "afkstatus": "afk-bucket",
        }.get(bucket_type)

        def fake_latest(bucket_id: str):
            if bucket_id == "window-bucket":
                return fresh_aw_event("Anki", "Review deck")
            if bucket_id == "afk-bucket":
                return {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "duration": 0,
                    "data": {"status": "not-afk"},
                }
            return None

        coach.get_latest_event = fake_latest
        coach.SERVICE_STARTED_AT = time.time() - 999

        coach.tick()

        now_json = read_json(ai_dir / "state/desktop/now.json")
        assert now_json["verdict"] == "on_task"
        assert now_json["task"] == "Review Anki"
        assert now_json["session_id"] == "session-smoke"
        assert now_json["policy_source"].endswith("current-policy.json")

        now_md = (ai_dir / "state/desktop/now.md").read_text(encoding="utf-8")
        assert "Current Desktop Coach Status" in now_md
        assert "Verdict: `on_task`" in now_md

        state = read_json(ai_dir / "state/desktop/coach-state.json")
        assert state["last_seen"]["verdict"] == "on_task"

        event_files = list((ai_dir / "events/desktop").glob("*.jsonl"))
        assert len(event_files) == 1
        events = [
            json.loads(line)
            for line in event_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert events[-1]["event"] == "coach_tick"
        assert events[-1]["verdict"] == "on_task"

        log_files = list((ai_dir / "logs/desktop").glob("*.md"))
        assert len(log_files) == 1
        assert "Verdict: on_task" in log_files[0].read_text(encoding="utf-8")


def test_missing_current_task_creates_default_template() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-coach-smoke-") as tmp:
        ai_dir = Path(tmp) / "AI"
        coach = load_coach(ai_dir)

        task = coach.parse_current_task()

        assert task["exists"] is False
        assert task["task"] == "Study / productive computer work"
        assert (ai_dir / "control/current-task.md").exists()


def test_completed_session_policy_is_not_treated_as_current_intent() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-coach-smoke-") as tmp:
        ai_dir = Path(tmp) / "AI"
        coach = load_coach(ai_dir)

        write_json(
            ai_dir / "state/session/current.json",
            {
                "session_id": "session-old",
                "status": "completed",
                "task": "Stale completed task",
                "mode": "coding",
            },
        )
        write_json(
            ai_dir / "state/session/current-policy.json",
            {
                "task": "Stale completed task",
                "mode": "coding",
                "allowed_apps": ["kitty"],
                "distracting_apps": ["Steam"],
                "intervention": {"level": 2, "cooldown_seconds": 600},
            },
        )

        task = coach.parse_current_task()

        assert task["task"] == "Study / productive computer work"
        assert task["mode"] == "study"
        assert task["session_id"] == ""
        assert task["policy_source"].endswith("control/current-task.md")


def main() -> None:
    tests = [
        test_tick_writes_now_logs_events_and_state_from_active_policy,
        test_missing_current_task_creates_default_template,
        test_completed_session_policy_is_not_treated_as_current_intent,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
