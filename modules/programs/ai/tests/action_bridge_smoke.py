#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
ACTION_BRIDGE = REPO / "modules/programs/ai/action-bridge/action_bridge.py"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
    except Exception:
        return default
    return default


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def run_action_bridge(ai_dir: Path, tasknotes_dir: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["AI_DIR"] = str(ai_dir)
    env["TASKNOTES_DIR"] = str(tasknotes_dir)
    env["STABILITY_SECONDS"] = "0"
    env["ACTION_BRIDGE_STABILITY_SECONDS"] = "0"
    env["ACTION_BRIDGE_TIMEZONE"] = "Europe/Paris"
    env["PYTHONUNBUFFERED"] = "1"

    shared_python = str(REPO / "modules/programs/ai/python")
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shared_python if not old_pythonpath else shared_python + ":" + old_pythonpath

    return subprocess.run(
        [sys.executable, str(ACTION_BRIDGE)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def today() -> str:
    return time.strftime("%Y-%m-%d")


def setup_base(ai_dir: Path) -> None:
    for rel in [
        "inbox/actions",
        "inbox/actions-processed",
        "inbox/actions-failed",
        "outbox/to-phone",
        "state/llm",
        "state/recovery",
        "state/action-bridge",
        "state/session",
        "events/actions",
        "events/recovery",
        "events/tasknotes",
        "events/proofs",
        "templates/actions",
        "schemas",
    ]:
        (ai_dir / rel).mkdir(parents=True, exist_ok=True)

    write_json(ai_dir / "state/session/current.json", {
        "session_id": "old-completed-session",
        "status": "completed",
        "task": "Old task",
        "project": "Old project",
        "mode": "old",
    })

    write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
        "schema_version": "phone_interaction_state.v1",
        "active_nudge": None,
        "active_question": None,
    })


def action_file(ai_dir: Path, name: str, payload: dict) -> Path:
    path = ai_dir / "inbox/actions" / name
    write_json(path, payload)

    # action-bridge intentionally ignores very fresh files to avoid
    # processing partially-synced JSON. Smoke tests age the file instead
    # of depending on a particular environment variable name.
    old_time = time.time() - 120
    os.utime(path, (old_time, old_time))

    return path


def assert_bridge_ok(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, (
        f"action bridge failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


def latest_action_events(ai_dir: Path) -> list[dict]:
    return read_jsonl(ai_dir / f"events/actions/{today()}.jsonl")


def processed_files(ai_dir: Path) -> list[Path]:
    return list((ai_dir / f"inbox/actions-processed/{today()}").glob("*.json"))


def test_ack_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-ack-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-ack-smoke",
            "message": "Smoke nudge",
            "recommended_next_action": "Acknowledge this.",
            "actions": [{"action": "ack_nudge", "label": "Done"}],
        })

        write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
            "active_nudge": {"nudge_id": "n-ack-smoke", "status": "active"},
            "active_question": None,
        })

        action_file(ai_dir, "1000_ack_nudge.json", {
            "schema_version": "action.v1",
            "action": "ack_nudge",
            "source": "test",
            "device": "phone",
            "nudge_id": "n-ack-smoke",
            "message": "Smoke nudge",
            "timestamp_epoch": int(time.time()),
        })

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "acknowledged"

        events = latest_action_events(ai_dir)
        assert any(e.get("event") == "ack_nudge" and e.get("nudge_id") == "n-ack-smoke" for e in events)
        assert processed_files(ai_dir), "action file was not moved to processed"


def test_snooze_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-snooze-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-snooze-smoke",
            "message": "Smoke snooze nudge",
            "recommended_next_action": "Snooze this.",
            "actions": [{"action": "snooze_nudge", "label": "Not now", "snooze_minutes": 15}],
        })

        action_file(ai_dir, "1000_snooze_nudge.json", {
            "schema_version": "action.v1",
            "action": "snooze_nudge",
            "source": "test",
            "device": "phone",
            "nudge_id": "n-snooze-smoke",
            "snooze_minutes": 15,
            "reason": "smoke",
            "timestamp_epoch": int(time.time()),
        })

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "snoozed"

        interaction_state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")
        snooze = interaction_state["last_nudge_snooze"]
        assert snooze["nudge_id"] == "n-snooze-smoke"
        assert snooze["snooze_minutes"] == 15
        assert snooze["snoozed_until"]

        events = latest_action_events(ai_dir)
        assert any(e.get("event") == "snooze_nudge" and e.get("snooze_minutes") == 15 for e in events)


