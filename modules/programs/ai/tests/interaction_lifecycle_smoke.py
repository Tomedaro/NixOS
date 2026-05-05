#!/usr/bin/env python3

from __future__ import annotations

from ai_system.interaction_lifecycle import (
    action_clears_active_nudge,
    clear_reason_for_active_nudge,
    nudge_age_seconds,
    prune_interaction_state,
    recovery_is_terminal,
)


def assert_equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def test_help_now_nudge_younger_than_ttl_stays_active():
    state = {
        "active_nudge": {
            "kind": "nudge",
            "status": "active",
            "planner_mode": "help-now",
            "created_at": "2026-05-05T20:00:00+02:00",
        }
    }

    reason = clear_reason_for_active_nudge(
        state,
        now="2026-05-05T20:30:00+02:00",
        ttl_seconds=3600,
    )

    assert_equal(reason, None)


def test_help_now_nudge_older_than_ttl_expires():
    state = {
        "active_nudge": {
            "kind": "nudge",
            "status": "active",
            "planner_mode": "help-now",
            "created_at": "2026-05-05T20:00:00+02:00",
        }
    }

    next_state, reason = prune_interaction_state(
        state,
        now="2026-05-05T21:01:00+02:00",
        ttl_seconds=3600,
    )

    assert_equal(reason, "expired_help-now_nudge")
    assert_equal(next_state["active_nudge"], None)
    assert_equal(state["active_nudge"]["status"], "active")


def test_updated_at_does_not_extend_created_at_ttl():
    nudge = {
        "kind": "nudge",
        "status": "active",
        "planner_mode": "help-now",
        "created_at": "2026-05-05T20:00:00+02:00",
        "updated_at": "2026-05-05T20:59:00+02:00",
    }

    assert_equal(
        nudge_age_seconds(nudge, "2026-05-05T21:01:00+02:00"),
        3660,
    )


def test_ack_and_snooze_clear_active_nudges():
    assert_equal(action_clears_active_nudge({"action": "ack_nudge"}), True)
    assert_equal(action_clears_active_nudge({"action": "snooze_nudge"}), True)
    assert_equal(action_clears_active_nudge({"action": "answer_question"}), False)

    state = {
        "active_nudge": {
            "kind": "nudge",
            "status": "active",
            "planner_mode": "help-now",
            "created_at": "2026-05-05T20:00:00+02:00",
        }
    }

    next_state, reason = prune_interaction_state(
        state,
        action_event={"action": "ack_nudge"},
        now="2026-05-05T20:05:00+02:00",
    )

    assert_equal(reason, "user_action_ack_nudge")
    assert_equal(next_state["active_nudge"], None)


def test_terminal_recovery_clears_matching_recovery_nudge():
    state = {
        "active_nudge": {
            "kind": "nudge",
            "status": "active",
            "planner_mode": "recovery",
            "nudge_id": "n-recovery-trigger-anki-1",
            "target_id": "anki",
            "created_at": "2026-05-05T20:00:00+02:00",
        }
    }
    recovery = {
        "status": "possible_success",
        "intervention": {
            "nudge_id": "n-recovery-trigger-anki-1",
        },
        "target": {
            "target_id": "anki",
        },
    }

    assert_equal(recovery_is_terminal(recovery), True)

    next_state, reason = prune_interaction_state(
        state,
        recovery_state=recovery,
        now="2026-05-05T20:10:00+02:00",
    )

    assert_equal(reason, "recovery_possible_success")
    assert_equal(next_state["active_nudge"], None)


def test_non_terminal_recovery_does_not_clear():
    state = {
        "active_nudge": {
            "kind": "nudge",
            "status": "active",
            "planner_mode": "recovery",
            "nudge_id": "n-recovery-trigger-anki-1",
            "created_at": "2026-05-05T20:00:00+02:00",
        }
    }
    recovery = {
        "status": "observing",
        "intervention": {
            "nudge_id": "n-recovery-trigger-anki-1",
        },
    }

    next_state, reason = prune_interaction_state(
        state,
        recovery_state=recovery,
        now="2026-05-05T20:10:00+02:00",
    )

    assert_equal(reason, None)
    assert_equal(next_state["active_nudge"]["status"], "active")


def run_all():
    tests = [
        test_help_now_nudge_younger_than_ttl_stays_active,
        test_help_now_nudge_older_than_ttl_expires,
        test_updated_at_does_not_extend_created_at_ttl,
        test_ack_and_snooze_clear_active_nudges,
        test_terminal_recovery_clears_matching_recovery_nudge,
        test_non_terminal_recovery_does_not_clear,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
