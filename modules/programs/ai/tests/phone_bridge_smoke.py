#!/usr/bin/env python3

import importlib.util
import json
import os
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PHONE_BRIDGE = REPO_ROOT / "modules/programs/ai/phone-bridge/phone_bridge.py"


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
        assert list((ai_dir / "inbox/from-phone/processed/2026-05-05").glob("*.json"))


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
        failed = list((ai_dir / "inbox/from-phone/failed/2026-05-05").glob("*.json"))
        assert failed, "bad raw file was not moved to failed"
        errors = list((ai_dir / "inbox/from-phone/failed/2026-05-05").glob("*.error.txt"))
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
        errors = list((ai_dir / "inbox/from-phone/failed/2026-05-05").glob("*.error.txt"))
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
        errors = list((ai_dir / "inbox/from-phone/failed/2026-05-05").glob("*.error.txt"))
        assert errors
        assert "misrouted action file" in errors[0].read_text(encoding="utf-8")


def main() -> None:
    tests = [
        test_valid_phone_event_is_processed,
        test_literal_tasker_variable_filename_is_failed,
        test_literal_tasker_variable_timestamp_is_failed,
        test_misrouted_action_is_failed,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
