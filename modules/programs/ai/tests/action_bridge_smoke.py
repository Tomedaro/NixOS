#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
ACTION_BRIDGE = REPO / "modules/programs/ai/action-bridge/action_bridge.py"
ACTION_BRIDGE_DEFAULT_NIX = REPO / "modules/programs/ai/action-bridge/default.nix"


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


def run_action_bridge(ai_dir: Path, tasknotes_dir: Path, extra_env=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["AI_DIR"] = str(ai_dir)
    env["TASKNOTES_DIR"] = str(tasknotes_dir)
    env["STABILITY_SECONDS"] = "0"
    env["ACTION_BRIDGE_STABILITY_SECONDS"] = "0"
    env["ACTION_BRIDGE_TIMEZONE"] = "Europe/Paris"
    env["PYTHONUNBUFFERED"] = "1"

    shared_python = str(REPO / "modules/programs/ai/python")
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        shared_python if not old_pythonpath else shared_python + ":" + old_pythonpath
    )

    if extra_env is not None:
        env.update(extra_env)

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
        "inbox/actions-manual-review",
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

    write_json(
        ai_dir / "state/session/current.json",
        {
            "session_id": "old-completed-session",
            "status": "completed",
            "task": "Old task",
            "project": "Old project",
            "mode": "old",
        },
    )

    write_json(
        ai_dir / "outbox/to-phone/interaction-state.json",
        {
            "schema_version": "phone_interaction_state.v1",
            "active_nudge": None,
            "active_question": None,
        },
    )


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
    assert (
        proc.returncode == 0
    ), f"action bridge failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


def latest_action_events(ai_dir: Path) -> list[dict]:
    return read_jsonl(ai_dir / f"events/actions/{today()}.jsonl")


def processed_files(ai_dir: Path) -> list[Path]:
    return list((ai_dir / f"inbox/actions-processed/{today()}").glob("*.json"))


def manual_review_files(ai_dir: Path) -> list[Path]:
    return list((ai_dir / f"inbox/actions-manual-review/{today()}").glob("*.json"))


def failed_files(ai_dir: Path) -> list[Path]:
    return list((ai_dir / f"inbox/actions-failed/{today()}").glob("*.json"))


def raw_action_file(ai_dir: Path, name: str, text: str) -> Path:
    path = ai_dir / "inbox/actions" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    old_time = time.time() - 120
    os.utime(path, (old_time, old_time))
    return path


def action_journal_path(ai_dir: Path, action_id: str) -> Path:
    digest = hashlib.sha256(action_id.encode("utf-8")).hexdigest()[:12]
    return ai_dir / "state/action-bridge/action-journal" / f"{action_id}-{digest}.json"


def test_ack_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-ack-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-ack-smoke",
                "intervention_id": "i-ack-smoke",
                "message": "Smoke nudge",
                "recommended_next_action": "Acknowledge this.",
                "actions": [{"action": "ack_nudge", "label": "Done"}],
            },
        )

        write_json(
            ai_dir / "outbox/to-phone/interaction-state.json",
            {
                "active_nudge": {"nudge_id": "n-ack-smoke", "status": "active"},
                "active_question": None,
            },
        )

        action_file(
            ai_dir,
            "1000_ack_nudge.json",
            {
                "schema_version": "action.v1",
                "action": "ack_nudge",
                "source": "test",
                "device": "phone",
                "nudge_id": "n-ack-smoke",
                "message": "Smoke nudge",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={"ACTION_AUTHORITY_LEVEL": "1"},
        )
        assert_bridge_ok(proc)

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "acknowledged"

        events = latest_action_events(ai_dir)
        ack_events = [
            e
            for e in events
            if e.get("event") == "ack_nudge" and e.get("nudge_id") == "n-ack-smoke"
        ]
        assert ack_events
        assert ack_events[-1]["intervention_id"] == "i-ack-smoke"

        interaction_state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")
        assert interaction_state["last_nudge_ack"]["intervention_id"] == "i-ack-smoke"
        assert processed_files(ai_dir), "action file was not moved to processed"


def test_snooze_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-snooze-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-snooze-smoke",
                "intervention_id": "i-snooze-smoke",
                "message": "Smoke snooze nudge",
                "recommended_next_action": "Snooze this.",
                "actions": [
                    {"action": "snooze_nudge", "label": "Not now", "snooze_minutes": 15}
                ],
            },
        )

        action_file(
            ai_dir,
            "1000_snooze_nudge.json",
            {
                "schema_version": "action.v1",
                "action": "snooze_nudge",
                "source": "test",
                "device": "phone",
                "nudge_id": "n-snooze-smoke",
                "snooze_minutes": 15,
                "reason": "smoke",
                "timestamp_epoch": int(time.time()),
            },
        )

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
        snooze_events = [
            e
            for e in events
            if e.get("event") == "snooze_nudge" and e.get("snooze_minutes") == 15
        ]
        assert snooze_events
        assert snooze_events[-1]["intervention_id"] == "i-snooze-smoke"
        assert (
            interaction_state["last_nudge_snooze"]["intervention_id"]
            == "i-snooze-smoke"
        )


