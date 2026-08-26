"""M2 verifier valid lifecycle tests.

Tests for valid lifecycle paths that should pass in baseline: all operations
(ingest_stuck, respond with all actions, show, check_database, reconcile,
replay, restart) exercised through the public kernel API only.

The only durable phases are awaiting_response and observing.
"""

from __future__ import annotations

import hashlib
import pytest
import uuid
from typing import Any

from m2_verifier_support import (
    make_response,
    make_resolution_input,
    make_stuck,
    reopen_kernel,
    KernelNotFoundError,
    KernelRefusalError,
)
from ai_system.task_initiation_kernel import KernelPolicy


# ===========================================================================
# M2-C01: Stuck ingestion
# ===========================================================================


def test_M2_C01_ingest_stuck_card_published(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """Ingest a Stuck event: card_published, phase=awaiting_response, check_database, reopen, replay."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert not op.replay, "first ingest should not be replay"
    assert op.result["status"] == "card_published"
    assert "event_id" in op.result
    assert "card" in op.result
    eid = op.result["event_id"]

    s = kernel.show(eid)
    assert s["phase"] == "awaiting_response"
    assert "terminal_status" in s

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"
    assert cdb["interaction_count"] == 1

    op2 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op2.replay
    assert op2.result["status"] == "card_published"

    k2 = reopen_kernel(temp_state_dir)
    assert k2.check_database()["status"] == "ok"
    s2 = k2.show(eid)
    assert s2["phase"] == "awaiting_response"


# ===========================================================================
# M2-C02: Start response
# ===========================================================================


def test_M2_C02_start_response_observing(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Respond 'start': accepted, phase=observing, check_database, reopen."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    r = kernel.respond(make_response(card, "start"), resolution=resolution_tasks)
    assert not r.replay
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "observing"
    assert r.result.get("terminal_status") is None

    s = kernel.show(eid)
    assert s["phase"] == "observing"

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"

    k2 = reopen_kernel(temp_state_dir)
    s2 = k2.show(eid)
    assert s2["phase"] == "observing"
    assert s2["terminal_status"] is None


# ===========================================================================
# M2-C03: Shrink response
# ===========================================================================


def test_M2_C03_shrink_response_next_card(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Respond 'shrink': next_card, phase=awaiting_response, reopen."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    r = kernel.respond(make_response(card, "shrink"), resolution=resolution_tasks)
    assert not r.replay
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None

    s = kernel.show(eid)
    assert s["phase"] == "awaiting_response"

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"

    s_inc = kernel.show(eid, include_sensitive=True)
    assert "aggregate" in s_inc
    assert len(s_inc["aggregate"]["revisions"]) >= 2


# ===========================================================================
# M2-C04: Blocked response
# ===========================================================================


def test_M2_C04_blocked_response_next_card(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Respond 'blocked': next_card, phase=awaiting_response."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    r = kernel.respond(make_response(card, "blocked"), resolution=resolution_tasks)
    assert not r.replay
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# M2-C05: Defer response
# ===========================================================================


def test_M2_C05_defer_response_completed(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Respond 'defer': terminal_status=completed, phase=observing, reopen."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    r = kernel.respond(make_response(card, "defer"), resolution=resolution_tasks)
    assert not r.replay
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"

    s = kernel.show(eid)
    assert s["terminal_status"] == "completed"
    assert s["phase"] == "observing"

    k2 = reopen_kernel(temp_state_dir)
    s2 = k2.show(eid)
    assert s2["terminal_status"] == "completed"


# ===========================================================================
# M2-C06: Dismiss response
# ===========================================================================


def test_M2_C06_dismiss_response_completed(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Respond 'dismiss': terminal_status=completed."""
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    r = kernel.respond(make_response(card, "dismiss"), resolution=resolution_tasks)
    assert not r.replay
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# M2-C07: Revision limit enforcement
# ===========================================================================


def test_M2_C07_revision_limit_terminal(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """max_card_revisions ceiling enforced: terminal after reaching limit."""
    eid = stuck_with_resolution["event_id"]
    kernel = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]

    r1 = kernel.respond(make_response(card, "shrink"), resolution=resolution_tasks)
    assert r1.result["status"] == "accepted"
    card2 = r1.result.get("next_card")
    assert card2 is not None

    r2 = kernel.respond(make_response(card2, "shrink"), resolution=resolution_tasks)
    assert r2.result["status"] == "accepted"
    card3 = r2.result.get("next_card")

    if card3 is not None:
        r3 = kernel.respond(make_response(card3, "shrink"), resolution=resolution_tasks)
        assert r3.result.get("terminal_status") is not None
    else:
        assert r2.result.get("terminal_status") is not None

    s = kernel.show(eid)
    assert s["terminal_status"] is not None
    assert kernel.check_database()["status"] == "ok"


# ===========================================================================
# M2-C08: Card expiry
# ===========================================================================


def test_M2_C08_card_expiry_refused(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Card past expires_at rejects respond, terminal_status set on show."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    expired_clock = lambda: card["expires_at_epoch"] + 1  # noqa: E731
    k2 = reopen_kernel(temp_state_dir, clock=expired_clock)

    with pytest.raises(KernelRefusalError):
        k2.respond(make_response(card, "start"), resolution=resolution_tasks)

    s = k2.show(eid)
    assert s["terminal_status"] is not None

    k3 = reopen_kernel(temp_state_dir, clock=expired_clock)
    s3 = k3.show(eid)
    assert s3["terminal_status"] is not None


# ===========================================================================
# M2-C09: Observation completion via reconcile
# ===========================================================================


def test_M2_C09_observation_completion_reconcile(
    temp_state_dir, kernel_short, stuck_event, resolution_tasks
) -> None:
    """reconcile transitions overdue observing to terminal, idempotent."""
    op = kernel_short.ingest_stuck(stuck_event, resolution=resolution_tasks)
    card = op.result["card"]
    kernel_short.respond(make_response(card, "start"), resolution=resolution_tasks)
    eid = op.result["event_id"]

    late_clock = lambda: 1_700_000_000 + 2000  # noqa: E731
    k2 = reopen_kernel(
        temp_state_dir,
        clock=late_clock,
        policy=KernelPolicy(card_ttl_seconds=10, observation_seconds=10),
    )

    rec = k2.reconcile()
    assert rec["ok"] is True
    assert rec["reconciled"] >= 1

    s = k2.show(eid)
    assert s["terminal_status"] is not None

    rec2 = k2.reconcile()
    assert rec2["reconciled"] == 0


# ===========================================================================
# M2-C10: Supersession
# ===========================================================================


def test_M2_C10_supersession_task_changed(
    temp_state_dir, kernel, stuck_event
) -> None:
    """Response with changed task revision supersedes interaction."""
    rev1 = hashlib.sha256(b"rev1").hexdigest()
    rev2 = hashlib.sha256(b"rev2").hexdigest()

    res1 = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "Original", "revision": rev1}},
    )
    op = kernel.ingest_stuck(stuck_event, resolution=res1)
    card = op.result["card"]
    eid = op.result["event_id"]

    res2 = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "Changed", "revision": rev2}},
    )
    r = kernel.respond(make_response(card, "start"), resolution=res2)
    assert r.result["status"] == "superseded"
    assert r.result.get("terminal_status") == "superseded"

    s = kernel.show(eid)
    assert s["terminal_status"] == "superseded"
    assert kernel.check_database()["status"] == "ok"


