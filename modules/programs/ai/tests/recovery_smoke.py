#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[4]
MANAGER = REPO / "modules/programs/ai/recovery-manager/recovery_manager.py"
TRIGGER = REPO / "modules/programs/ai/recovery-trigger/recovery_trigger.py"
TZ = ZoneInfo("Europe/Paris")


def iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=TZ).isoformat(timespec="seconds")


def day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=TZ).strftime("%Y-%m-%d")


def clock(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=TZ).strftime("%H:%M:%S")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items),
        encoding="utf-8",
    )


def run_script(script: Path, ai_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["AI_DIR"] = str(ai_dir)
    env["RECOVERY_MANAGER_TIMEZONE"] = "Europe/Paris"
    env["RECOVERY_TRIGGER_TIMEZONE"] = "Europe/Paris"

    shared_python = str(REPO / "modules/programs/ai/python")
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shared_python if not old_pythonpath else shared_python + ":" + old_pythonpath

    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def run_json(script: Path, ai_dir: Path, *args: str) -> dict:
    proc = run_script(script, ai_dir, *args)
    if proc.returncode not in (0, 1):
        raise AssertionError(f"{script.name} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

    try:
        return json.loads(proc.stdout)
    except Exception as error:
        raise AssertionError(
            f"could not parse JSON from {script.name}: {error}\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        ) from error


def phone_event(kind: str, epoch: int) -> dict:
    return {
        "schema_version": "event.v1",
        "source": "test",
        "device": "phone",
        "event": kind,
        "event_type": kind,
        "timestamp": iso(epoch),
        "timestamp_epoch": epoch,
        "date": day(epoch),
        "time": clock(epoch),
        "processed_at": iso(epoch),
        "raw_file": f"synthetic/{epoch}_{kind}.json",
        "message": f"Synthetic {kind}",
    }


def recovery_state(start_epoch: int, status: str = "active") -> dict:
    return {
        "schema_version": "recovery_session.v1",
        "recovery_id": f"recovery-anki-smoke-{start_epoch}",
        "status": status,
        "started_at": iso(start_epoch),
        "updated_at": iso(start_epoch),
        "source": "test",
        "device": "phone",
        "action_id": "smoke-test",
        "target": {
            "target_id": "anki",
            "name": "Anki",
            "kind": "app",
            "android_package": "com.ichi2.anki",
        },
        "goal": {
            "text": "5 minutes in AnkiDroid",
            "stop_condition": "Stay in AnkiDroid for 5 minutes, then stop.",
        },
        "launch": {
            "requested": True,
            "android_package": "com.ichi2.anki",
            "handled_by": "tasker",
        },
        "last_event": {
            "schema_version": "event.v1",
            "source": "test",
            "device": "phone",
            "action": "start_recovery_target",
            "event": "recovery_started",
            "event_type": "recovery_started",
            "timestamp": iso(start_epoch),
            "timestamp_epoch": start_epoch,
            "date": day(start_epoch),
            "time": clock(start_epoch),
            "processed_at": iso(start_epoch),
            "recovery_id": f"recovery-anki-smoke-{start_epoch}",
            "target_id": "anki",
            "target_name": "Anki",
        },
    }


def setup_manager(ai_dir: Path, recovery: dict, events: list[dict]) -> None:
    write_json(ai_dir / "state/recovery/current.json", recovery)
    append_jsonl(ai_dir / f"events/phone/{day(int(time.time()))}.jsonl", events)


def manager_status(ai_dir: Path) -> dict:
    return run_json(MANAGER, ai_dir, "--dry-run")["recovery"]


def test_manager_fresh_quick_exit() -> None:
    now = int(time.time())
    start = now - 120
    setup_manager(
        Path(os.environ["TEST_AI_DIR"]),
        recovery_state(start),
        [phone_event("opened_ankidroid", now - 100), phone_event("closed_ankidroid", now - 70)],
    )
    recovery = manager_status(Path(os.environ["TEST_AI_DIR"]))
    assert recovery["status"] == "observing", recovery["status"]
    assert recovery["lifecycle"]["rapid_exit_detected"] is True


def test_manager_old_quick_exit() -> None:
    now = int(time.time())
    start = now - 1200
    setup_manager(
        Path(os.environ["TEST_AI_DIR"]),
        recovery_state(start),
        [phone_event("opened_ankidroid", start + 10), phone_event("closed_ankidroid", start + 46)],
    )
    recovery = manager_status(Path(os.environ["TEST_AI_DIR"]))
    assert recovery["status"] == "possible_abort", recovery["status"]
    assert recovery["lifecycle"]["rapid_exit_detected"] is True


def test_manager_success_still_open() -> None:
    now = int(time.time())
    start = now - 600
    setup_manager(
        Path(os.environ["TEST_AI_DIR"]),
        recovery_state(start),
        [phone_event("opened_ankidroid", start + 10)],
    )
    recovery = manager_status(Path(os.environ["TEST_AI_DIR"]))
    assert recovery["status"] == "possible_success", recovery["status"]
    assert recovery["lifecycle"]["total_observed_dwell_seconds"] >= 300


def test_manager_terminal_no_churn() -> None:
    now = int(time.time())
    start = now - 900
    ai_dir = Path(os.environ["TEST_AI_DIR"])
    state = recovery_state(start, status="possible_success")
    state["classification"] = {
        "status": "possible_success",
        "previous_status": "active",
        "reason": "observed_target_dwell_reached_success_threshold",
        "classified_at": iso(now - 300),
    }
    setup_manager(ai_dir, state, [phone_event("opened_ankidroid", start + 1)])

    status_path = ai_dir / "state/recovery/status.md"
    events_path = ai_dir / f"events/recovery/{day(now)}.jsonl"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("sentinel\n", encoding="utf-8")
    append_jsonl(events_path, [{"event": "sentinel"}])

    current_path = ai_dir / "state/recovery/current.json"
    before_current = current_path.stat().st_mtime_ns
    before_status = status_path.stat().st_mtime_ns
    before_events = events_path.read_text(encoding="utf-8")

    proc = run_script(MANAGER, ai_dir, "--once")
    assert proc.returncode == 0, proc.stderr
    assert "terminal_status_unchanged" in proc.stdout

    assert current_path.stat().st_mtime_ns == before_current
    assert status_path.stat().st_mtime_ns == before_status
    assert events_path.read_text(encoding="utf-8") == before_events


def setup_trigger(ai_dir: Path, *, due: int, nudge_active=False, question_active=False, recovery_status="expired", snooze_now=False, session_active=False) -> None:
    now = int(time.time())

    write_json(ai_dir / "state/session/current.json", {
        "status": "active" if session_active else "completed",
        "task": "Smoke task",
    })
    write_json(ai_dir / "state/anki/status.json", {
        "available": True,
        "totals": {"due": due, "review_due": due},
    })
    write_json(ai_dir / "state/desktop/now.json", {
        "verdict": "idle",
        "app": "kitty",
        "title": "terminal",
    })
    write_json(ai_dir / "state/recovery/current.json", {
        "schema_version": "recovery_session.v1",
        "recovery_id": "trigger-smoke-recovery",
        "status": recovery_status,
        "updated_at": "2020-01-01T00:00:00+02:00",
    })
    write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
        "status": "active" if nudge_active else "inactive",
    })
    write_json(ai_dir / "outbox/to-phone/current-question.json", {
        "status": "active" if question_active else "inactive",
    })
    write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
        "active_nudge": {"nudge_id": "active"} if nudge_active else None,
        "active_question": {"question_id": "active"} if question_active else None,
    })

    if snooze_now:
        append_jsonl(ai_dir / f"events/actions/{day(now)}.jsonl", [{
            "event": "snooze_nudge",
            "action": "snooze_nudge",
            "timestamp_epoch": now,
        }])