def test_start_recovery_target_consumes_nudge() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-recovery-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-recovery-smoke",
                "intervention_id": "i-recovery-smoke",
                "planner_mode": "recovery",
                "message": "Start Anki.",
                "recommended_next_action": "Tap Start Anki.",
                "actions": [{"action": "start_recovery_target", "label": "Start Anki"}],
            },
        )

        action_file(
            ai_dir,
            "1000_start_recovery_target.json",
            {
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
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={"ALLOW_RECOVERY_TARGET_START": "1"},
        )
        assert_bridge_ok(proc)

        recovery = read_json(ai_dir / "state/recovery/current.json")
        assert recovery["status"] == "active"
        assert recovery["target"]["target_id"] == "anki"
        assert recovery["goal"]["text"] == "5 minutes in AnkiDroid"
        assert recovery["intervention"]["intervention_id"] == "i-recovery-smoke"

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "recovery_started"

        recovery_events = read_jsonl(ai_dir / f"events/recovery/{today()}.jsonl")
        recovery_started = [
            e
            for e in recovery_events
            if e.get("event") == "recovery_started"
            and e.get("nudge_id") == "n-recovery-smoke"
        ]
        assert recovery_started
        assert recovery_started[-1]["intervention_id"] == "i-recovery-smoke"

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["last_recovery_start"]["intervention_id"] == "i-recovery-smoke"


def test_answer_question() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-answer-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-question.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "question",
                "status": "active",
                "question_id": "q-answer-smoke",
                "question": "What is blocking you?",
                "answer_options": [{"id": "overwhelmed", "label": "Overwhelmed"}],
                "free_text_allowed": True,
                "response_action": "answer_question",
            },
        )

        write_json(
            ai_dir / "state/llm/pending-question.json",
            {
                "question_id": "q-answer-smoke",
                "question": "What is blocking you?",
                "status": "pending",
            },
        )

        action_file(
            ai_dir,
            "1000_answer_question.json",
            {
                "schema_version": "action.v1",
                "action": "answer_question",
                "source": "test",
                "device": "phone",
                "question_id": "q-answer-smoke",
                "answer": "overwhelmed",
                "answer_label": "Overwhelmed",
                "free_text": "Smoke answer",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        last_answer = read_json(ai_dir / "state/llm/last-answer.json")
        assert last_answer["question_id"] == "q-answer-smoke"
        assert last_answer["answer"] == "overwhelmed"

        current_question = read_json(ai_dir / "outbox/to-phone/current-question.json")
        assert current_question["status"] == "inactive"
        assert current_question["last_status"] == "answered"

        pending = read_json(ai_dir / "state/llm/pending-question.json", {})
        assert pending == {} or pending.get("status") in {
            "inactive",
            "answered",
            "cleared",
        }


def test_dismiss_question() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-dismiss-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-question.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "question",
                "status": "active",
                "question_id": "q-dismiss-smoke",
                "question": "Dismiss?",
                "answer_options": [],
                "free_text_allowed": True,
                "response_action": "answer_question",
            },
        )

        write_json(
            ai_dir / "state/llm/pending-question.json",
            {
                "question_id": "q-dismiss-smoke",
                "question": "Dismiss?",
                "status": "pending",
            },
        )

        action_file(
            ai_dir,
            "1000_dismiss_question.json",
            {
                "schema_version": "action.v1",
                "action": "dismiss_question",
                "source": "test",
                "device": "phone",
                "question_id": "q-dismiss-smoke",
                "reason": "smoke",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        current_question = read_json(ai_dir / "outbox/to-phone/current-question.json")
        assert current_question["status"] == "inactive"
        assert current_question["last_status"] == "dismissed"

        events = latest_action_events(ai_dir)
        assert any(
            e.get("event") == "dismiss_question"
            and e.get("question_id") == "q-dismiss-smoke"
            for e in events
        )


def test_queue_ignores_partial_dotfiles_and_non_json() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-queue-ignore-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-ignore-smoke",
                "message": "Ignore queue noise.",
                "recommended_next_action": "Do nothing.",
                "actions": [{"action": "ack_nudge", "label": "Done"}],
            },
        )

        payload = json.dumps(
            {
                "schema_version": "action.v1",
                "action": "ack_nudge",
                "source": "test",
                "device": "phone",
                "nudge_id": "n-ignore-smoke",
                "timestamp_epoch": int(time.time()),
            },
            indent=2,
        )

        raw_action_file(ai_dir, ".1000_ack_nudge.json", payload)
        raw_action_file(ai_dir, "1001_ack_nudge.json.tmp", payload)
        raw_action_file(ai_dir, "README.md", "not an action")

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "active"
        assert not processed_files(ai_dir)
        assert not failed_files(ai_dir)
        assert not latest_action_events(ai_dir)

        status = read_json(ai_dir / "state/action-bridge/status.json")
        ignored = status.get("details", {}).get("ignored", [])
        assert any(".1000_ack_nudge.json" in item for item in ignored)
        assert any("1001_ack_nudge.json.tmp" in item for item in ignored)


