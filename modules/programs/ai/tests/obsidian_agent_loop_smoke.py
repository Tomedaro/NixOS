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
    assert "--validate-task-draft" in result.stdout


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


def write_pending_intent(ai_dir: Path) -> None:
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


def approve_current_proposal(ai_dir: Path) -> None:
    import json

    proposal = json.loads(
        (ai_dir / "outbox/to-obsidian/current-proposal.json").read_text(
            encoding="utf-8"
        )
    )
    inbox = ai_dir / "inbox/obsidian/actions"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "approve-proposal.json").write_text(
        json.dumps(
            {
                "schema_version": "obsidian_proposal_action.v1",
                "timestamp": "2026-05-06T16:00:00+00:00",
                "timestamp_epoch": 1778083200,
                "source": "obsidian",
                "surface": "obsidian",
                "decision": "approve_proposal",
                "proposal_id": proposal["proposal_id"],
                "proposal_kind": proposal["proposal_kind"],
                "approved": True,
                "rejected": False,
                "revision_requested": False,
                "executes_now": False,
                "writes_live_action_queue": False,
                "requires_downstream_bridge": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_bridge_approved_proposal_writes_reviewed_outbox_only() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-bridge-") as tmp:
        ai_dir = Path(tmp) / "AI"
        write_pending_intent(ai_dir)

        proposal_result = run_loop("--write-proposal", ai_dir=ai_dir)
        assert proposal_result.returncode == 0, proposal_result.stdout

        approve_current_proposal(ai_dir)

        bridge_result = run_loop("--bridge-approved-proposal", ai_dir=ai_dir)

        assert bridge_result.returncode == 0, bridge_result.stdout
        assert "approval bridge" in bridge_result.stdout
        assert not (ai_dir / "inbox/actions").exists()
        assert (ai_dir / "outbox/to-obsidian/current-approved-proposal.json").exists()


def test_write_task_draft_creates_reviewable_tasknotes_draft_only() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-task-draft-") as tmp:
        ai_dir = Path(tmp) / "AI"
        write_pending_intent(ai_dir)

        proposal_result = run_loop("--write-proposal", ai_dir=ai_dir)
        assert proposal_result.returncode == 0, proposal_result.stdout

        approve_current_proposal(ai_dir)

        draft_result = run_loop("--write-task-draft", ai_dir=ai_dir)

        assert draft_result.returncode == 0, draft_result.stdout
        assert (ai_dir / "outbox/to-obsidian/current-task-draft.json").exists()
        assert (ai_dir / "outbox/to-obsidian/current-task-draft.md").exists()
        assert not (ai_dir / "inbox/actions").exists()



def test_validate_task_draft_is_non_writing_dry_run() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-loop-validate-task-") as tmp:
        root = Path(tmp)
        ai_dir = root / "AI"
        tasknotes_dir = root / "TaskNotes"
        write_pending_intent(ai_dir)

        proposal_result = run_loop("--write-proposal", ai_dir=ai_dir)
        assert proposal_result.returncode == 0, proposal_result.stdout

        approve_current_proposal(ai_dir)

        draft_result = run_loop("--write-task-draft", ai_dir=ai_dir)
        assert draft_result.returncode == 0, draft_result.stdout
        assert (ai_dir / "outbox/to-obsidian/current-task-draft.json").exists()
        assert not tasknotes_dir.exists()

        validate_result = run_loop("--validate-task-draft", ai_dir=ai_dir)

        assert validate_result.returncode == 0, validate_result.stdout
        assert "tasknotes_apply_validation_result.v1" in validate_result.stdout
        assert "status=accepted" in validate_result.stdout
        assert "writes_tasknotes=false" in validate_result.stdout
        assert "idempotency_key=tasknotes_apply:" in validate_result.stdout
        assert "collision_checked=true" in validate_result.stdout
        assert "reasons=[]" in validate_result.stdout
        assert not (ai_dir / "inbox/actions").exists()
        assert not tasknotes_dir.exists()

def run_all() -> None:
    tests = [
        test_help_is_available,
        test_default_loop_is_non_mutating_without_inputs,
        test_write_proposal_only_writes_reviewable_outbox,
        test_bridge_approved_proposal_writes_reviewed_outbox_only,
        test_write_task_draft_creates_reviewable_tasknotes_draft_only,
        test_validate_task_draft_is_non_writing_dry_run,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
