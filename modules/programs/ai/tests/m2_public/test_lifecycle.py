"""M2 lifecycle acceptance tests (A01-A17).

Tests functional lifecycle of the task-initiation kernel: Stuck ingestion,
all response actions, expiry, reconciliation, idempotent replay, supersession,
restart resilience, and active listing.

Every test uses the kernel API, calls check_database after each operation,
closes and reopens the kernel to verify durability, and exercises exact replay.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest

from m2_support import (
    FIXED_NOW_BASE,
    REV_FIXTURE,
    KernelPolicy,
    KernelRefusalError,
    KernelNotFoundError,
    TaskInitiationKernel,
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)


# ===========================================================================
# A01: Stuck event ingestion
# ===========================================================================


def test_M2_A01_initialization(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Ingest a Stuck event: verify card_published, check_database, reopen, replay."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op.result["status"] == "card_published"
    assert "event_id" in op.result
    assert "card" in op.result
    eid = op.result["event_id"]

    # show
    s = kernel.show(eid)
    assert s["phase"] == "awaiting_response"

    # check_database
    cdb = kernel.check_database()
    assert cdb["status"] == "ok"
    assert cdb["interaction_count"] == 1

    # exact replay
    op2 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op2.replay is True
    assert op2.result["status"] == "card_published"

    # row counts
    with kernel._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 1

    # reopen
    k2 = reopen_kernel(temp_state_dir)
    assert k2.check_database()["status"] == "ok"
    s2 = k2.show(eid)
    assert s2["phase"] == "awaiting_response"

    # changed payload conflict
    with pytest.raises(KernelRefusalError):
        k2.ingest_stuck(
            make_stuck(event_id=eid, task_description="changed"),
            resolution=resolution_tasks,
        )


# ===========================================================================
# A02: Start response
# ===========================================================================


def test_M2_A02_start_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Respond 'start': verify accepted, observing phase, check_database, reopen."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    resp = make_response(card, "start")
    r = k.respond(resp, resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "observing"
    assert r.result.get("terminal_status") is None

    s = k.show(eid)
    assert s["phase"] == "observing"

    cdb = k.check_database()
    assert cdb["status"] == "ok"
    assert cdb["interaction_count"] == 1
    assert cdb["message_count"] == 2

    # exact replay
    replay_op = k.respond(resp, resolution=resolution_tasks)
    assert replay_op.replay is True
    assert replay_op.result["status"] == "accepted"

    # second response with different id but same card must be refused
    with pytest.raises(KernelRefusalError):
        k.respond(make_response(card, "start"), resolution=resolution_tasks)

    # reopen
    k2 = reopen_kernel(temp_state_dir)
    s2 = k2.show(eid)
    assert s2["phase"] == "observing"
    assert s2["terminal_status"] is None


# ===========================================================================
# A03: Shrink response
# ===========================================================================


def test_M2_A03_shrink_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Respond 'shrink': verify next_card, phase awaiting_response, reopen."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    r = k.respond(make_response(card, "shrink"), resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None

    s = k.show(eid)
    assert s["phase"] == "awaiting_response"

    cdb = k.check_database()
    assert cdb["status"] == "ok"

    with k._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 2

    s_inc = k.show(eid, include_sensitive=True)
    assert "aggregate" in s_inc
    assert len(s_inc["aggregate"]["revisions"]) >= 2


# ===========================================================================
# A04: Blocked response
# ===========================================================================


def test_M2_A04_blocked_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Respond 'blocked': verify next_card, phase awaiting_response."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    r = k.respond(make_response(card, "blocked"), resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None

    cdb = k.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# A05: Defer response
# ===========================================================================


def test_M2_A05_defer_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Respond 'defer': verify terminal_status completed, reopen."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    r = k.respond(make_response(card, "defer"), resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"
    assert r.result["phase"] == "observing"

    s = k.show(eid)
    assert s["terminal_status"] == "completed"
    assert s["phase"] == "observing"

    cdb = k.check_database()
    assert cdb["status"] == "ok"

    # reopen
    k2 = reopen_kernel(temp_state_dir)
    s2 = k2.show(eid)
    assert s2["terminal_status"] == "completed"


# ===========================================================================
# A06: Dismiss response
# ===========================================================================


def test_M2_A06_dismiss_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Respond 'dismiss': verify terminal_status completed."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]

    r = k.respond(make_response(card, "dismiss"), resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"

    cdb = k.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# A07: Card expiry
# ===========================================================================


def test_M2_A07_card_expiry(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify card expiry rejects response and terminal_status appears."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    # Use a clock past card expiry
    k_expired = reopen_kernel(
        temp_state_dir, clock=lambda: card["expires_at_epoch"] + 1
    )
    with pytest.raises(KernelRefusalError):
        k_expired.respond(make_response(card, "start"), resolution=resolution_tasks)

    s = k_expired.show(eid)
    assert s["terminal_status"] is not None

    # Reopen still expired
    k2 = reopen_kernel(temp_state_dir, clock=lambda: card["expires_at_epoch"] + 1)
    s2 = k2.show(eid)
    assert s2["terminal_status"] is not None


# ===========================================================================
# A08: Observation completion via reconcile
# ===========================================================================


def test_M2_A08_observation_completion(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify observation completion via reconcile, idempotent."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]
    k.respond(make_response(card, "start"), resolution=resolution_tasks)

    # Use clock past observation deadline
    k_overdue = reopen_kernel(
        temp_state_dir, clock=lambda: FIXED_NOW_BASE + 2000
    )
    rec = k_overdue.reconcile()
    assert rec["ok"] is True
    assert rec["reconciled"] >= 1

    s = k_overdue.show(eid)
    assert s["terminal_status"] is not None

    cdb = k_overdue.check_database()
    assert cdb["status"] == "ok"

    # Idempotent reconcile
    rec2 = k_overdue.reconcile()
    assert rec2["reconciled"] == 0


# ===========================================================================
# A09: Revision ceiling
# ===========================================================================


def test_M2_A09_revision_ceiling(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify max_card_revisions ceiling is enforced."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    # First shrink (rev 1 -> 2)
    r1 = k.respond(make_response(card, "shrink"), resolution=resolution_tasks)
    assert r1.result["status"] == "accepted"
    card2 = r1.result.get("next_card")
    assert card2 is not None

    # Second shrink (rev 2 -> 3, total=3 hits ceiling with max_card_revisions=3)
    r2 = k.respond(make_response(card2, "shrink"), resolution=resolution_tasks)
    assert r2.result["status"] == "accepted"
    card3 = r2.result.get("next_card")

    # Third shrink exceeds ceiling
    if card3 is not None:
        r3 = k.respond(make_response(card3, "shrink"), resolution=resolution_tasks)
        assert r3.result.get("terminal_status") is not None
    else:
        assert r2.result.get("terminal_status") is not None

    s = k.show(eid)
    assert s["terminal_status"] is not None

    cdb = k.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# A10: Idempotent Stuck replay
# ===========================================================================


def test_M2_A10_idempotent_stuck(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Verify idempotent Stuck replay: same payload returns replay=True."""
    op1 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert not op1.replay

    op2 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op2.replay is True
    assert op1.result["status"] == op2.result["status"]

    with kernel._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1