def test_start_recovery_target_consumes_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-recovery-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-recovery-smoke",
            "planner_mode": "recovery",
            "message": "Start Anki.",
            "recommended_next_action": "Tap Start Anki.",
            "actions": [{"action": "start_recovery_target", "label": "Start Anki"}],
        })

        action_file(ai_dir, "1000_start_recovery_target.json", {
            "schema_version": "action.v1",
            "action": "start_recovery_target",
            "source": "test",
            "device": "phone",
            "nudge_id": "n-recovery-smoke",
            "target_id": "anki",
            "target_name": "Anki",
            "goal_text": "5 minutes in AnkiDroid",
            "stop_condition": "Stay in AnkiDroid for 5 minutes, then stop.",
            "android_package": "com.ichi2.anki",
            "timestamp_epoch": int(time.time()),
        })

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        recovery = read_json(ai_dir / "state/recovery/current.json")
        assert recovery["status"] == "active"
        assert recovery["target"]["target_id"] == "anki"
        assert recovery["goal"]["text"] == "5 minutes in AnkiDroid"

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "recovery_started"

        recovery_events = read_jsonl(ai_dir / f"events/recovery/{today()}.jsonl")
        assert any(e.get("event") == "recovery_started" and e.get("nudge_id") == "n-recovery-smoke" for e in recovery_events)


def test_answer_question() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-answer-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(ai_dir / "outbox/to-phone/current-question.json", {
            "schema_version": "phone_interaction.v1",
            "kind": "question",
            "status": "active",
            "question_id": "q-answer-smoke",
            "question": "What is blocking you?",
            "answer_options": [
                {"id": "overwhelmed", "label": "Overwhelmed"}
            ],
            "free_text_allowed": True,
            "response_action": "answer_question",
        })

        write_json(ai_dir / "state/llm/pending-question.json", {
            "question_id": "q-answer-smoke",
            "question": "What is blocking you?",
            "status": "pending",
        })

        action_file(ai_dir, "1000_answer_question.json", {
            "schema_version": "action.v1",
            "action": "answer_question",
            "source": "test",
            "device": "phone",
            "question_id": "q-answer-smoke",
            "answer": "overwhelmed",
            "answer_label": "Overwhelmed",
            "free_text": "Smoke answer",
            "timestamp_epoch": int(time.time()),
        })

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        last_answer = read_json(ai_dir / "state/llm/last-answer.json")
        assert last_answer["question_id"] == "q-answer-smoke"
        assert last_answer["answer"] == "overwhelmed"

        current_question = read_json(ai_dir / "outbox/to-phone/current-question.json")
        assert current_question["status"] == "inactive"
        assert current_question["last_status"] == "answered"

        pending = read_json(ai_dir / "state/llm/pending-question.json", {})
        assert pending == {} or pending.get("status") in {"inactive", "answered", "cleared"}


def test_dismiss_question() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-dismiss-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(ai_dir / "outbox/to-phone/current-question.json", {
            "schema_version": "phone_interaction.v1",
            "kind": "question",
            "status": "active",
            "question_id": "q-dismiss-smoke",
            "question": "Dismiss?",
            "answer_options": [],
            "free_text_allowed": True,
            "response_action": "answer_question",
        })

        write_json(ai_dir / "state/llm/pending-question.json", {
            "question_id": "q-dismiss-smoke",
            "question": "Dismiss?",
            "status": "pending",
        })

        action_file(ai_dir, "1000_dismiss_question.json", {
            "schema_version": "action.v1",
            "action": "dismiss_question",
            "source": "test",
            "device": "phone",
            "question_id": "q-dismiss-smoke",
            "reason": "smoke",
            "timestamp_epoch": int(time.time()),
        })

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        current_question = read_json(ai_dir / "outbox/to-phone/current-question.json")
        assert current_question["status"] == "inactive"
        assert current_question["last_status"] == "dismissed"

        events = latest_action_events(ai_dir)
        assert any(e.get("event") == "dismiss_question" and e.get("question_id") == "q-dismiss-smoke" for e in events)


def main() -> None:
    tests = [
        test_ack_nudge,
        test_snooze_nudge,
        test_start_recovery_target_consumes_nudge,
        test_answer_question,
        test_dismiss_question,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
