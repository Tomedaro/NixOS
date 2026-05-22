#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
DIALOG_BRIDGE = REPO / "modules/programs/ai/dialog-bridge/dialog_bridge.py"

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_dialog_bridge(
    ai_dir: Path,
    notify_send: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["AI_DIR"] = str(ai_dir)
    env["NOTIFY_SEND"] = str(notify_send) if notify_send is not None else "false"
    env["PYTHONPATH"] = str(REPO / "modules/programs/ai/python") + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    for key, value in (extra_env or {}).items():
        env[key] = value

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


def test_answer_selection_writes_canonical_action_file() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-dialog-answer-action-") as tmp:
        root = Path(tmp)
        ai_dir = root / "AI"
        fake_notify = root / "notify-send"
        fake_notify.write_text(
            "#!/usr/bin/env sh\nprintf '%s\\n' overwhelmed\n",
            encoding="utf-8",
        )
        fake_notify.chmod(0o755)

        write_json(
            ai_dir / "state/llm/pending-question.json",
            {
                "question_id": "q-dialog-smoke",
                "question": "What is blocking you?",
                "reason": "Smoke test",
                "answer_options": [
                    {"id": "overwhelmed", "label": "Overwhelmed"},
                    {"id": "tired", "label": "Tired"},
                ],
                "free_text_allowed": True,
            },
        )

        proc = run_dialog_bridge(ai_dir, notify_send=fake_notify)

        assert (
            proc.returncode == 0
        ), f"dialog bridge failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        assert "queued answer_question action" in proc.stdout

        action_files = sorted((ai_dir / "inbox/actions").glob("*.json"))
        assert len(action_files) == 1
        action = read_json(action_files[0])

        assert action["schema_version"] == "action.v1"
        assert action["action"] == "answer_question"
        assert action["action_id"] == "dialog-answer-q-dialog-smoke-overwhelmed"
        assert action["source"] == "dialog-bridge"
        assert action["device"] == "desktop"
        assert action["question_id"] == "q-dialog-smoke"
        assert action["answer"] == "overwhelmed"
        assert action["answer_label"] == "Overwhelmed"
        assert action["free_text"] == ""

        assert not list(
            (ai_dir / "inbox/from-desktop/events").rglob("*question_answered*.json")
        )
        assert not (ai_dir / "events/desktop").exists()
        assert not (ai_dir / "state/llm/last-answer.json").exists()
        assert (ai_dir / "state/llm/pending-question.json").exists()
        assert not list((ai_dir / "state/llm/questions/archive").rglob("*.json"))

        dialog_state = read_json(ai_dir / "state/desktop/dialog-bridge-state.json")
        question_state = dialog_state["questions"]["q-dialog-smoke"]
        assert question_state["status"] == "answer_queued"
        assert question_state["last_answer_action_id"] == action["action_id"]

        current_question = (
            ai_dir / "outbox/to-phone/current-question.md"
        ).read_text(encoding="utf-8")
        assert "Status: active" in current_question
        assert "Reason: answered" not in current_question


def main() -> None:
    tests = [
        test_no_pending_question_writes_inactive_markdown,
        test_answer_selection_writes_canonical_action_file,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
