#!/usr/bin/env python3

from __future__ import annotations

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


def run_all() -> None:
    tests = [
        test_prompt_package_is_bounded_and_llm_specific,
        test_valid_llm_proposal_is_sanitized_to_obsidian_contract,
        test_direct_execution_fields_are_rejected,
        test_fallback_proposal_is_safe_and_task_draftable,
        test_json_parser_accepts_wrapped_json,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
