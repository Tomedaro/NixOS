#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.obsidian_approval_bridge import run_bridge


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def base_proposal() -> dict:
    return {
        "schema_version": "obsidian_proposal.v1",
        "proposal_id": "proposal-intent-1",
        "intent_id": "intent-1",
        "status": "proposed",
        "source": "obsidian-intent-planner",
        "surface": "obsidian",
        "created_at": "2026-05-06T12:00:00+00:00",
        "timestamp_epoch": 1778072400,
        "proposal_kind": "next_goal_step",
        "summary": "Pick a tiny STEM step",
        "message_markdown": "Do one linear algebra exercise.",
        "note_path": "Goals/Today.md",
        "goal_ids": ["stem-study"],
        "task_ids": [],
        "suggested_actions": [
            {
                "type": "draft_task",
                "label": "Draft one Obsidian task",
                "requires_approval": True,
            }
        ],
        "execution_policy": "proposal_only_no_direct_execution",
    }


def base_action(decision: str = "approve_proposal") -> dict:
    return {
        "schema_version": "obsidian_proposal_action.v1",
        "timestamp": "2026-05-06T12:01:00+00:00",
        "timestamp_epoch": 1778072460,
        "source": "obsidian",
        "surface": "obsidian",
        "decision": decision,
        "proposal_id": "proposal-intent-1",
        "proposal_kind": "next_goal_step",
        "approved": decision == "approve_proposal",
        "rejected": decision == "reject_proposal",
        "revision_requested": decision == "revise_proposal",
        "executes_now": False,
        "writes_live_action_queue": False,
        "requires_downstream_bridge": decision == "approve_proposal",
    }


def test_approved_proposal_writes_reviewed_artifact_only() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-approval-bridge-") as tmp:
        ai_dir = Path(tmp) / "AI"

        proposal = base_proposal()
        action = base_action()

        write_json(
            ai_dir / "outbox/to-obsidian/proposals/proposal-intent-1.json",
            proposal,
        )
        action_path = ai_dir / "inbox/obsidian/actions/1_approve.json"
        write_json(action_path, action)

        result = run_bridge(ai_dir, write=True, action_path=action_path)

        assert result["status"] == "review_ready"
        assert result["writes_live_action_queue"] is False

        reviewed_path = (
            ai_dir / "outbox/to-obsidian/approved-proposals/proposal-intent-1.json"
        )
        current_path = ai_dir / "outbox/to-obsidian/current-approved-proposal.json"
        current_md = ai_dir / "outbox/to-obsidian/current-approved-proposal.md"

        assert current_path.exists()
        assert current_md.exists()

        reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
        current = json.loads(current_path.read_text(encoding="utf-8"))
        assert current["proposal_id"] == "proposal-intent-1"

        assert reviewed["schema_version"] == "obsidian_reviewed_proposal.v1"
        assert reviewed["proposal_id"] == "proposal-intent-1"
        assert reviewed["executes_now"] is False
        assert reviewed["writes_live_action_queue"] is False
        assert reviewed["requires_capability_bridge"] is True
        assert not (ai_dir / "inbox/actions").exists()


def test_reject_decision_is_not_bridge_ready() -> None:
    with tempfile.TemporaryDirectory(
        prefix="ai-obsidian-approval-bridge-reject-"
    ) as tmp:
        ai_dir = Path(tmp) / "AI"

        proposal = base_proposal()
        action = base_action("reject_proposal")

        write_json(
            ai_dir / "outbox/to-obsidian/proposals/proposal-intent-1.json",
            proposal,
        )
        action_path = ai_dir / "inbox/obsidian/actions/1_reject.json"
        write_json(action_path, action)

        result = run_bridge(ai_dir, write=True, action_path=action_path)

        assert result["status"] == "rejected"
        assert result["reason"] == "decision_not_approved"
        assert result["writes_live_action_queue"] is False
        assert not (ai_dir / "outbox/to-obsidian/approved-proposals").exists()


def test_mismatched_proposal_is_rejected() -> None:
    with tempfile.TemporaryDirectory(
        prefix="ai-obsidian-approval-bridge-mismatch-"
    ) as tmp:
        ai_dir = Path(tmp) / "AI"

        proposal = base_proposal()
        proposal["proposal_id"] = "proposal-other"
        action = base_action()

        write_json(
            ai_dir / "outbox/to-obsidian/current-proposal.json",
            proposal,
        )
        action_path = ai_dir / "inbox/obsidian/actions/1_approve.json"
        write_json(action_path, action)

        result = run_bridge(ai_dir, write=True, action_path=action_path)

        assert result["status"] == "proposal_not_found"
        assert not (ai_dir / "inbox/actions").exists()


def run_all() -> None:
    tests = [
        test_approved_proposal_writes_reviewed_artifact_only,
        test_reject_decision_is_not_bridge_ready,
        test_mismatched_proposal_is_rejected,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
