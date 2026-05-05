#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
TRIGGER = REPO / "modules/programs/ai/recovery-trigger/recovery_trigger.py"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def read_intervention_events(ai_dir: Path) -> list[dict]:
    events = []
    for path in sorted((ai_dir / "events/interventions").glob("*.jsonl")):
        events.extend(read_jsonl(path))
    return events


def run_trigger(ai_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["AI_DIR"] = str(ai_dir)
    env["RECOVERY_TRIGGER_TIMEZONE"] = "Europe/Paris"

    shared_python = str(REPO / "modules/programs/ai/python")
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shared_python if not old_pythonpath else shared_python + ":" + old_pythonpath

    return subprocess.run(
        [sys.executable, str(TRIGGER), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def setup_trigger(ai_dir: Path, *, due: int) -> None:
    write_json(ai_dir / "state/session/current.json", {
        "status": "completed",
        "task": "Smoke task",
    })
    write_json(ai_dir / "state/anki/status.json", {
        "available": True,
        "totals": {
            "due": due,
            "review_due": due,
        },
    })
    write_json(ai_dir / "state/desktop/now.json", {
        "verdict": "idle",
        "app": "kitty",
        "title": "terminal",
    })
    write_json(ai_dir / "state/recovery/current.json", {
        "schema_version": "recovery_session.v1",
        "recovery_id": "trigger-smoke-recovery",
        "status": "expired",
        "updated_at": "2020-01-01T00:00:00+02:00",
    })
    write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
        "status": "inactive",
    })
    write_json(ai_dir / "outbox/to-phone/current-question.json", {
        "status": "inactive",
    })
    write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
        "active_nudge": None,
        "active_question": None,
    })


def assert_ok_or_wrote_nudge(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode in (0, 1), (
        f"trigger failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


def test_trigger_logs_written_nudge_intervention() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-intervention-written-") as tmp:
        ai_dir = Path(tmp) / "AI"
        setup_trigger(ai_dir, due=5)

        proc = run_trigger(ai_dir, "--once")
        assert_ok_or_wrote_nudge(proc)

        summary = json.loads(proc.stdout)
        assert summary["decision"] == "write_nudge"
        assert summary["wrote_nudge"] is True

        events = read_intervention_events(ai_dir)
        names = [event.get("event") for event in events]
        assert names == [
            "intervention_proposed",
            "intervention_gated",
            "intervention_nudge_written",
        ], names

        intervention_ids = {event.get("intervention_id") for event in events}
        assert len(intervention_ids) == 1, intervention_ids

        gated = events[1]
        assert gated["gate_ok"] is True
        assert gated["gate_reason"] == "validated"
        assert gated["wrote_nudge"] is True

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "active"
        assert nudge["intervention_id"] in intervention_ids


def test_trigger_logs_rejected_intervention_without_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-intervention-rejected-") as tmp:
        ai_dir = Path(tmp) / "AI"
        setup_trigger(ai_dir, due=0)

        proc = run_trigger(ai_dir, "--once")
        assert_ok_or_wrote_nudge(proc)

        summary = json.loads(proc.stdout)
        assert summary["decision"] == "skip"
        assert summary["wrote_nudge"] is False

        events = read_intervention_events(ai_dir)
        names = [event.get("event") for event in events]
        assert names == [
            "intervention_proposed",
            "intervention_gated",
        ], names

        gated = events[1]
        assert gated["gate_ok"] is False
        assert gated["gate_reason"] == "write_nudge_blocked"
        assert "anki_not_due" in gated["blocked_reasons"]


def main() -> None:
    tests = [
        test_trigger_logs_written_nudge_intervention,
        test_trigger_logs_rejected_intervention_without_nudge,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
