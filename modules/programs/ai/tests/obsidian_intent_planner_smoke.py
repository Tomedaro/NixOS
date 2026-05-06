#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.obsidian_ingress import build_intent, write_intent
from ai_system.obsidian_intent_planner import build_proposal, run_planner


def test_goal_message_builds_next_step_proposal() -> None:
    intent = build_intent(
        message="Help me choose the next useful action.",
        note_path="Goals/Today.md",
        goal_ids=["stem-study"],
        now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
    )

    context = {
        "generated_at": "2026-05-06T12:00:00+00:00",
        "context_hub": {
            "facts": {
                "obsidian": {},
                "activitywatch": {},
                "interaction": {},
                "recovery": {},
            }
        },
    }

    proposal = build_proposal(
        intent,
        context,
        now=datetime(2026, 5, 6, 12, 1, tzinfo=timezone.utc),
    )

    assert proposal["schema_version"] == "obsidian_proposal.v1"
    assert proposal["status"] == "proposed"
    assert proposal["proposal_kind"] == "next_goal_step"
    assert proposal["execution_policy"] == "proposal_only_no_direct_execution"
    assert proposal["goal_ids"] == ["stem-study"]
    assert "AI Proposal" in proposal["markdown"]


def test_action_request_stays_review_only() -> None:
    intent = build_intent(
        action="create_task",
        note_path="Goals/Today.md",
        now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
    )

    proposal = build_proposal(
        intent,
        {"context_hub": {"facts": {}}},
        now=datetime(2026, 5, 6, 12, 1, tzinfo=timezone.utc),
    )

    assert proposal["proposal_kind"] == "review_action_request"
    assert proposal["suggested_actions"][0]["requires_approval"] is True
    assert "direct" not in proposal["suggested_actions"][0]["type"]


def test_run_planner_writes_current_proposal() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-planner-") as tmp:
        ai_dir = Path(tmp) / "AI"

        intent = build_intent(
            message="Pick a next CLI learning step.",
            note_path="Goals/CLI.md",
            goal_ids=["cli-learning"],
            now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        )
        write_intent(ai_dir, intent)

        result = run_planner(ai_dir, write=True)

        assert result["status"] == "proposal_built"
        paths = result["written_paths"]
        current = Path(paths["current_json"])
        current_md = Path(paths["current_markdown"])

        assert current.exists()
        assert current_md.exists()

        proposal = json.loads(current.read_text(encoding="utf-8"))
        assert proposal["intent_id"] == intent["intent_id"]
        assert proposal["execution_policy"] == "proposal_only_no_direct_execution"
        assert "# AI Proposal" in current_md.read_text(encoding="utf-8")


def test_no_pending_intent_is_nonfatal() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-planner-empty-") as tmp:
        ai_dir = Path(tmp) / "AI"
        result = run_planner(ai_dir, write=True)

        assert result["status"] == "no_pending_intent"


def run_all() -> None:
    tests = [
        test_goal_message_builds_next_step_proposal,
        test_action_request_stays_review_only,
        test_run_planner_writes_current_proposal,
        test_no_pending_intent_is_nonfatal,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
