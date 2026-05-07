#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
DIALOG_BRIDGE = REPO / "modules/programs/ai/dialog-bridge/dialog_bridge.py"


def run_dialog_bridge(ai_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["AI_DIR"] = str(ai_dir)
    env["TRIGGER_PLANNER_ON_ANSWER"] = "0"
    env["NOTIFY_SEND"] = "false"
    env["PYTHONPATH"] = str(REPO / "modules/programs/ai/python") + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    return subprocess.run(
        [sys.executable, str(DIALOG_BRIDGE)],
        cwd=str(REPO),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_no_pending_question_writes_inactive_markdown() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-dialog-smoke-") as tmp:
        ai_dir = Path(tmp) / "AI"

        proc = run_dialog_bridge(ai_dir)

        assert (
            proc.returncode == 0
        ), f"dialog bridge failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        assert "no pending question" in proc.stdout

        current_question = ai_dir / "outbox/to-phone/current-question.md"
        assert current_question.exists()

        text = current_question.read_text(encoding="utf-8")
        assert "Status: inactive" in text
        assert "Reason: no pending question" in text


def main() -> None:
    tests = [
        test_no_pending_question_writes_inactive_markdown,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
