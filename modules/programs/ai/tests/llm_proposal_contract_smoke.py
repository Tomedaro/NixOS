#!/usr/bin/env python3

from __future__ import annotations

import json

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.llm_proposal_contract import (
    build_llm_prompt_package,
    fallback_proposal_from_intent,
    parse_json_object,
    sanitize_llm_obsidian_proposal,
    validate_llm_obsidian_proposal,
)


def sample_intent() -> dict:
    return {
        "schema_version": "obsidian_intent.v1",
        "intent_id": "intent-study-1",
        "kind": "message",
        "source": "obsidian",
        "surface": "obsidian",
        "mode": "mentor",
        "note_path": "Goals/Today.md",
        "message": "Help me make progress on linear algebra.",
        "goal_ids": ["stem-study"],
    }


def sample_context() -> dict:
    return {
        "schema_version": "agent_context.v1",
        "generated_at": "2026-05-06T18:00:00+02:00",
        "timestamp_epoch": 1778083200,
        "context_hub": {
            "schema_version": "context_hub.v1",
            "facts": {
                "obsidian": {
                    "active_note_path": "Goals/Today.md",
                    "open_tasks": [
                        {
                            "text": "Do one linear algebra exercise",
                            "goal_id": "stem-study",
                        }
                    ],
                    "large_raw_payload_that_should_not_leak": "x" * 1000,
                },
                "recovery": {
                    "status": "possible_success",
                    "raw": {"large": "should not leak"},
                },
                "interaction": {"active_nudge_status": "none"},
            },
            "warnings": [],
        },
    }


def test_prompt_package_is_bounded_and_llm_specific() -> None:
    package = build_llm_prompt_package(sample_intent(), sample_context())

    assert package["schema_version"] == "llm_prompt_package.v1"
    assert "Return JSON only." in package["safety_rules"]
    assert package["intent"]["intent_id"] == "intent-study-1"
    assert package["expected_output"]["schema_version"] == "obsidian_proposal.v1"

    text = str(package)
    assert "large_raw_payload_that_should_not_leak" not in text
    assert "'raw':" not in text


def test_valid_llm_proposal_is_sanitized_to_obsidian_contract() -> None:
    candidate = {
        "schema_version": "obsidian_proposal.v1",
        "proposal_kind": "next_goal_step",
        "summary": "Do one linear algebra exercise",
        "message_markdown": "Do one short exercise, then stop.",
        "goal_ids": ["stem-study"],
        "suggested_actions": [
            {
                "type": "draft_task",
                "label": "Draft task: one linear algebra exercise",
                "title": "Do one linear algebra exercise",
                "estimated_minutes": 20,
                "requires_approval": True,
            }
        ],
    }

    result = validate_llm_obsidian_proposal(
        candidate, sample_intent(), sample_context()
    )

    assert result["valid"] is True
    proposal = result["proposal"]
    assert proposal["schema_version"] == "obsidian_proposal.v1"
    assert proposal["source"] == "llm-proposal-contract"
    assert proposal["execution_policy"] == "proposal_only_no_direct_execution"
    assert proposal["suggested_actions"][0]["type"] == "draft_task"
    assert proposal["suggested_actions"][0]["requires_approval"] is True


def test_direct_execution_fields_are_rejected() -> None:
    candidate = {
        "proposal_kind": "next_goal_step",
        "summary": "Run command",
        "message_markdown": "I will run this now.",
        "shell_command": "rm -rf /",
        "suggested_actions": [],
    }

    result = validate_llm_obsidian_proposal(
        candidate, sample_intent(), sample_context()
    )

    assert result["valid"] is False
    assert "direct execution fields" in result["error"]


def test_fallback_proposal_is_safe_and_task_draftable() -> None:
    proposal = fallback_proposal_from_intent(sample_intent(), sample_context())

    assert proposal["schema_version"] == "obsidian_proposal.v1"
    assert proposal["source"] == "llm-proposal-contract-fallback"
    assert proposal["proposal_kind"] == "next_goal_step"
    assert proposal["suggested_actions"][0]["type"] == "draft_task"
    assert proposal["suggested_actions"][0]["requires_approval"] is True
    assert proposal["execution_policy"] == "proposal_only_no_direct_execution"


def test_json_parser_accepts_wrapped_json() -> None:
    parsed = parse_json_object(
        'Here is JSON:\\n{"summary": "x", "proposal_kind": "clarify_or_plan"}\\nThanks'
    )
    assert parsed["summary"] == "x"



