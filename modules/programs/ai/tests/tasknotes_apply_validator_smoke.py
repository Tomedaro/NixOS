#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.tasknotes_apply_validator import validate_tasknotes_apply_candidate


def valid_draft() -> dict:
    return {
        "schema_version": "obsidian_task_draft.v1",
        "task_id": "task-linear-algebra",
        "title": "Do one linear algebra exercise",
        "markdown": "- [ ] Do one linear algebra exercise",
        "tasknote_frontmatter": {
            "status": "todo",
            "project": "study",
        },
        "source_proposal_id": "proposal-123",
        "source_intent_id": "intent-456",
        "requires_templater_apply": True,
        "executes_now": False,
        "writes_live_action_queue": False,
        "edits_obsidian_now": False,
    }


def valid_reviewed_proposal() -> dict:
    return {
        "schema_version": "obsidian_reviewed_proposal.v1",
        "status": "review_ready",
        "proposal_id": "proposal-123",
        "intent_id": "intent-456",
        "executes_now": False,
        "writes_live_action_queue": False,
        "requires_capability_bridge": True,
    }


def snapshot_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}

    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_matching_draft_and_reviewed_proposal_is_accepted() -> None:
    with tempfile.TemporaryDirectory(prefix="tasknotes-apply-validator-") as tmp:
        tasknotes = Path(tmp) / "TaskNotes"
        before = snapshot_tree(tasknotes)

        result = validate_tasknotes_apply_candidate(
            valid_draft(),
            approval=valid_reviewed_proposal(),
            tasknotes_dir=tasknotes,
            input_draft_path="AI/outbox/to-obsidian/task-drafts/task-linear-algebra.json",
        )
        repeat = validate_tasknotes_apply_candidate(
            valid_draft(),
            approval=valid_reviewed_proposal(),
            tasknotes_dir=tasknotes,
        )

        after = snapshot_tree(tasknotes)

        assert before == after
        assert result["schema_version"] == "tasknotes_apply_validation_result.v1"
        assert result["status"] == "accepted"
        assert result["writes_tasknotes"] is False
        assert result["reasons"] == []
        assert result["warnings"] == []
        assert result["task_id"] == "task-linear-algebra"
        assert result["source_proposal_id"] == "proposal-123"
        assert result["source_intent_id"] == "intent-456"
        assert result["idempotency_key"] == repeat["idempotency_key"]
        assert result["input_draft_path"].endswith("task-linear-algebra.json")
        assert result["approval_path"] == ""
        assert result["target_tasknotes_path_candidate"].endswith(
            "TaskNotes/Tasks/task-linear-algebra.md"
        )
        assert result["collision_checked"] is True


def test_missing_approval_is_refused() -> None:
    result = validate_tasknotes_apply_candidate(valid_draft())

    assert result["status"] == "refused"
    assert result["writes_tasknotes"] is False
    assert "missing_approval" in result["reasons"]


def test_proposal_id_mismatch_is_refused() -> None:
    approval = valid_reviewed_proposal()
    approval["proposal_id"] = "other-proposal"

    result = validate_tasknotes_apply_candidate(valid_draft(), approval=approval)

    assert result["status"] == "refused"
    assert "approval_proposal_mismatch" in result["reasons"]


def test_intent_id_mismatch_is_refused() -> None:
    approval = valid_reviewed_proposal()
    approval["intent_id"] = "other-intent"

    result = validate_tasknotes_apply_candidate(valid_draft(), approval=approval)

    assert result["status"] == "refused"
    assert "approval_intent_mismatch" in result["reasons"]


def test_reviewed_proposal_shape_is_required() -> None:
    approval = valid_reviewed_proposal()
    approval["schema_version"] = "obsidian_proposal_action.v1"

    result = validate_tasknotes_apply_candidate(valid_draft(), approval=approval)

    assert result["status"] == "refused"
    assert "approval_wrong_schema_version" in result["reasons"]


def test_direct_execution_field_is_refused() -> None:
    draft = valid_draft()
    draft["shell_command"] = "rm -rf /"

    result = validate_tasknotes_apply_candidate(draft, approval=valid_reviewed_proposal())

    assert result["status"] == "refused"
    assert "direct_execution_fields_present" in result["reasons"]