def test_invalid_json_moves_to_failed_once() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-invalid-json-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        raw_action_file(ai_dir, "1000_bad.json", "{not json")

        first = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(first)

        failed = failed_files(ai_dir)
        assert len(failed) == 1
        assert failed[0].with_suffix(failed[0].suffix + ".error.txt").exists()

        second = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(second)

        assert len(failed_files(ai_dir)) == 1
        assert not list((ai_dir / "inbox/actions").glob("*.json"))


def test_duplicate_action_id_is_skipped_without_duplicate_effects() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-idempotent-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-dedupe-smoke",
                "intervention_id": "i-dedupe-smoke",
                "message": "Dedupe nudge.",
                "recommended_next_action": "Acknowledge once.",
                "actions": [
                    {"action": "ack_nudge", "label": "Done"},
                    {"action": "snooze_nudge", "label": "Not now"},
                ],
            },
        )

        write_json(
            ai_dir / "outbox/to-phone/interaction-state.json",
            {
                "active_nudge": {"nudge_id": "n-dedupe-smoke", "status": "active"},
                "active_question": None,
            },
        )

        shared = {
            "schema_version": "action.v1",
            "action_id": "dedupe-action-smoke",
            "source": "test",
            "device": "phone",
            "nudge_id": "n-dedupe-smoke",
            "timestamp_epoch": int(time.time()),
        }

        action_file(
            ai_dir,
            "1000_ack_nudge.json",
            dict(shared, action="ack_nudge"),
        )
        action_file(
            ai_dir,
            "1001_snooze_nudge.json",
            dict(shared, action="snooze_nudge", snooze_minutes=15),
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        events = [
            event
            for event in latest_action_events(ai_dir)
            if event.get("action_id") == "dedupe-action-smoke"
        ]
        assert len(events) == 1
        assert events[0]["event"] == "ack_nudge"

        interaction_state = read_json(ai_dir / "outbox/to-phone/interaction-state.json")
        assert interaction_state["last_nudge_ack"]["nudge_id"] == "n-dedupe-smoke"
        assert "last_nudge_snooze" not in interaction_state

        assert len(processed_files(ai_dir)) == 2

        cache = read_json(ai_dir / "state/action-bridge/processed-action-ids.json")
        assert "dedupe-action-smoke" in cache["ids"]



def test_dispatched_actions_have_capability_policy() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    module_name = f"action_bridge_policy_smoke_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    expected = {
        "ack_nudge",
        "snooze_nudge",
        "answer_question",
        "dismiss_question",
        "start_session",
        "end_session",
        "check_in",
        "start_recovery_target",
        "submit_proof",
        "promote_task_proposal",
        "promote_proposal",
    }

    policy = module.ACTION_CAPABILITY_POLICY

    assert set(policy) == expected
    assert policy["ack_nudge"]["capability"] == "interaction.nudge.respond"
    assert policy["snooze_nudge"]["capability"] == "interaction.nudge.respond"
    assert policy["answer_question"]["capability"] == "interaction.question.respond"
    assert policy["dismiss_question"]["capability"] == "interaction.question.respond"
    assert policy["start_session"]["capability"] == "session.lifecycle"
    assert policy["end_session"]["capability"] == "session.lifecycle"
    assert policy["check_in"]["capability"] == "session.check_in"
    assert policy["start_recovery_target"]["capability"] == "recovery.target.start"
    assert policy["submit_proof"]["capability"] == "proof.submit"
    assert policy["promote_task_proposal"]["capability"] == "disabled.legacy"
    assert policy["promote_proposal"]["capability"] == "disabled.legacy"