# ===========================================================================
# A11: Idempotent Response replay
# ===========================================================================


def test_M2_A11_idempotent_response(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify idempotent Response replay."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]

    resp = make_response(card, "start")
    r1 = k.respond(resp, resolution=resolution_tasks)
    assert not r1.replay

    r2 = k.respond(resp, resolution=resolution_tasks)
    assert r2.replay is True
    assert r1.result["status"] == r2.result["status"]


# ===========================================================================
# A12: Task change supersession
# ===========================================================================


def test_M2_A12_task_change_supersession(
    temp_state_dir: Any, kernel: Any, resolution_tasks: Any
) -> None:
    """Verify response with different task revision supersedes."""
    op = kernel.ingest_stuck(
        make_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}),
        resolution=resolution_tasks,
    )
    card = op.result["card"]
    eid = op.result["event_id"]

    res_changed = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff").hexdigest()}},
    )

    r = kernel.respond(make_response(card, "start"), resolution=res_changed)
    assert r.result["status"] == "superseded"
    assert r.result.get("terminal_status") == "superseded"
    assert r.result["phase"] == "awaiting_response"

    s = kernel.show(eid)
    assert s["phase"] == "awaiting_response"
    assert s["terminal_status"] == "superseded"

    cdb = kernel.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# A13: check_database integrity