def test_mutating_flags_are_refused() -> None:
    for field in ["writes_live_action_queue", "executes_now", "edits_obsidian_now"]:
        draft = valid_draft()
        draft[field] = True

        result = validate_tasknotes_apply_candidate(
            draft,
            approval=valid_reviewed_proposal(),
        )

        assert result["status"] == "refused"
        assert f"{field}_not_false" in result["reasons"]


def test_missing_required_draft_fields_are_refused() -> None:
    for field in [
        "task_id",
        "title",
        "markdown",
        "tasknote_frontmatter",
        "source_proposal_id",
        "source_intent_id",
    ]:
        draft = valid_draft()
        draft.pop(field)

        result = validate_tasknotes_apply_candidate(
            draft,
            approval=valid_reviewed_proposal(),
        )

        assert result["status"] == "refused"
        assert f"missing_{field}" in result["reasons"]


def test_unsafe_task_id_is_refused() -> None:
    draft = valid_draft()
    draft["task_id"] = "../unsafe"

    result = validate_tasknotes_apply_candidate(
        draft,
        approval=valid_reviewed_proposal(),
    )

    assert result["status"] == "refused"
    assert "unsafe_task_id" in result["reasons"]
    assert result["writes_tasknotes"] is False


def test_existing_tasknotes_target_requires_manual_review_and_does_not_write() -> None:
    with tempfile.TemporaryDirectory(prefix="tasknotes-apply-validator-existing-") as tmp:
        tasknotes = Path(tmp) / "TaskNotes"
        tasks = tasknotes / "Tasks"
        tasks.mkdir(parents=True)
        target = tasks / "task-linear-algebra.md"
        target.write_text("existing content\n", encoding="utf-8")

        before = snapshot_tree(tasknotes)

        result = validate_tasknotes_apply_candidate(
            valid_draft(),
            approval=valid_reviewed_proposal(),
            tasknotes_dir=tasknotes,
        )

        after = snapshot_tree(tasknotes)

        assert before == after
        assert result["status"] == "manual_review_required"
        assert result["writes_tasknotes"] is False
        assert "target_tasknotes_file_exists" in result["reasons"]
        assert result["collision_checked"] is True
        assert result["target_tasknotes_path_candidate"].endswith(
            "TaskNotes/Tasks/task-linear-algebra.md"
        )


def test_missing_tasknotes_dir_still_accepts_without_collision_check() -> None:
    result = validate_tasknotes_apply_candidate(
        valid_draft(),
        approval=valid_reviewed_proposal(),
    )

    assert result["status"] == "accepted"
    assert result["writes_tasknotes"] is False
    assert result["collision_checked"] is False
    assert result["target_tasknotes_path_candidate"] == "Tasks/task-linear-algebra.md"
    assert "target_collision_not_checked_missing_tasknotes_dir" in result["warnings"]


def test_validator_loads_current_approved_proposal_file_without_writes() -> None:
    with tempfile.TemporaryDirectory(prefix="tasknotes-apply-validator-approval-") as tmp:
        root = Path(tmp)
        ai_dir = root / "AI"
        approval_path = ai_dir / "state" / "obsidian" / "current-approved-proposal.json"
        approval_path.parent.mkdir(parents=True)
        approval_path.write_text(
            json.dumps(valid_reviewed_proposal(), indent=2),
            encoding="utf-8",
        )

        tasknotes = root / "TaskNotes"
        before = snapshot_tree(tasknotes)

        result = validate_tasknotes_apply_candidate(
            valid_draft(),
            ai_dir=ai_dir,
            tasknotes_dir=tasknotes,
        )

        after = snapshot_tree(tasknotes)

        assert before == after
        assert result["status"] == "accepted"
        assert result["writes_tasknotes"] is False
        assert result["approval_path"].endswith("current-approved-proposal.json")


def run_all() -> None:
    tests = [
        test_matching_draft_and_reviewed_proposal_is_accepted,
        test_missing_approval_is_refused,
        test_proposal_id_mismatch_is_refused,
        test_intent_id_mismatch_is_refused,
        test_reviewed_proposal_shape_is_required,
        test_direct_execution_field_is_refused,
        test_mutating_flags_are_refused,
        test_missing_required_draft_fields_are_refused,
        test_unsafe_task_id_is_refused,
        test_existing_tasknotes_target_requires_manual_review_and_does_not_write,
        test_missing_tasknotes_dir_still_accepts_without_collision_check,
        test_validator_loads_current_approved_proposal_file_without_writes,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
