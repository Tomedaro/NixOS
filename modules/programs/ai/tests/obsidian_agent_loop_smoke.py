#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "modules/programs/ai/dev/run-obsidian-agent-loop.sh"


def run_loop(*args: str, ai_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AI_DIR"] = str(ai_dir)
    env["PYTHONPATH"] = str(REPO_ROOT / "modules/programs/ai/python")
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_help_is_available() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-help-") as tmp:
        result = run_loop("--help", ai_dir=Path(tmp) / "AI")

    assert result.returncode == 0
    assert "Inspect-first Obsidian agent operator loop" in result.stdout
    assert "--write-proposal" in result.stdout


def test_default_loop_is_non_mutating_without_inputs() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-") as tmp:
        ai_dir = Path(tmp) / "AI"
        result = run_loop(ai_dir=ai_dir)

        assert result.returncode == 0, result.stdout
        assert "writes_live_action_queue=false" in result.stdout
        assert "edits_obsidian_now=false" in result.stdout
        assert "auto_approval=false" in result.stdout
        assert not (ai_dir / "inbox/actions").exists()
        assert not (ai_dir / "outbox/to-obsidian/current-proposal.json").exists()


def test_write_proposal_only_writes_reviewable_outbox() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-write-") as tmp:
        ai_dir = Path(tmp) / "AI"
        inbox = ai_dir / "inbox/obsidian/messages"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "intent-study.json").write_text(
            """
{
  "schema_version": "obsidian_intent.v1",
  "status": "pending",
  "intent_id": "intent-study",
  "kind": "message",
  "message": "Help me choose a tiny STEM next action.",
  "goal_ids": ["stem-study"],
  "note_path": "Goals/Today.md"
}
""".strip()
            + "\n",
            encoding="utf-8",
        )

        result = run_loop("--write-proposal", ai_dir=ai_dir)

        assert result.returncode == 0, result.stdout
        assert (ai_dir / "outbox/to-obsidian/current-proposal.json").exists()
        assert (ai_dir / "outbox/to-obsidian/current-proposal.md").exists()
        assert not (ai_dir / "inbox/actions").exists()


def run_all() -> None:
    tests = [
        test_help_is_available,
        test_default_loop_is_non_mutating_without_inputs,
        test_write_proposal_only_writes_reviewable_outbox,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