def test_action_capability_policy_metadata_invariants() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    module_name = f"action_bridge_policy_metadata_smoke_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    valid_statuses = {"supported", "gated", "disabled"}
    required_fields = {
        "capability",
        "status",
        "side_effect",
        "default_enabled",
        "enabled",
    }

    for action_name, policy in module.ACTION_CAPABILITY_POLICY.items():
        assert required_fields <= set(policy), action_name
        assert policy["status"] in valid_statuses, action_name
        assert isinstance(policy["side_effect"], str), action_name
        assert policy["side_effect"], action_name
        assert isinstance(policy["default_enabled"], bool), action_name

        if policy["status"] == "supported":
            assert policy["default_enabled"] is True, action_name
            assert policy["enabled"] is True, action_name
            assert "gate_env" not in policy, action_name
            assert "min_authority" not in policy, action_name

        if policy["status"] == "gated":
            assert "gate_env" in policy, action_name
            assert policy["gate_env"].startswith("ALLOW_"), action_name
            assert callable(policy["enabled"]), action_name

        if policy["status"] == "disabled":
            assert policy["default_enabled"] is False, action_name
            assert policy["enabled"] is False, action_name
            assert policy["capability"] == "disabled.legacy", action_name

    for policy in module.ACTION_CAPABILITY_POLICY.values():
        assert policy["capability"] != "tasknotes.promote"

    assert (
        module.ACTION_CAPABILITY_POLICY["check_in"]["gate_env"]
        == "ALLOW_SESSION_CHECK_IN"
    )
    assert (
        module.ACTION_CAPABILITY_POLICY["start_recovery_target"]["gate_env"]
        == "ALLOW_RECOVERY_TARGET_START"
    )
    assert (
        module.ACTION_CAPABILITY_POLICY["submit_proof"]["gate_env"]
        == "ALLOW_PROOF_SUBMIT"
    )
    assert module.ACTION_CAPABILITY_POLICY["submit_proof"]["min_authority"] == 1

    assert module.ACTION_CAPABILITY_POLICY["promote_task_proposal"]["status"] == "disabled"
    assert module.ACTION_CAPABILITY_POLICY["promote_proposal"]["status"] == "disabled"
    assert (
        module.ACTION_CAPABILITY_POLICY["promote_task_proposal"]["side_effect"]
        == "none_disabled_tasknotes"
    )
    assert (
        module.ACTION_CAPABILITY_POLICY["promote_proposal"]["side_effect"]
        == "none_disabled_tasknotes"
    )



def test_action_capability_policy_defaults_match_runtime_and_nix_wiring() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    env_keys = [
        "ACTION_AUTHORITY_LEVEL",
        "ALLOW_PROOF_SUBMIT",
        "ALLOW_RECOVERY_TARGET_START",
        "ALLOW_SESSION_CHECK_IN",
    ]
    old_env = {key: os.environ.get(key) for key in env_keys}

    try:
        for key in env_keys:
            os.environ.pop(key, None)

        module_name = f"action_bridge_default_authority_smoke_{time.time_ns()}"
        spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert module.AUTHORITY_LEVEL == 2
    assert module.ALLOW_PROOF_SUBMIT is True
    assert module.ALLOW_RECOVERY_TARGET_START is False
    assert module.ALLOW_SESSION_CHECK_IN is True

    gated = {
        "check_in": ("ALLOW_SESSION_CHECK_IN", "allowSessionCheckIn"),
        "start_recovery_target": (
            "ALLOW_RECOVERY_TARGET_START",
            "allowRecoveryTargetStart",
        ),
        "submit_proof": ("ALLOW_PROOF_SUBMIT", "allowProofSubmit"),
    }

    for action_name, (env_name, _nix_option) in gated.items():
        policy = module.ACTION_CAPABILITY_POLICY[action_name]
        expected_default = action_name != "start_recovery_target"
        assert policy["status"] == "gated", action_name
        assert policy["default_enabled"] is expected_default, action_name
        assert policy["gate_env"] == env_name, action_name
        assert policy["enabled"]() is expected_default, action_name

    assert module.ACTION_CAPABILITY_POLICY["submit_proof"]["min_authority"] == 1

    capabilities = {
        policy["capability"]
        for policy in module.ACTION_CAPABILITY_POLICY.values()
    }
    assert "tasknotes.promote" not in capabilities

    action_source = ACTION_BRIDGE.read_text(encoding="utf-8")
    nix_source = ACTION_BRIDGE_DEFAULT_NIX.read_text(encoding="utf-8")

    assert 'ACTION_AUTHORITY_LEVEL", "2"' in action_source
    assert 'ALLOW_PROOF_SUBMIT", "1"' in action_source
    assert 'ALLOW_RECOVERY_TARGET_START", "0"' in action_source
    assert 'ALLOW_SESSION_CHECK_IN", "1"' in action_source

    assert "if AUTHORITY_LEVEL < 1:" in action_source
    assert "submit_proof requires ACTION_AUTHORITY_LEVEL >= 1" in action_source

    assert "allowLegacyTaskNotesPromotion" not in nix_source
    assert "ALLOW_LEGACY_TASKNOTES_PROMOTION" not in nix_source
    assert "ALLOW_LEGACY_TASKNOTES_PROMOTION" not in action_source

    def nix_option_block(option_name: str) -> str:
        marker = f"    {option_name} = lib.mkOption {{"
        start = nix_source.find(marker)
        assert start >= 0, option_name
        end_marker = "\n    };"
        end = nix_source.find(end_marker, start)
        assert end >= 0, option_name
        return nix_source[start : end + len(end_marker)]

    for _action_name, (env_name, nix_option) in gated.items():
        block = nix_option_block(nix_option)
        expected_default_line = (
            "default = false;"
            if nix_option == "allowRecoveryTargetStart"
            else "default = true;"
        )
        assert expected_default_line in block, nix_option
        assert (
            f'{env_name} = if cfg.{nix_option} then "1" else "0";'
            in nix_source
        ), env_name

    authority_block = nix_option_block("authorityLevel")
    assert "default = 2;" in authority_block