def tasknotes_context_hub_fixture() -> dict:
    return {
        "schema_version": "context_hub.v1",
        "available": True,
        "provider_count": 1,
        "providers": [
            {
                "name": "tasknotes.read_context",
                "available": True,
                "freshness": "1780000000",
                "source_paths": [
                    "/tmp/example/TaskNotes/Tasks",
                ],
                "warnings": [
                    "tasknotes.read_context is bounded/truncated",
                ],
                "facts": {
                    "module": "tasknotes.read_context",
                    "status": "ok",
                    "available": True,
                    "generated_at_epoch": 1780000000,
                    "limits": {
                        "file_limit": 12,
                        "bytes_per_file": 4096,
                        "total_bytes": 32768,
                    },
                    "item_count": 12,
                    "truncated": True,
                    "omitted": {
                        "over_limit": 2,
                        "unreadable": 0,
                        "bytes": 2048,
                    },
                    "source": {
                        "kind": "TaskNotes/Tasks",
                        "tasks_root": "/tmp/example/TaskNotes/Tasks",
                    },
                    "provenance": {
                        "item_paths": [
                            "Tasks/00.md",
                            "Tasks/01.md",
                        ],
                    },
                    "may_mutate_tasknotes": False,
                    "required_action_capabilities": [],
                },
            },
        ],
        "facts": {
            "tasknotes.read_context": {
                "module": "tasknotes.read_context",
                "status": "ok",
                "available": True,
                "generated_at_epoch": 1780000000,
                "limits": {
                    "file_limit": 12,
                    "bytes_per_file": 4096,
                    "total_bytes": 32768,
                },
                "item_count": 12,
                "truncated": True,
                "omitted": {
                    "over_limit": 2,
                    "unreadable": 0,
                    "bytes": 2048,
                },
                "source": {
                    "kind": "TaskNotes/Tasks",
                    "tasks_root": "/tmp/example/TaskNotes/Tasks",
                },
                "provenance": {
                    "item_paths": [
                        "Tasks/00.md",
                        "Tasks/01.md",
                    ],
                },
                "may_mutate_tasknotes": False,
                "required_action_capabilities": [],
            },
        },
    }


def test_prompt_package_includes_tasknotes_read_context_metadata() -> None:
    package = build_llm_prompt_package(
        {"kind": "review_tasknotes_context"},
        {"context_hub": tasknotes_context_hub_fixture()},
    )

    tasknotes = package["context"]["tasknotes_read_context"]

    assert tasknotes["module"] == "tasknotes.read_context"
    assert tasknotes["status"] == "ok"
    assert tasknotes["available"] is True
    assert tasknotes["freshness"] == "1780000000"
    assert tasknotes["generated_at_epoch"] == 1780000000
    assert tasknotes["limits"]["file_limit"] == 12
    assert tasknotes["limits"]["bytes_per_file"] == 4096
    assert tasknotes["limits"]["total_bytes"] == 32768
    assert tasknotes["item_count"] == 12
    assert tasknotes["truncated"] is True
    assert tasknotes["omitted"]["over_limit"] == 2
    assert tasknotes["warnings"] == ["tasknotes.read_context is bounded/truncated"]
    assert tasknotes["source"]["kind"] == "TaskNotes/Tasks"
    assert "root" not in tasknotes["source"]
    assert "tasks_root" not in tasknotes["source"]
    assert "source_paths" not in tasknotes
    assert tasknotes["provenance"]["item_paths"] == ["Tasks/00.md", "Tasks/01.md"]
    assert tasknotes["may_mutate_tasknotes"] is False
    assert tasknotes["required_action_capabilities"] == []

    serialized_tasknotes = json.dumps(tasknotes, sort_keys=True)
    forbidden = [
        "content",
        "action_payload",
        "AI/inbox/actions",
        "tasknotes.promote",
        "promote_task_proposal",
        "apply_tasknotes",
        "execute",
        "run_command",
        "/tmp/example/TaskNotes",
        "source_paths",
        "tasks_root",
        "\"root\"",
    ]
    assert all(value not in serialized_tasknotes for value in forbidden)


def test_direct_execution_fields_rejected_with_tasknotes_context() -> None:
    package = build_llm_prompt_package(
        {"kind": "review_tasknotes_context"},
        {"context_hub": tasknotes_context_hub_fixture()},
    )

    assert "tasknotes_read_context" in package["context"]

    candidate = {
        "proposal_kind": "next_goal_step",
        "summary": "Run command",
        "message_markdown": "I will run this now.",
        "shell_command": "rm -rf /",
        "suggested_actions": [],
        "action_payload": {
            "execute": True,
        },
        "tasknotes": {
            "apply_tasknotes": True,
        },
    }

    result = validate_llm_obsidian_proposal(
        candidate,
        sample_intent(),
        sample_context(),
    )

    assert result["valid"] is False
    assert "direct execution fields" in result["error"]

def run_all() -> None:
    tests = [
        test_prompt_package_is_bounded_and_llm_specific,
        test_valid_llm_proposal_is_sanitized_to_obsidian_contract,
        test_direct_execution_fields_are_rejected,
        test_prompt_package_includes_tasknotes_read_context_metadata,
        test_direct_execution_fields_rejected_with_tasknotes_context,
        test_fallback_proposal_is_safe_and_task_draftable,
        test_json_parser_accepts_wrapped_json,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
