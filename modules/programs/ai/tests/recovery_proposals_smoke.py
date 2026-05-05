#!/usr/bin/env python3

from ai_system.recovery_proposals import build_deterministic_recovery_proposal, build_recovery_reasoning


CLEAR_FACTS = {
    "has_active_session": False,
    "has_active_nudge": False,
    "has_active_question": False,
    "has_active_recovery": False,
    "recent_terminal_recovery": False,
    "recent_snooze": False,
    "anki_due": 8,
    "desktop_verdict": "idle",
}


def test_clear_facts_build_write_nudge_proposal() -> None:
    proposal = build_deterministic_recovery_proposal(CLEAR_FACTS)

    assert proposal["schema_version"] == "agent_recovery_proposal.v1"
    assert proposal["decision"] == "write_nudge"
    assert proposal["target_id"] == "anki"
    assert proposal["source"] == "deterministic-v0"
    assert proposal["allowed_actions"] == ["start_recovery_target", "snooze_nudge"]
    assert proposal["blocked_reasons"] == []
    assert "anki_due" in proposal["reason_codes"]


def test_blockers_are_explainable() -> None:
    facts = dict(CLEAR_FACTS)
    facts["has_active_session"] = True
    facts["recent_snooze"] = True

    reasoning = build_recovery_reasoning(facts)

    assert "active_session" in reasoning["blocked_reasons"]
    assert "recent_snooze" in reasoning["blocked_reasons"]
    assert "no_active_nudge" in reasoning["reason_codes"]


def test_anki_not_due_blocks() -> None:
    facts = dict(CLEAR_FACTS)
    facts["anki_due"] = 0

    proposal = build_deterministic_recovery_proposal(facts)

    assert "anki_not_due" in proposal["blocked_reasons"]
    assert "anki_due" not in proposal["reason_codes"]


def test_bad_desktop_verdict_blocks() -> None:
    facts = dict(CLEAR_FACTS)
    facts["desktop_verdict"] = "deep_focus"

    proposal = build_deterministic_recovery_proposal(facts)

    assert "desktop_verdict_deep_focus" in proposal["blocked_reasons"]


def test_non_dict_facts_are_safe() -> None:
    proposal = build_deterministic_recovery_proposal(None)

    assert proposal["target_id"] == "anki"
    assert "anki_not_due" in proposal["blocked_reasons"]


def main() -> None:
    tests = [
        test_clear_facts_build_write_nudge_proposal,
        test_blockers_are_explainable,
        test_anki_not_due_blocks,
        test_bad_desktop_verdict_blocks,
        test_non_dict_facts_are_safe,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