# ===========================================================================
# M2-C11: Idempotent replay
# ===========================================================================


def test_M2_C11_idempotent_stuck_replay(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """Identical Stuck replay returns replay=True with same result."""
    op1 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert not op1.replay

    op2 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op2.replay
    assert op1.result["status"] == op2.result["status"]


def test_M2_C11_idempotent_response_replay(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Identical Response replay returns replay=True."""
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    resp = make_response(card, "start")
    r1 = kernel.respond(resp, resolution=resolution_tasks)
    assert not r1.replay

    r2 = kernel.respond(resp, resolution=resolution_tasks)
    assert r2.replay
    assert r1.result["status"] == r2.result["status"]


# ===========================================================================
# M2-C12: Restart resilience
# ===========================================================================


def test_M2_C12_restart_resilience(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Close/reopen preserves all state: check_database, phase, aggregate intact."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    kernel.respond(make_response(card, "start"), resolution=resolution_tasks)

    k2 = reopen_kernel(temp_state_dir)
    assert k2.check_database()["status"] == "ok"

    s2 = k2.show(eid)
    assert s2["phase"] == "observing"
    assert s2["terminal_status"] is None

    s2_inc = k2.show(eid, include_sensitive=True)
    assert len(s2_inc["aggregate"]["revisions"]) >= 1


# ===========================================================================
# show() tests
# ===========================================================================


def test_show_includes_correct_fields(stuck_with_resolution) -> None:
    """show returns required fields; aggregate only with include_sensitive."""
    eid = stuck_with_resolution["event_id"]
    kernel = stuck_with_resolution["kernel"]

    s = kernel.show(eid)
    assert s["event_id"] == eid
    assert "phase" in s
    assert "terminal_status" in s
    assert "state_version" in s
    assert "needs_reconciliation" in s
    assert "aggregate" not in s

    s_inc = kernel.show(eid, include_sensitive=True)
    assert "aggregate" in s_inc
    assert "revisions" in s_inc["aggregate"]


def test_show_unknown_event_id_raises(kernel) -> None:
    """show on unknown event_id raises KernelNotFoundError."""
    with pytest.raises(KernelNotFoundError):
        kernel.show(str(uuid.uuid4()))


# ===========================================================================
# list_active() tests
# ===========================================================================


def test_list_active_excludes_terminal(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """list_active excludes terminal interactions."""
    op1 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    card = op1.result["card"]
    kernel.respond(make_response(card, "defer"), resolution=resolution_tasks)

    active = kernel.list_active()
    assert len(active) == 0

    op2 = kernel.ingest_stuck(make_stuck(), resolution=resolution_tasks)
    active2 = kernel.list_active()
    assert len(active2) >= 1
    for item in active2:
        assert "event_id" in item
        assert "phase" in item


# ===========================================================================
# reconcile() tests
# ===========================================================================


def test_reconcile_idempotent(
    temp_state_dir, kernel_short, stuck_event, resolution_tasks
) -> None:
    """reconcile is idempotent."""
    op = kernel_short.ingest_stuck(stuck_event, resolution=resolution_tasks)
    card = op.result["card"]
    kernel_short.respond(make_response(card, "start"), resolution=resolution_tasks)

    late_clock = lambda: 1_700_000_000 + 2000  # noqa: E731
    k2 = reopen_kernel(
        temp_state_dir,
        clock=late_clock,
        policy=KernelPolicy(card_ttl_seconds=10, observation_seconds=10),
    )

    rec1 = k2.reconcile()
    assert rec1["ok"] is True
    assert rec1["reconciled"] >= 1

    rec2 = k2.reconcile()
    assert rec2["ok"] is True
    assert rec2["reconciled"] == 0