def trigger_decision(ai_dir: Path) -> dict:
    return run_json(TRIGGER, ai_dir, "--dry-run")["decision"]


def test_trigger_due_zero_skips() -> None:
    ai_dir = Path(os.environ["TEST_AI_DIR"])
    setup_trigger(ai_dir, due=0)
    decision = trigger_decision(ai_dir)
    assert decision["decision"] == "skip"
    assert "anki_not_due" in decision["blocked_reasons"]


def test_trigger_gates_clear_writes_nudge() -> None:
    ai_dir = Path(os.environ["TEST_AI_DIR"])
    setup_trigger(ai_dir, due=42)
    decision = trigger_decision(ai_dir)
    assert decision["decision"] == "write_nudge"

    proc = run_script(TRIGGER, ai_dir, "--once")
    assert proc.returncode == 0, proc.stderr

    summary = json.loads(proc.stdout)
    assert summary["decision"] == "write_nudge"
    assert summary["wrote_nudge"] is True

    nudge = json.loads((ai_dir / "outbox/to-phone/current-nudge.json").read_text(encoding="utf-8"))
    assert nudge["status"] == "active"
    assert nudge["actions"][0]["action"] == "start_recovery_target"



def test_trigger_uses_agent_context_due_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-trigger-agent-context-") as tmp:
        ai_dir = Path(tmp) / "AI"
        setup_trigger(ai_dir, due=0)

        # This shape is understood by agent_context.py. The old trigger-local
        # parser only looked under totals, so this proves the trigger consumes
        # the shared context contract instead of duplicate local derivation.
        write_json(ai_dir / "state/anki/status.json", {
            "available": True,
            "due": 4,
        })

        result = run_json(TRIGGER, ai_dir, "--dry-run")
        decision = result["decision"]

        assert decision["facts"]["anki_due"] == 4
        assert decision["decision"] == "write_nudge", decision
        assert decision["validation_result"]["ok"] is True
        assert decision["agent_context"]["source"] == "agent_context.py"


def test_trigger_blocks() -> None:
    cases = [
        ("active_nudge", {"nudge_active": True}, "active_nudge"),
        ("active_question", {"question_active": True}, "active_question"),
        ("active_recovery", {"recovery_status": "active"}, "active_recovery"),
        ("recent_snooze", {"snooze_now": True}, "recent_snooze"),
        ("active_session", {"session_active": True}, "active_session"),
    ]

    for name, kwargs, expected_block in cases:
        with tempfile.TemporaryDirectory(prefix=f"ai-trigger-{name}-") as tmp:
            ai_dir = Path(tmp)
            setup_trigger(ai_dir, due=42, **kwargs)
            decision = trigger_decision(ai_dir)
            assert decision["decision"] == "skip", name
            assert expected_block in decision["blocked_reasons"], decision["blocked_reasons"]


def run_isolated(test_func) -> None:
    with tempfile.TemporaryDirectory(prefix="ai-smoke-") as tmp:
        os.environ["TEST_AI_DIR"] = tmp
        test_func()
    print(f"PASS {test_func.__name__}")


def main() -> None:
    tests = [
        test_manager_fresh_quick_exit,
        test_manager_old_quick_exit,
        test_manager_success_still_open,
        test_manager_terminal_no_churn,
        test_trigger_due_zero_skips,
        test_trigger_gates_clear_writes_nudge,
        test_trigger_uses_agent_context_due_shape,
        test_trigger_blocks,
    ]

    for test in tests:
        run_isolated(test)

    print("ALL PASS")


if __name__ == "__main__":
    main()
