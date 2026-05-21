#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.obsidian_task_draft import normalize_task_draft, write_task_draft


def approved_payload() -> dict:
    return {
        "schema_version": "obsidian_approval_bridge_result.v1",
        "approved": True,
        "decision": "approve_proposal",
        "proposal": {
            "schema_version": "obsidian_proposal.v1",
            "proposal_id": "proposal-intent-study-1",
            "intent_id": "intent-study-1",
            "proposal_kind": "next_goal_step",
            "summary": "Do one linear algebra exercise",
            "message_markdown": "A good next step is one small linear algebra exercise.",
            "goal_ids": ["stem-study"],
            "suggested_actions": [
                {
                    "type": "draft_task",
                    "label": "Do one linear algebra exercise",
                    "priority": "high",
                    "energy": "medium",
                    "estimated_minutes": 20,
                    "goal_id": "stem-study",
                    "area": "study",
                }
            ],
        },
    }


def test_approved_proposal_normalizes_to_tasknotes_draft() -> None:
    draft = normalize_task_draft(approved_payload())

    assert draft["schema_version"] == "obsidian_task_draft.v1"
    assert draft["title"] == "Do one linear algebra exercise"
    assert draft["goal_id"] == "stem-study"
    assert draft["priority"] == "high"
    assert draft["energy"] == "medium"
    assert draft["estimated_minutes"] == 20
    assert draft["requires_templater_apply"] is True
    assert draft["executes_now"] is False
    assert draft["writes_live_action_queue"] is False

    fm = draft["tasknote_frontmatter"]
    assert fm["ai_created"] is True
    assert fm["agent_created"] is True
    assert fm["source_proposal_id"] == "proposal-intent-study-1"
    assert fm["source_intent_id"] == "intent-study-1"
    assert fm["title"] == "Do one linear algebra exercise"
    assert fm["status"] == "open"
    assert fm["timeEstimate"] == 20
    assert "task" in fm["tags"]
    assert "ai-task" in fm["tags"]
    assert "tasknotes" in fm["tags"]
    assert "ai_created: true" in draft["markdown"]
    assert "agent_created: true" in draft["markdown"]


def test_task_draft_action_is_preferred_over_next_step_summary() -> None:
    payload = approved_payload()
    payload["proposal"]["suggested_actions"].insert(
        0,
        {
            "type": "suggest_next_step",
            "label": "Do one linear algebra exercise",
            "estimated_minutes": 5,
            "priority": "low",
        },
    )

    draft = normalize_task_draft(payload)

    assert draft["priority"] == "high"
    assert draft["estimated_minutes"] == 20
    assert draft["tasknote_frontmatter"]["timeEstimate"] == 20


def test_tasknotes_status_aliases_match_live_config() -> None:
    payload = approved_payload()
    payload["proposal"]["suggested_actions"][0]["status"] = "doing"

    draft = normalize_task_draft(payload)

    assert draft["tasknote_frontmatter"]["status"] == "in-progress"


def test_rejected_or_unapproved_payload_is_refused() -> None:
    payload = approved_payload()
    payload["approved"] = False
    payload["decision"] = "reject_proposal"

    try:
        normalize_task_draft(payload)
    except ValueError as exc:
        assert "approved proposal action is required" in str(exc)
    else:
        raise AssertionError("unapproved proposal should be refused")


def test_direct_execution_fields_are_refused() -> None:
    payload = approved_payload()
    payload["proposal"]["shell_command"] = "rm -rf /"

    try:
        normalize_task_draft(payload)
    except ValueError as exc:
        assert "direct execution fields" in str(exc)
    else:
        raise AssertionError("direct execution proposal should be refused")


def test_write_outputs_reviewable_outbox_only() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-task-draft-") as tmp:
        ai_dir = Path(tmp) / "AI"
        tasknotes_dir = Path(tmp) / "TaskNotes"
        tasknotes_dir.mkdir()
        result = write_task_draft(approved_payload(), ai_dir=ai_dir)

        paths = result["written_paths"]
        draft_json = Path(paths["draft_json"])
        draft_md = Path(paths["draft_markdown"])
        current_json = ai_dir / "outbox/to-obsidian/current-task-draft.json"
        current_md = ai_dir / "outbox/to-obsidian/current-task-draft.md"
        latest_json = ai_dir / "state/obsidian/latest-task-draft.json"

        assert draft_json.exists()
        assert draft_md.exists()
        assert current_json.exists()
        assert current_md.exists()
        assert latest_json.exists()

        assert draft_json.parent == ai_dir / "outbox/to-obsidian/task-drafts"
        assert not (ai_dir / "inbox/actions").exists()
        assert not any(tasknotes_dir.rglob("*"))
        assert not (tasknotes_dir / "Tasks").exists()

        loaded = json.loads(current_json.read_text(encoding="utf-8"))
        assert loaded["title"] == "Do one linear algebra exercise"
        assert loaded["edits_obsidian_now"] is False


def run_all() -> None:
    tests = [
        test_approved_proposal_normalizes_to_tasknotes_draft,
        test_task_draft_action_is_preferred_over_next_step_summary,
        test_tasknotes_status_aliases_match_live_config,
        test_rejected_or_unapproved_payload_is_refused,
        test_direct_execution_fields_are_refused,
        test_write_outputs_reviewable_outbox_only,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