def test_numeric_action_authority_scope_is_explicit() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    env_keys = [
        "ACTION_AUTHORITY_LEVEL",
        "ALLOW_PROOF_SUBMIT",
        "ALLOW_RECOVERY_TARGET_START",
        "ALLOW_SESSION_CHECK_IN",
    ]
    old_env = {key: os.environ.get(key) for key in env_keys}

    try:
        for key in env_keys:
            os.environ.pop(key, None)

        module_name = f"action_bridge_numeric_authority_smoke_{time.time_ns()}"
        spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert module.AUTHORITY_LEVEL == 2

    actions_with_min_authority = {
        action_name
        for action_name, policy in module.ACTION_CAPABILITY_POLICY.items()
        if "min_authority" in policy
    }
    assert actions_with_min_authority == {"submit_proof"}
    assert module.ACTION_CAPABILITY_POLICY["submit_proof"]["min_authority"] == 1

    capabilities = {
        policy["capability"]
        for policy in module.ACTION_CAPABILITY_POLICY.values()
    }
    assert "tasknotes.promote" not in capabilities

    action_source = ACTION_BRIDGE.read_text(encoding="utf-8")
    nix_source = ACTION_BRIDGE_DEFAULT_NIX.read_text(encoding="utf-8")

    numeric_enforcement_lines = [
        line.strip()
        for line in action_source.splitlines()
        if line.strip().startswith("if ")
        and "AUTHORITY_LEVEL" in line
        and any(operator in line for operator in ["<=", ">=", "<", ">"])
    ]

    assert numeric_enforcement_lines == ["if AUTHORITY_LEVEL < 1:"]
    assert "submit_proof requires ACTION_AUTHORITY_LEVEL >= 1" in action_source

    submit_handler_start = action_source.find("def handle_submit_proof")
    assert submit_handler_start >= 0
    submit_authority_check = action_source.find(
        "if AUTHORITY_LEVEL < 1:",
        submit_handler_start,
    )
    assert submit_authority_check >= 0

    assert "allowLegacyTaskNotesPromotion" not in nix_source
    assert "ALLOW_LEGACY_TASKNOTES_PROMOTION" not in nix_source
    assert "ALLOW_LEGACY_TASKNOTES_PROMOTION" not in action_source

    def nix_option_block(option_name: str) -> str:
        marker = f"    {option_name} = lib.mkOption {{"
        start = nix_source.find(marker)
        assert start >= 0, option_name
        end_marker = "\n    };"
        end = nix_source.find(end_marker, start)
        assert end >= 0, option_name
        return nix_source[start : end + len(end_marker)]

    authority_block = nix_option_block("authorityLevel")
    assert "default = 2;" in authority_block
    assert "ACTION_AUTHORITY_LEVEL = toString cfg.authorityLevel;" in nix_source


