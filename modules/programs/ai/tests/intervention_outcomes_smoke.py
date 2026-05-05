#!/usr/bin/env python3

from ai_system.intervention_outcomes import (
    build_outcome_stats,
    summarize_intervention,
    summarize_interventions,
)


def event(name: str, intervention_id: str, epoch: int, **extra):
    out = {
        "schema_version": "event.v1",
        "event": name,
        "event_type": name,
        "intervention_id": intervention_id,
        "intervention_kind": "recovery_nudge",
        "target_id": "anki",
        "target_name": "Anki",
        "nudge_id": f"n-{intervention_id}",
        "timestamp_epoch": epoch,
        "timestamp": f"2026-05-05T10:{epoch % 60:02d}:00+02:00",
        "processed_at": f"2026-05-05T10:{epoch % 60:02d}:00+02:00",
        "source": "smoke",
        "device": "local",
    }
    out.update(extra)
    return out


def base_intervention(intervention_id: str, *, gate_ok=True, wrote=True):
    events = [
        event("intervention_proposed", intervention_id, 100),
        event(
            "intervention_gated",
            intervention_id,
            101,
            gate_ok=gate_ok,
            gate_reason="validated" if gate_ok else "write_nudge_blocked",
            wrote_nudge=wrote,
        ),
    ]
    if wrote:
        events.append(event("intervention_nudge_written", intervention_id, 102, wrote_nudge=True))
    return events


def test_not_shown_when_gate_blocks() -> None:
    summary = summarize_intervention(
        "i-blocked",
        intervention_events=base_intervention("i-blocked", gate_ok=False, wrote=False),
    )

    assert summary["outcome"] == "not_shown"
    assert summary["gate_ok"] is False
    assert summary["nudge_written"] is False


def test_shown_no_response_when_nudge_written_only() -> None:
    summary = summarize_intervention(
        "i-shown",
        intervention_events=base_intervention("i-shown"),
    )

    assert summary["outcome"] == "shown_no_response"
    assert summary["nudge_written"] is True
    assert summary["user_acted"] is False


def test_acknowledged_and_snoozed() -> None:
    ack = summarize_intervention(
        "i-ack",
        intervention_events=base_intervention("i-ack"),
        action_events=[event("ack_nudge", "i-ack", 110, device="phone")],
    )
    assert ack["outcome"] == "acknowledged"
    assert ack["user_acted"] is True

    snooze = summarize_intervention(
        "i-snooze",
        intervention_events=base_intervention("i-snooze"),
        action_events=[event("snooze_nudge", "i-snooze", 110, device="phone", snooze_minutes=15)],
    )
    assert snooze["outcome"] == "snoozed"
    assert snooze["user_acted"] is True


def test_started_and_terminal_recovery_outcomes() -> None:
    started = summarize_intervention(
        "i-start",
        intervention_events=base_intervention("i-start"),
        action_events=[event("recovery_started", "i-start", 110, device="phone")],
    )
    assert started["outcome"] == "started"
    assert started["recovery_started"] is True

    success = summarize_intervention(
        "i-success",
        intervention_events=base_intervention("i-success"),
        action_events=[event("recovery_started", "i-success", 110, device="phone")],
        recovery_events=[event("recovery_possible_success", "i-success", 500, status="possible_success")],
    )
    assert success["outcome"] == "possible_success"
    assert success["terminal_recovery"] is True

    abort = summarize_intervention(
        "i-abort",
        intervention_events=base_intervention("i-abort"),
        action_events=[event("recovery_started", "i-abort", 110, device="phone")],
        recovery_events=[event("recovery_possible_abort", "i-abort", 500, status="possible_abort")],
    )
    assert abort["outcome"] == "possible_abort"

    expired = summarize_intervention(
        "i-expired",
        intervention_events=base_intervention("i-expired"),
        action_events=[event("recovery_started", "i-expired", 110, device="phone")],
        recovery_events=[event("recovery_expired", "i-expired", 500, status="expired")],
    )
    assert expired["outcome"] == "expired"


def test_summarize_many_and_stats() -> None:
    intervention_events = []
    action_events = []
    recovery_events = []

    intervention_events.extend(base_intervention("i-blocked", gate_ok=False, wrote=False))
    intervention_events.extend(base_intervention("i-snooze"))
    action_events.append(event("snooze_nudge", "i-snooze", 110, device="phone"))

    intervention_events.extend(base_intervention("i-success"))
    action_events.append(event("recovery_started", "i-success", 120, device="phone"))
    recovery_events.append(event("recovery_possible_success", "i-success", 500, status="possible_success"))

    summaries = summarize_interventions(intervention_events, action_events, recovery_events)
    outcomes = {item["intervention_id"]: item["outcome"] for item in summaries}

    assert outcomes["i-blocked"] == "not_shown"
    assert outcomes["i-snooze"] == "snoozed"
    assert outcomes["i-success"] == "possible_success"

    stats = build_outcome_stats(summaries)
    assert stats["total"] == 3
    assert stats["by_outcome"]["not_shown"] == 1
    assert stats["by_outcome"]["snoozed"] == 1
    assert stats["by_outcome"]["possible_success"] == 1
    assert stats["shown_count"] == 2
    assert stats["acted_count"] == 2
    assert stats["started_count"] == 1
    assert stats["terminal_count"] == 1
    assert stats["success_count"] == 1


def main() -> None:
    tests = [
        test_not_shown_when_gate_blocks,
        test_shown_no_response_when_nudge_written_only,
        test_acknowledged_and_snoozed,
        test_started_and_terminal_recovery_outcomes,
        test_summarize_many_and_stats,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
