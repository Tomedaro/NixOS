#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.agent_context import build_agent_context
from ai_system.obsidian_ingress import build_intent, write_intent


def test_message_intent_is_bounded_and_non_executing() -> None:
    intent = build_intent(
        message="x" * 3000,
        note_path="Daily/Today.md",
        selected_text="y" * 3000,
        goal_ids=["stem-study,cli-learning", "stem-study"],
        now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
    )

    assert intent["schema_version"] == "obsidian_intent.v1"
    assert intent["kind"] == "message"
    assert intent["status"] == "pending"
    assert intent["execution_policy"] == "planner_must_decide_no_direct_execution"
    assert intent["goal_ids"] == ["stem-study", "cli-learning"]
    assert len(intent["message"]) <= 2000
    assert len(intent["selected_text_preview"]) <= 1200
    assert "requested_action" not in intent


def test_action_request_is_not_direct_execution() -> None:
    intent = build_intent(
        action="create_task",
        note_path="Goals/Today.md",
        task_ids=["task-1"],
        now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
    )

    assert intent["kind"] == "action_request"
    assert intent["requested_action"] == "create_task"
    assert intent["execution_policy"] == "planner_must_decide_no_direct_execution"


def test_write_intent_feeds_context_hub() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-ingress-") as tmp:
        ai_dir = Path(tmp) / "AI"

        intent = build_intent(
            message="Help me pick the next study action.",
            note_path="Goals/Today.md",
            goal_ids=["stem-study"],
            now=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        )
        path = write_intent(ai_dir, intent)

        assert path.exists()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["intent_id"] == intent["intent_id"]

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        hub_facts = context["context_hub"]["facts"]

        assert "obsidian_intent" in hub_facts
        assert hub_facts["obsidian_intent"]["pending_count_seen"] == 1
        assert (
            hub_facts["obsidian_intent"]["latest"]["message_preview"]
            == "Help me pick the next study action."
        )


def run_all() -> None:
    tests = [
        test_message_intent_is_bounded_and_non_executing,
        test_action_request_is_not_direct_execution,
        test_write_intent_feeds_context_hub,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