def test_action_capability_policy_enforcement_classification_is_explicit() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    module_name = f"action_bridge_policy_enforcement_smoke_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    enforced_actions = {
        "check_in",
        "start_recovery_target",
        "submit_proof",
        "promote_task_proposal",
        "promote_proposal",
    }
    supported_default_actions = {
        "start_session",
        "end_session",
        "answer_question",
        "dismiss_question",
        "ack_nudge",
        "snooze_nudge",
    }
    disabled_actions = {
        "promote_task_proposal",
        "promote_proposal",
    }
    named_gates = {
        "check_in": "ALLOW_SESSION_CHECK_IN",
        "start_recovery_target": "ALLOW_RECOVERY_TARGET_START",
        "submit_proof": "ALLOW_PROOF_SUBMIT",
    }

    policy_actions = set(module.ACTION_CAPABILITY_POLICY)
    assert enforced_actions | supported_default_actions == policy_actions
    assert enforced_actions & supported_default_actions == set()
    assert disabled_actions <= enforced_actions

    for action_name in supported_default_actions:
        policy = module.ACTION_CAPABILITY_POLICY[action_name]
        assert policy["status"] == "supported", action_name
        assert policy["default_enabled"] is True, action_name
        assert policy["enabled"] is True, action_name
        assert "gate_env" not in policy, action_name
        assert "min_authority" not in policy, action_name

    for action_name, gate_env in named_gates.items():
        policy = module.ACTION_CAPABILITY_POLICY[action_name]
        expected_default = action_name != "start_recovery_target"
        assert policy["status"] == "gated", action_name
        assert policy["default_enabled"] is expected_default, action_name
        assert policy["gate_env"] == gate_env, action_name
        assert callable(policy["enabled"]), action_name

    actions_with_min_authority = {
        action_name
        for action_name, policy in module.ACTION_CAPABILITY_POLICY.items()
        if "min_authority" in policy
    }
    assert actions_with_min_authority == {"submit_proof"}
    assert module.ACTION_CAPABILITY_POLICY["submit_proof"]["min_authority"] == 1

    for action_name in disabled_actions:
        policy = module.ACTION_CAPABILITY_POLICY[action_name]
        assert policy["status"] == "disabled", action_name
        assert policy["capability"] == "disabled.legacy", action_name
        assert policy["default_enabled"] is False, action_name
        assert policy["enabled"] is False, action_name
        assert policy["side_effect"] == "none_disabled_tasknotes", action_name

    capabilities = {
        policy["capability"]
        for policy in module.ACTION_CAPABILITY_POLICY.values()
    }
    assert "tasknotes.promote" not in capabilities

    action_source = ACTION_BRIDGE.read_text(encoding="utf-8")

    def has_literal_require_call(action_name: str) -> bool:
        return (
            f'require_action_capability("{action_name}")' in action_source
            or f"require_action_capability('{action_name}')" in action_source
        )

    for action_name in named_gates:
        assert has_literal_require_call(action_name), action_name

    # Disabled legacy actions are covered by policy classification here and by
    # test_tasknotes_promotion_is_disabled_even_with_legacy_env for behavior.
    # Do not require a literal source call shape for the shared legacy handler.
    assert (
        module.ACTION_CAPABILITY_POLICY["promote_task_proposal"]["status"]
        == "disabled"
    )
    assert (
        module.ACTION_CAPABILITY_POLICY["promote_proposal"]["status"]
        == "disabled"
    )

    for action_name in supported_default_actions:
        assert not has_literal_require_call(action_name), action_name


def test_dispatch_aliases_have_capability_policy() -> None:
    shared_python = str(REPO / "modules/programs/ai/python")
    if shared_python not in sys.path:
        sys.path.insert(0, shared_python)

    module_name = f"action_bridge_alias_policy_smoke_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, ACTION_BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    expected_aliases = {
        "start": "start_session",
        "end": "end_session",
        "manual_checkin": "check_in",
        "question_answered": "answer_question",
        "nudge_acknowledged": "ack_nudge",
        "defer_nudge": "snooze_nudge",
        "nudge_snoozed": "snooze_nudge",
        "question_dismissed": "dismiss_question",
        "start_recovery": "start_recovery_target",
        "recovery_start": "start_recovery_target",
        "proof_submitted": "submit_proof",
        "promote_proposal": "promote_proposal",
    }

    assert module.ACTION_CAPABILITY_ALIASES == expected_aliases

    for alias, canonical in expected_aliases.items():
        assert canonical in module.ACTION_CAPABILITY_POLICY, alias

    assert (
        module.ACTION_CAPABILITY_POLICY["promote_task_proposal"]["capability"]
        == "disabled.legacy"
    )
    assert (
        module.ACTION_CAPABILITY_POLICY["promote_proposal"]["capability"]
        == "disabled.legacy"
    )


def test_tasknotes_promotion_is_disabled_even_with_legacy_env() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-tasknotes-disabled-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        proposal_name = "disabled-tasknotes-promotion"
        proposal_dir = ai_dir / "proposed-tasks"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        (proposal_dir / f"{proposal_name}.md").write_text(
            "# Should never be promoted\n",
            encoding="utf-8",
        )

        target = tasknotes_dir / "Tasks/disabled-should-not-write.md"

        action_file(
            ai_dir,
            "1000_promote_task_proposal.json",
            {
                "schema_version": "action.v1",
                "action": "promote_task_proposal",
                "action_id": "disabled-tasknotes-promotion",
                "source": "test",
                "device": "phone",
                "timestamp_epoch": int(time.time()),
                "proposal": proposal_name,
                "target": "Tasks/disabled-should-not-write.md",
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={
                "ACTION_AUTHORITY_LEVEL": "2",
                "ALLOW_LEGACY_TASKNOTES_PROMOTION": "1",
            },
        )
        assert_bridge_ok(proc)

        assert not target.exists()
        assert not any(tasknotes_dir.rglob("*"))
        assert not processed_files(ai_dir)
        assert failed_files(ai_dir)

        error_text = "\\n".join(
            path.read_text(encoding="utf-8")
            for path in (ai_dir / "inbox/actions-failed").rglob("*.error.txt")
        )
        assert "promote_task_proposal is disabled" in error_text


def test_proof_submit_requires_named_capability() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-proof-capability-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        action_file(
            ai_dir,
            "1000_submit_proof.json",
            {
                "schema_version": "action.v1",
                "action": "submit_proof",
                "action_id": "proof-submit-capability-blocked",
                "source": "test",
                "device": "phone",
                "proof_id": "blocked-proof",
                "message": "This proof should not be written.",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={
                "ACTION_AUTHORITY_LEVEL": "1",
                "ALLOW_PROOF_SUBMIT": "0",
            },
        )
        assert_bridge_ok(proc)

        assert not processed_files(ai_dir)
        assert failed_files(ai_dir)
        assert not any((ai_dir / "proofs").rglob("*"))
        assert not any((ai_dir / "events/proofs").rglob("*.jsonl"))

        error_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ai_dir / "inbox/actions-failed").rglob("*.error.txt")
        )
        assert "ALLOW_PROOF_SUBMIT=1" in error_text




