#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SESSION_MANAGER = REPO / "modules/programs/ai/session-manager/session_manager.py"


def run_ai_session(ai_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["AI_DIR"] = str(ai_dir)
    env["PYTHONPATH"] = str(REPO / "modules/programs/ai/python") + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    return subprocess.run(
        [sys.executable, str(SESSION_MANAGER), *args],
        cwd=str(REPO),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_ok(proc: subprocess.CompletedProcess) -> None:
    assert (
        proc.returncode == 0
    ), f"ai-session failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


def desktop_events(ai_dir: Path) -> list[dict]:
    events = []
    for path in sorted((ai_dir / "events/desktop").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def test_start_and_end_session_writes_state_control_archive_and_events() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-session-smoke-") as tmp:
        ai_dir = Path(tmp) / "AI"

        start = run_ai_session(
            ai_dir,
            "start",
            "--task",
            "Review 10 Anki cards",
            "--mode",
            "anki",
            "--project",
            "Language",
            "--duration",
            "10",
            "--allow-app",
            "anki-helper",
            "--distract-domain",
            "example.com",
        )
        assert_ok(start)
        assert "started session:" in start.stdout

        current = read_json(ai_dir / "state/session/current.json")
        policy = read_json(ai_dir / "state/session/current-policy.json")

        assert current["status"] == "active"
        assert current["task"] == "Review 10 Anki cards"
        assert current["mode"] == "anki"
        assert current["project"] == "Language"
        assert current["duration_minutes"] == 10

        assert policy["task"] == "Review 10 Anki cards"
        assert policy["mode"] == "anki"
        assert "anki-helper" in policy["allowed_apps"]
        assert "example.com" in policy["distracting_domains"]

        assert "Review 10 Anki cards" in (ai_dir / "control/current-task.md").read_text(
            encoding="utf-8"
        )
        assert "Mode: anki" in (ai_dir / "control/current-mode.md").read_text(
            encoding="utf-8"
        )
        assert current["session_id"] in (ai_dir / "control/current-block.md").read_text(
            encoding="utf-8"
        )
        assert "Review 10 Anki cards" in (
            ai_dir / "state/session/current-policy.md"
        ).read_text(encoding="utf-8")

        events = desktop_events(ai_dir)
        assert any(event.get("event") == "session_started" for event in events)

        end = run_ai_session(
            ai_dir,
            "end",
            "--status",
            "completed",
            "--reason",
            "smoke done",
        )
        assert_ok(end)
        assert "ended session:" in end.stdout

        ended = read_json(ai_dir / "state/session/current.json")
        assert ended["session_id"] == current["session_id"]
        assert ended["status"] == "completed"
        assert ended["end_reason"] == "smoke done"

        archives = list(
            (ai_dir / "state/session/archive").glob(f"*/{current['session_id']}.json")
        )
        assert len(archives) == 1
        archived = read_json(archives[0])
        assert archived["status"] == "completed"

        block = (ai_dir / "control/current-block.md").read_text(encoding="utf-8")
        assert "Status: completed" in block
        assert "Reason: smoke done" in block

        events = desktop_events(ai_dir)
        assert any(event.get("event") == "session_ended" for event in events)


def main() -> None:
    tests = [
        test_start_and_end_session_writes_state_control_archive_and_events,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
