#!/usr/bin/env python3

from ai_system.proposal_gate import validate_recovery_proposal


CLEAR_FACTS = {
    "has_active_session": False,
    "has_active_nudge": False,
    "has_active_question": False,
    "has_active_recovery": False,
    "recent_snooze": False,
    "recent_terminal_recovery": False,
    "anki_due": 10,
}


def assert_rejected(result, reason):
    assert result["ok"] is False, result
    assert result["status"] == "rejected", result
    assert result["reason"] == reason, result


def test_valid_write_nudge():
    proposal = {
        "schema_version": "agent_recovery_proposal.v1",
        "decision": "write_nudge",
        "target_id": "anki",
        "target_name": "Anki",
        "confidence": 0.72,
        "reason_codes": ["anki_due", "idle"],
        "blocked_reasons": [],
        "message": "Try a tiny Anki block.",
        "recommended_next_action": "Open Anki and stay for 5 minutes.",
        "allowed_actions": ["start_recovery_target", "snooze_nudge"],
    }

    result = validate_recovery_proposal(proposal, CLEAR_FACTS)

    assert result["ok"] is True, result
    normalized = result["normalized"]
    assert normalized["decision"] == "write_nudge"
    assert normalized["target_id"] == "anki"
    assert normalized["phone_nudge"]["status"] == "active"
    assert normalized["phone_nudge"]["actions"][0]["action"] == "start_recovery_target"
    assert normalized["phone_nudge"]["actions"][1]["action"] == "snooze_nudge"


def test_due_zero_blocks_write():
    facts = dict(CLEAR_FACTS)
    facts["anki_due"] = 0

    result = validate_recovery_proposal({
        "decision": "write_nudge",
        "target_id": "anki",
        "confidence": 0.5,
    }, facts)

    assert_rejected(result, "write_nudge_blocked")
    assert "anki_not_due" in result["details"]["blocked_reasons"]


def test_active_recovery_blocks_write():
    facts = dict(CLEAR_FACTS)
    facts["has_active_recovery"] = True

    result = validate_recovery_proposal({
        "decision": "write_nudge",
        "target_id": "anki",
        "confidence": 0.5,
    }, facts)

    assert_rejected(result, "write_nudge_blocked")
    assert "active_recovery" in result["details"]["blocked_reasons"]


def test_unknown_target_rejected():
    result = validate_recovery_proposal({
        "decision": "write_nudge",
        "target_id": "unknown-target",
    }, CLEAR_FACTS)

    assert_rejected(result, "unknown_recovery_target")


def test_unsafe_direct_execution_rejected():
    result = validate_recovery_proposal({
        "decision": "write_nudge",
        "target_id": "anki",
        "android_package": "com.bad.actor",
    }, CLEAR_FACTS)

    assert_rejected(result, "proposal_contains_direct_execution_fields")


def test_unsupported_action_rejected():
    result = validate_recovery_proposal({
        "decision": "write_nudge",
        "target_id": "anki",
        "allowed_actions": ["start_recovery_target", "submit_proof"],
    }, CLEAR_FACTS)

    assert_rejected(result, "proposal_contains_unsupported_actions")


def test_skip_is_accepted_even_with_blocked_reasons():
    result = validate_recovery_proposal({
        "decision": "skip",
        "target_id": "anki",
        "blocked_reasons": ["anki_not_due"],
        "confidence": 0.1,
    }, {"anki_due": 0})

    assert result["ok"] is True, result
    assert result["normalized"]["decision"] == "skip"
    assert "anki_not_due" in result["normalized"]["blocked_reasons"]


def main():
    tests = [
        test_valid_write_nudge,
        test_due_zero_blocks_write,
        test_active_recovery_blocks_write,
        test_unknown_target_rejected,
        test_unsafe_direct_execution_rejected,
        test_unsupported_action_rejected,
        test_skip_is_accepted_even_with_blocked_reasons,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