def test_start_recovery_target_default_requires_named_capability() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-recovery-default-capability-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-recovery-default-capability-blocked",
                "intervention_id": "i-recovery-default-capability-blocked",
                "message": "Recovery default capability blocked nudge",
                "recommended_next_action": "Start Anki.",
                "target": {
                    "target_id": "anki",
                    "label": "Anki",
                    "android_package": "com.ichi2.anki",
                },
                "actions": [{"action": "start_recovery_target", "label": "Start Anki"}],
            },
        )

        action_file(
            ai_dir,
            "1000_start_recovery_target.json",
            {
                "schema_version": "action.v1",
                "action": "start_recovery_target",
                "action_id": "recovery-target-default-capability-blocked",
                "source": "test",
                "device": "phone",
                "target_id": "anki",
                "recovery_id": "recovery-default-capability-blocked",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        assert not processed_files(ai_dir)
        assert failed_files(ai_dir)
        assert not (ai_dir / "state/recovery/current.json").exists()
        assert not any((ai_dir / "events/recovery").rglob("*.jsonl"))
        assert not any(tasknotes_dir.rglob("*"))

        current_nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert current_nudge["status"] == "active"
        assert current_nudge.get("last_status") != "recovery_started"

        error_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ai_dir / "inbox/actions-failed").rglob("*.error.txt")
        )
        assert "ALLOW_RECOVERY_TARGET_START=1" in error_text


def test_start_recovery_target_requires_named_capability() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-recovery-capability-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-recovery-capability-blocked",
                "intervention_id": "i-recovery-capability-blocked",
                "message": "Recovery capability blocked nudge",
                "recommended_next_action": "Start Anki.",
                "target": {
                    "target_id": "anki",
                    "label": "Anki",
                    "android_package": "com.ichi2.anki",
                },
                "actions": [{"action": "start_recovery_target", "label": "Start Anki"}],
            },
        )

        action_file(
            ai_dir,
            "1000_start_recovery_target.json",
            {
                "schema_version": "action.v1",
                "action": "start_recovery_target",
                "action_id": "recovery-target-capability-blocked",
                "source": "test",
                "device": "phone",
                "target_id": "anki",
                "recovery_id": "recovery-capability-blocked",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={"ALLOW_RECOVERY_TARGET_START": "0"},
        )
        assert_bridge_ok(proc)

        assert not processed_files(ai_dir)
        assert failed_files(ai_dir)
        assert not (ai_dir / "state/recovery/current.json").exists()
        assert not any((ai_dir / "events/recovery").rglob("*.jsonl"))

        error_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ai_dir / "inbox/actions-failed").rglob("*.error.txt")
        )
        assert "ALLOW_RECOVERY_TARGET_START=1" in error_text



def test_check_in_requires_named_capability() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-check-in-capability-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        action_id = "check-in-capability-blocked"

        action_file(
            ai_dir,
            "1000_check_in.json",
            {
                "schema_version": "action.v1",
                "action": "check_in",
                "action_id": action_id,
                "source": "test",
                "device": "desktop",
                "answer": "blocked",
                "answer_label": "Blocked",
                "free_text": "This check-in should not be recorded.",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={
                "ALLOW_SESSION_CHECK_IN": "0",
                "TRIGGER_HELP_NOW": "0",
            },
        )
        assert_bridge_ok(proc)

        assert not processed_files(ai_dir)
        assert failed_files(ai_dir)

        events = [
            event
            for event in latest_action_events(ai_dir)
            if event.get("event") == "check_in"
            and event.get("action_id") == action_id
        ]
        assert not events

        error_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ai_dir / "inbox/actions-failed").rglob("*.error.txt")
        )
        assert "ALLOW_SESSION_CHECK_IN=1" in error_text