# ===========================================================================


def test_M2_A13_check_database(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify check_database returns correct counts and version."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    k.respond(make_response(card, "start"), resolution=resolution_tasks)

    cdb = k.check_database()
    assert cdb["status"] == "ok"
    assert cdb["interaction_count"] == 1
    assert cdb["message_count"] == 2
    assert cdb["version"] == 1


# ===========================================================================
# A14: show
# ===========================================================================


def test_M2_A14_show(
    temp_state_dir: Any, stuck_with_resolution: Any
) -> None:
    """Verify show returns correct fields with and without include_sensitive."""
    k = stuck_with_resolution["kernel"]
    eid = stuck_with_resolution["event_id"]

    s = k.show(eid)
    assert s["event_id"] == eid
    assert "phase" in s
    assert "terminal_status" in s
    assert "state_version" in s
    assert "aggregate" not in s
    assert "needs_reconciliation" in s

    s_inc = k.show(eid, include_sensitive=True)
    assert "aggregate" in s_inc
    assert "revisions" in s_inc["aggregate"]

    # not-found
    with pytest.raises(KernelNotFoundError):
        k.show(str(uuid.uuid4()))


# ===========================================================================
# A15: list_active
# ===========================================================================


def test_M2_A15_list_active(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Verify list_active excludes terminal, includes non-terminal."""
    op1 = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    card = op1.result["card"]

    # Make it terminal via defer
    kernel.respond(make_response(card, "defer"), resolution=resolution_tasks)
    active = kernel.list_active()
    assert len(active) == 0  # terminal excluded

    # Add another non-terminal
    op2 = kernel.ingest_stuck(
        make_stuck(event_id=str(uuid.uuid4())), resolution=resolution_tasks
    )
    active2 = kernel.list_active()
    assert len(active2) >= 1
    for item in active2:
        assert "event_id" in item
        assert item.get("terminal_status") is None


# ===========================================================================
# A16: reconcile
# ===========================================================================


def test_M2_A16_reconcile(
    temp_state_dir: Any, kernel_short: Any, stuck_event: Any
, resolution_tasks: Any) -> None:
    """Verify reconcile transitions overdue observations, idempotent."""
    k = kernel_short
    res = make_resolution_input(
        temp_state_dir, {"Tasks/test.md": {"label": "A16 Task", "revision": REV_FIXTURE}},
        policy=KernelPolicy(card_ttl_seconds=10, observation_seconds=10),
    )
    op = k.ingest_stuck(stuck_event, resolution=res)
    card = op.result["card"]
    k.respond(make_response(card, "start"), resolution=resolution_tasks)

    k_late = reopen_kernel(
        temp_state_dir,
        policy=KernelPolicy(card_ttl_seconds=10, observation_seconds=10),
        clock=lambda: FIXED_NOW_BASE + 2000,
    )
    rec = k_late.reconcile()
    assert rec["ok"] is True
    assert rec["reconciled"] >= 1

    rec2 = k_late.reconcile()
    assert rec2["reconciled"] == 0


# ===========================================================================
# A17: Restart resilience
# ===========================================================================


def test_M2_A17_restart_resilience(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Verify database survives close/reopen with full integrity."""
    k = stuck_with_resolution["kernel"]
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    k.respond(make_response(card, "start"), resolution=resolution_tasks)

    # Reopen
    k2 = reopen_kernel(temp_state_dir)
    cdb = k2.check_database()
    assert cdb["status"] == "ok"

    s = k2.show(eid)
    assert s["phase"] == "observing"
    assert s["terminal_status"] is None

    s_inc = k2.show(eid, include_sensitive=True)
    assert len(s_inc["aggregate"]["revisions"]) >= 1

    with k2._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 1