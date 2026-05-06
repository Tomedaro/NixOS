#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.obsidian_proposal_action import (  # noqa: E402
    normalize_proposal_action,
    write_proposal_action,
)


def test_approve_is_bounded_and_non_executing() -> None:
    action = normalize_proposal_action(
        {
            "decision": "approve_proposal",
            "proposal_id": "proposal-123",
            "proposal_kind": "next_step",
            "message": "Yes, do this.",
            "proposal_summary": "Create a tiny STEM next action.",
            "reason_codes": ["user_approved"],
        }
    )

    assert action["schema_version"] == "obsidian_proposal_action.v1"
    assert action["approved"] is True
    assert action["executes_now"] is False
    assert action["writes_live_action_queue"] is False
    assert action["requires_downstream_bridge"] is True


def test_reject_and_revise_are_not_bridge_ready() -> None:
    reject = normalize_proposal_action(
        {
            "decision": "reject_proposal",
            "proposal_id": "proposal-123",
            "message": "Not now.",
        }
    )
    revise = normalize_proposal_action(
        {
            "decision": "revise_proposal",
            "proposal_id": "proposal-123",
            "requested_changes": "Make it smaller.",
        }
    )

    assert reject["rejected"] is True
    assert reject["requires_downstream_bridge"] is False
    assert revise["revision_requested"] is True
    assert revise["requires_downstream_bridge"] is False


def test_unknown_decision_is_rejected() -> None:
    try:
        normalize_proposal_action(
            {
                "decision": "run_shell_command",
                "proposal_id": "proposal-123",
            }
        )
    except ValueError as exc:
        assert "unsupported proposal decision" in str(exc)
    else:
        raise AssertionError("expected unsupported decision to fail")


def test_write_goes_to_obsidian_inbox_not_live_action_queue() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-proposal-action-") as tmp:
        ai_dir = Path(tmp) / "AI"
        result = write_proposal_action(
            {
                "decision": "approve_proposal",
                "proposal_id": "proposal-approve",
                "proposal_kind": "next_step",
                "message": "Approved.",
            },
            ai_dir=ai_dir,
        )

        written = Path(result["written_path"])
        latest = ai_dir / "state/obsidian/latest-proposal-action.json"
        live_action_queue = ai_dir / "inbox/actions"

        assert written.exists()
        assert written.parent == ai_dir / "inbox/obsidian/actions"
        assert latest.exists()
        assert not live_action_queue.exists()

        data = json.loads(written.read_text(encoding="utf-8"))
        assert data["decision"] == "approve_proposal"
        assert data["writes_live_action_queue"] is False


def run_all() -> None:
    tests = [
        test_approve_is_bounded_and_non_executing,
        test_reject_and_revise_are_not_bridge_ready,
        test_unknown_decision_is_rejected,
        test_write_goes_to_obsidian_inbox_not_live_action_queue,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