def test_action_journal_records_processed_action() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-journal-success-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        action_id = "action-journal-success"

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-journal-success",
                "intervention_id": "i-journal-success",
                "message": "Journal success nudge",
                "recommended_next_action": "Acknowledge this.",
                "actions": [{"action": "ack_nudge", "label": "Done"}],
            },
        )

        action_file(
            ai_dir,
            "1000_journal_success.json",
            {
                "schema_version": "action.v1",
                "action": "ack_nudge",
                "action_id": action_id,
                "source": "test",
                "device": "phone",
                "nudge_id": "n-journal-success",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        journal = read_json(action_journal_path(ai_dir, action_id))
        assert journal["schema_version"] == "action_processing_journal.v1"
        assert journal["action_id"] == action_id
        assert journal["status"] == "processed"
        assert journal["raw_file"].startswith("inbox/actions-processed/")
        assert journal["raw_sha256"]
        assert journal["details"]["processed_path"]

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "inactive"
        assert nudge["last_status"] == "acknowledged"


def test_processing_journal_blocks_replay_without_side_effects() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-journal-interrupted-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        setup_base(ai_dir)

        action_id = "action-journal-interrupted"

        write_json(
            action_journal_path(ai_dir, action_id),
            {
                "schema_version": "action_processing_journal.v1",
                "action_id": action_id,
                "action": "ack_nudge",
                "status": "processing",
                "raw_file": "inbox/actions/1000_interrupted.json",
            },
        )

        write_json(
            ai_dir / "outbox/to-phone/current-nudge.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "nudge",
                "status": "active",
                "nudge_id": "n-interrupted",
                "intervention_id": "i-interrupted",
                "message": "Interrupted nudge",
                "recommended_next_action": "Acknowledge this.",
                "actions": [{"action": "ack_nudge", "label": "Done"}],
            },
        )

        action_file(
            ai_dir,
            "1000_interrupted.json",
            {
                "schema_version": "action.v1",
                "action": "ack_nudge",
                "action_id": action_id,
                "source": "test",
                "device": "phone",
                "nudge_id": "n-interrupted",
                "timestamp_epoch": int(time.time()),
            },
        )

        proc = run_action_bridge(ai_dir, tasknotes_dir)
        assert_bridge_ok(proc)

        nudge = read_json(ai_dir / "outbox/to-phone/current-nudge.json")
        assert nudge["status"] == "active"

        assert not processed_files(
            ai_dir
        ), "stale processing journal should not process"
        assert not failed_files(
            ai_dir
        ), "stale processing journal should not be ordinary failure"
        assert manual_review_files(
            ai_dir
        ), "stale processing journal should require manual review"

        journal = read_json(action_journal_path(ai_dir, action_id))
        assert journal["status"] == "manual_review"
        assert journal["details"]["reason"] == "stale_processing_journal"

        status = read_json(ai_dir / "state/action-bridge/status.json")
        assert status["status"] == "manual_review"
        assert status["details"]["manual_review"]


def test_process_lock_is_non_blocking() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-action-bridge-lock-") as tmp:
        ai_dir = Path(tmp) / "AI"

        old_ai_dir = os.environ.get("AI_DIR")
        os.environ["AI_DIR"] = str(ai_dir)

        try:
            shared_python = str(REPO / "modules/programs/ai/python")
            if shared_python not in sys.path:
                sys.path.insert(0, shared_python)

            module_path = REPO / "modules/programs/ai/action-bridge/action_bridge.py"
            spec = importlib.util.spec_from_file_location(
                "action_bridge_lock_smoke",
                module_path,
            )
            assert spec is not None
            assert spec.loader is not None

            action_bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(action_bridge)

            action_bridge.ensure_dirs()

            first = action_bridge.acquire_process_lock()
            assert first is not None

            second = action_bridge.acquire_process_lock()
            assert second is None

            action_bridge.release_process_lock(first)

            third = action_bridge.acquire_process_lock()
            assert third is not None
            action_bridge.release_process_lock(third)
        finally:
            if old_ai_dir is None:
                os.environ.pop("AI_DIR", None)
            else:
                os.environ["AI_DIR"] = old_ai_dir


def main() -> None:
    tests = [
        test_ack_nudge,
        test_snooze_nudge,
        test_start_recovery_target_consumes_nudge,
        test_answer_question,
        test_dismiss_question,
        test_queue_ignores_partial_dotfiles_and_non_json,
        test_invalid_json_moves_to_failed_once,
        test_duplicate_action_id_is_skipped_without_duplicate_effects,
        test_dispatched_actions_have_capability_policy,
        test_action_capability_policy_metadata_invariants,
        test_action_capability_policy_defaults_match_runtime_and_nix_wiring,
        test_numeric_action_authority_scope_is_explicit,
        test_action_capability_policy_enforcement_classification_is_explicit,
        test_dispatch_aliases_have_capability_policy,
        test_tasknotes_promotion_is_disabled_even_with_legacy_env,
        test_proof_submit_requires_named_capability,
        test_start_recovery_target_default_requires_named_capability,
        test_start_recovery_target_requires_named_capability,
        test_check_in_requires_named_capability,
        test_action_journal_records_processed_action,
        test_processing_journal_blocks_replay_without_side_effects,
        test_process_lock_is_non_blocking,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
