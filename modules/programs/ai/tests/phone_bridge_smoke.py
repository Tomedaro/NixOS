#!/usr/bin/env python3

import importlib.util
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
PHONE_BRIDGE = REPO_ROOT / "modules/programs/ai/phone-bridge/phone_bridge.py"
PYTHON_LIB = REPO_ROOT / "modules/programs/ai/python"


def run_bridge(
    ai_dir: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env.update({
        "AI_DIR": str(ai_dir),
        "PYTHONPATH": str(PYTHON_LIB) + ((f":{existing_pythonpath}") if existing_pythonpath else ""),
    })
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, str(PHONE_BRIDGE), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_phone_bridge(ai_dir: Path):
    os.environ["AI_DIR"] = str(ai_dir)
    os.environ["STABILITY_SECONDS"] = "0"
    os.environ["CREATE_TEMPLATES"] = "0"
    os.environ["PHONE_BRIDGE_TIMEZONE"] = "Europe/Paris"

    import sys
    sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

    spec = importlib.util.spec_from_file_location("phone_bridge_under_test", PHONE_BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def setup_ai_dir() -> tuple[tempfile.TemporaryDirectory, Path, object]:
    tmp = tempfile.TemporaryDirectory()
    ai_dir = Path(tmp.name) / "AI"
    module = load_phone_bridge(ai_dir)
    module.ensure_dirs()
    return tmp, ai_dir, module


def find_files(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob(pattern))


def test_valid_phone_event_is_processed() -> None:
    tmp, ai_dir, module = setup_ai_dir()
    with tmp:
        raw = ai_dir / "inbox/from-phone/events/1777995447_opened_ankidroid.json"
        write_json(raw, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Opened AnkiDroid",
            "timestamp_epoch": 1777995447,
            "tasker_date": "05-05-2026",
            "tasker_time": "17.37",
        })

        assert module.tick() == 1

        events = read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        assert len(events) == 1
        assert events[0]["event"] == "opened_ankidroid"
        assert events[0]["raw_file"] == "inbox/from-phone/events/1777995447_opened_ankidroid.json"
        assert not raw.exists()
        assert find_files(ai_dir / "inbox/from-phone/processed", "*.json")


def test_literal_tasker_variable_filename_is_failed() -> None:
    tmp, ai_dir, module = setup_ai_dir()
    with tmp:
        raw = ai_dir / "inbox/from-phone/events/%ai_event_epoch_opened_ankidroid.json"
        write_json(raw, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Opened AnkiDroid",
            "timestamp_epoch": 1777995447,
        })

        assert module.tick() == 0

        assert not read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        failed = find_files(ai_dir / "inbox/from-phone/failed", "*.json")
        assert failed, "bad raw file was not moved to failed"
        errors = find_files(ai_dir / "inbox/from-phone/failed", "*.error.txt")
        assert errors
        assert "unexpanded Tasker variable" in errors[0].read_text(encoding="utf-8")


def test_literal_tasker_variable_timestamp_is_failed() -> None:
    tmp, ai_dir, module = setup_ai_dir()
    with tmp:
        raw = ai_dir / "inbox/from-phone/events/1777995447_opened_ankidroid.json"
        write_json(raw, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Opened AnkiDroid",
            "timestamp_epoch": "%ai_event_epoch",
        })

        assert module.tick() == 0

        assert not read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        errors = find_files(ai_dir / "inbox/from-phone/failed", "*.error.txt")
        assert errors
        assert "unexpanded Tasker variable" in errors[0].read_text(encoding="utf-8")


def test_misrouted_action_is_failed() -> None:
    tmp, ai_dir, module = setup_ai_dir()
    with tmp:
        raw = ai_dir / "inbox/from-phone/events/1777995447_start_recovery_target.json"
        write_json(raw, {
            "schema_version": "action.v1",
            "source": "tasker",
            "device": "phone",
            "action": "start_recovery_target",
            "event": "start_recovery_target",
            "timestamp_epoch": 1777995447,
        })

        assert module.tick() == 0

        assert not read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        errors = find_files(ai_dir / "inbox/from-phone/failed", "*.error.txt")
        assert errors
        assert "misrouted action file" in errors[0].read_text(encoding="utf-8")



def test_queue_ignores_partial_dotfiles_and_non_json() -> None:
    tmp, ai_dir, module = setup_ai_dir()
    with tmp:
        raw_dir = ai_dir / "inbox/from-phone/events"

        hidden = raw_dir / ".1777998501_opened_ankidroid.json"
        write_json(hidden, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Hidden temp event",
            "timestamp_epoch": 1777998501,
        })

        temp = raw_dir / "1777998502_opened_ankidroid.json.tmp"
        temp.write_text("{not complete json", encoding="utf-8")

        partial = raw_dir / "1777998503_opened_ankidroid.partial"
        partial.write_text("partial", encoding="utf-8")

        non_json = raw_dir / "README.md"
        non_json.write_text("not a queue item", encoding="utf-8")

        valid = raw_dir / "1777998504_opened_ankidroid.json"
        write_json(valid, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Valid queue event",
            "timestamp_epoch": 1777998504,
            "tasker_date": "05-05-2026",
            "tasker_time": "18.28",
        })

        assert module.tick() == 1

        events = read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        assert len(events) == 1
        assert events[0]["message"] == "Valid queue event"

        assert not valid.exists()
        assert hidden.exists()
        assert temp.exists()
        assert partial.exists()
        assert non_json.exists()
        assert not find_files(ai_dir / "inbox/from-phone/failed", "*")


def test_once_mode_processes_and_exits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ai_dir = Path(tmp) / "AI"
        raw_dir = ai_dir / "inbox/from-phone/events"
        raw_dir.mkdir(parents=True)

        event_path = raw_dir / "1777998500_opened_ankidroid.json"
        write_json(event_path, {
            "schema_version": "event.v1",
            "source": "tasker",
            "device": "phone",
            "event": "opened_ankidroid",
            "message": "Once mode smoke",
            "timestamp_epoch": "1777998500",
            "tasker_date": "05-05-2026",
            "tasker_time": "18.28",
        })

        proc = run_bridge(
            ai_dir,
            "--once",
            extra_env={
                "STABILITY_SECONDS": "0",
                "CREATE_TEMPLATES": "0",
            },
        )

        assert proc.returncode == 0, proc.stderr
        assert "processed 1 phone event(s)" in proc.stdout
        assert not event_path.exists(), "raw event should be moved out of inbox"

        events = read_jsonl(ai_dir / "events/phone/2026-05-05.jsonl")
        assert len(events) == 1
        assert events[0]["message"] == "Once mode smoke"

def main() -> None:
    tests = [
        test_valid_phone_event_is_processed,
        test_queue_ignores_partial_dotfiles_and_non_json,
        test_literal_tasker_variable_filename_is_failed,
        test_literal_tasker_variable_timestamp_is_failed,
        test_misrouted_action_is_failed,
        test_once_mode_processes_and_exits,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
