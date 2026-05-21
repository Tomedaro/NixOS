#!/usr/bin/env python3

import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
ANKI_BRIDGE = REPO / "modules/programs/ai/anki-bridge/anki_bridge.py"
SHARED_PYTHON = REPO / "modules/programs/ai/python"

if str(SHARED_PYTHON) not in sys.path:
    sys.path.insert(0, str(SHARED_PYTHON))


def load_anki_bridge(ai_dir: Path, tasknotes_dir: Path, extra_env: dict[str, str] | None = None):
    env = {
        "AI_DIR": str(ai_dir),
        "TASKNOTES_DIR": str(tasknotes_dir),
        "ANKI_DECKS_JSON": "[]",
        "ANKI_BRIDGE_TIMEZONE": "Europe/Paris",
    }
    if extra_env:
        env.update(extra_env)

    old_env = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        module_name = f"anki_bridge_smoke_{time.time_ns()}"
        spec = importlib.util.spec_from_file_location(module_name, ANKI_BRIDGE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def available_status() -> dict:
    return {
        "schema_version": "anki-status.v1",
        "available": True,
        "timestamp": "2026-05-21T12:00:00+02:00",
        "date": "2026-05-21",
        "totals": {
            "due": 5,
            "new": 0,
            "learning": 0,
            "review_due": 5,
            "reviewed_today": 0,
            "again_today": 0,
        },
        "overall_priority": "normal",
        "decks": [
            {
                "deck": "General",
                "derived": {
                    "due": 5,
                    "new": 0,
                    "learning": 0,
                    "review_due": 5,
                    "reviewed_today": 0,
                    "again_today": 0,
                    "suggested_goal": "Do a short cleanup block.",
                },
            }
        ],
    }


def test_default_propose_mode_writes_proposal_not_real_tasknotes() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-anki-bridge-propose-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        tasknotes_dir.mkdir(parents=True)

        module = load_anki_bridge(ai_dir, tasknotes_dir)

        assert module.TASKNOTE_MODE == "propose"
        module.ensure_dirs()
        output = module.write_recovery_task_or_proposal(available_status())

        proposal = ai_dir / "proposed-tasks/anki-recovery.md"
        direct_tasknote = tasknotes_dir / "AI/anki-due-recovery.md"

        assert output["mode"] == "propose"
        assert output["path"] == str(proposal)
        assert proposal.exists()
        assert "Proposed by the local AI Anki bridge" in proposal.read_text(encoding="utf-8")
        assert not direct_tasknote.exists()
        assert not any(tasknotes_dir.rglob("*"))


def test_create_tasknote_false_forces_off_without_task_writes() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-anki-bridge-off-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        tasknotes_dir.mkdir(parents=True)

        module = load_anki_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={
                "CREATE_TASKNOTE": "0",
                "TASKNOTE_MODE": "direct",
            },
        )

        assert module.TASKNOTE_MODE == "off"
        module.ensure_dirs()
        output = module.write_recovery_task_or_proposal(available_status())

        assert output is None
        assert not (ai_dir / "proposed-tasks/anki-recovery.md").exists()
        assert not (tasknotes_dir / "AI/anki-due-recovery.md").exists()
        assert not any(tasknotes_dir.rglob("*"))


def test_direct_mode_falls_back_to_propose_without_tasknotes_write() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-anki-bridge-direct-disabled-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        tasknotes_dir.mkdir(parents=True)

        module = load_anki_bridge(
            ai_dir,
            tasknotes_dir,
            extra_env={
                "CREATE_TASKNOTE": "1",
                "TASKNOTE_MODE": "direct",
            },
        )

        assert module.TASKNOTE_MODE == "propose"
        module.ensure_dirs()
        output = module.write_recovery_task_or_proposal(available_status())

        proposal = ai_dir / "proposed-tasks/anki-recovery.md"
        direct_tasknote = tasknotes_dir / "AI/anki-due-recovery.md"

        assert output["mode"] == "propose"
        assert output["path"] == str(proposal)
        assert proposal.exists()
        assert "Proposed by the local AI Anki bridge" in proposal.read_text(encoding="utf-8")
        assert not direct_tasknote.exists()
        assert not any(tasknotes_dir.rglob("*"))


def run_all() -> None:
    tests = [
        test_default_propose_mode_writes_proposal_not_real_tasknotes,
        test_create_tasknote_false_forces_off_without_task_writes,
        test_direct_mode_falls_back_to_propose_without_tasknotes_write,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
