#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
REPORTER = REPO / "modules/programs/ai/intervention-outcomes/intervention_outcomes_reporter.py"


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def event(name: str, intervention_id: str, epoch: int, **extra) -> dict:
    out = {
        "schema_version": "event.v1",
        "event": name,
        "event_type": name,
        "intervention_id": intervention_id,
        "intervention_kind": "recovery_nudge",
        "target_id": "anki",
        "target_name": "Anki",
        "nudge_id": f"n-{intervention_id}",
        "timestamp_epoch": epoch,
        "timestamp": "2026-05-05T10:00:00+02:00",
        "processed_at": "2026-05-05T10:00:00+02:00",
        "source": "smoke",
        "device": "local",
    }
    out.update(extra)
    return out


def run_reporter(ai_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["AI_DIR"] = str(ai_dir)
    env["INTERVENTION_OUTCOMES_TIMEZONE"] = "Europe/Paris"

    shared_python = str(REPO / "modules/programs/ai/python")
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shared_python if not old_pythonpath else shared_python + ":" + old_pythonpath

    return subprocess.run(
        [sys.executable, str(REPORTER), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def assert_ok(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, (
        f"reporter failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


def setup_events(ai_dir: Path) -> None:
    date = today()

    write_jsonl(ai_dir / f"events/interventions/{date}.jsonl", [
        event("intervention_proposed", "i-success", 100),
        event("intervention_gated", "i-success", 101, gate_ok=True, gate_reason="validated", wrote_nudge=True),
        event("intervention_nudge_written", "i-success", 102, wrote_nudge=True),
        event("intervention_proposed", "i-blocked", 200),
        event("intervention_gated", "i-blocked", 201, gate_ok=False, gate_reason="write_nudge_blocked", wrote_nudge=False),
    ])

    write_jsonl(ai_dir / f"events/actions/{date}.jsonl", [
        event("recovery_started", "i-success", 110, device="phone"),
    ])

    write_jsonl(ai_dir / f"events/recovery/{date}.jsonl", [
        event("recovery_possible_success", "i-success", 500, status="possible_success", reason="observed_target_dwell_reached_success_threshold"),
    ])


def test_dry_run_does_not_write_state() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-intervention-reporter-dry-") as tmp:
        ai_dir = Path(tmp) / "AI"
        setup_events(ai_dir)

        proc = run_reporter(ai_dir, "--days", "1")
        assert_ok(proc)

        payload = json.loads(proc.stdout)
        assert payload["dry_run"] is True
        assert payload["report"]["stats"]["total"] == 2
        assert not (ai_dir / "state/interventions/current.json").exists()


def test_write_report_outputs_state() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-intervention-reporter-write-") as tmp:
        ai_dir = Path(tmp) / "AI"
        setup_events(ai_dir)

        proc = run_reporter(ai_dir, "--days", "1", "--write")
        assert_ok(proc)

        summary = json.loads(proc.stdout)
        assert summary["wrote"] is True
        assert summary["total"] == 2

        current = read_json(ai_dir / "state/interventions/current.json")
        stats = read_json(ai_dir / "state/interventions/stats.json")
        status_md = (ai_dir / "state/interventions/status.md").read_text(encoding="utf-8")

        assert current["schema_version"] == "intervention_outcome_report.v1"
        assert current["stats"]["total"] == 2
        assert stats["by_outcome"]["possible_success"] == 1
        assert stats["by_outcome"]["not_shown"] == 1
        assert "Intervention Outcomes" in status_md
        assert "possible_success" in status_md
        assert "not_shown" in status_md


def main() -> None:
    tests = [
        test_dry_run_does_not_write_state,
        test_write_report_outputs_state,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
