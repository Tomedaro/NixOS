"""M2 policy determinism acceptance tests (P01-P09).

Tests that kernel policy (stuck_ttl, card_ttl, observation_seconds, max_card_revisions,
max_resolution_tasks, owner check, first-response-wins) is deterministically enforced
and that persisted policy governs even after restart with a different policy.
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
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)


# ===========================================================================
# P01: Stuck TTL enforcement
# ===========================================================================


def test_M2_P01_stuck_ttl_enforcement(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Stuck events older than stuck_ttl_seconds are refused."""
    # Default stuck_ttl is 7200 — our clock is at FIXED_NOW_BASE,
    # stuck occurred at FIXED_NOW_BASE-10, well within TTL.
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert op.result["status"] == "card_published"

    # Create kernel with short stuck_ttl
    pol_short = KernelPolicy(stuck_ttl_seconds=1)
    k2 = reopen_kernel(temp_state_dir, policy=pol_short, clock=lambda: FIXED_NOW_BASE + 100)
    # Now a new stuck event timed at FIXED_NOW_BASE-10 would be too old
    with pytest.raises(KernelRefusalError):
        k2.ingest_stuck(
            make_stuck(event_id=str(uuid.uuid4()), occurred_at_epoch=FIXED_NOW_BASE - 10),
            resolution=resolution_tasks,
        )


# ===========================================================================
# P02: Card TTL enforcement
# ===========================================================================


def test_M2_P02_card_ttl_enforcement(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Card expiry governed by card_ttl_seconds; persisted policy binds."""
    pol_short = KernelPolicy(card_ttl_seconds=5, observation_seconds=60)
    k = reopen_kernel(temp_state_dir, policy=pol_short)
    k.initialize()

    res = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "P02", "revision": REV_FIXTURE}},
        policy=pol_short,
    )
    op = k.ingest_stuck(stuck_event, resolution=res)
    card = op.result["card"]

    # Card should expire at FIXED_NOW_BASE + 5 (approx) based on card_ttl
    # Use clock past expiration
    k_exp = reopen_kernel(temp_state_dir, policy=pol_short, clock=lambda: FIXED_NOW_BASE + 100)
    with pytest.raises(KernelRefusalError):
        k_exp.respond(make_response(card, "start"), resolution=resolution_tasks)

    s = k_exp.show(op.result["event_id"])
    assert s["terminal_status"] is not None


# ===========================================================================
# P03: Observation seconds enforcement
# ===========================================================================


def test_M2_P03_observation_seconds(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Observation deadline governed by observation_seconds in policy."""
    pol = KernelPolicy(card_ttl_seconds=900, observation_seconds=5)
    k = reopen_kernel(temp_state_dir, policy=pol)
    k.initialize()
    res = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "P03", "revision": REV_FIXTURE}},
        policy=pol,
    )
    op = k.ingest_stuck(stuck_event, resolution=res)
    card = op.result["card"]
    eid = op.result["event_id"]
    r = k.respond(make_response(card, "start"), resolution=resolution_tasks)
    assert r.result["phase"] == "observing"
    # observation_due_at_epoch should be ~FIXED_NOW_BASE + 5
    assert "observation_due_at_epoch" in r.result

    # Advance past observation
    k2 = reopen_kernel(temp_state_dir, policy=pol, clock=lambda: FIXED_NOW_BASE + 100)
    rec = k2.reconcile()
    assert rec["reconciled"] >= 1
    s = k2.show(eid)
    assert s["terminal_status"] is not None


# ===========================================================================
# P04: max_card_revisions enforcement
# ===========================================================================


def test_M2_P04_max_card_revisions(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Non-default max_card_revisions limits shrink/blocked chains."""
    pol = KernelPolicy(max_card_revisions=1)
    k = reopen_kernel(temp_state_dir, policy=pol)
    k.initialize()
    res = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "P04", "revision": REV_FIXTURE}},
        policy=pol,
    )
    op = k.ingest_stuck(stuck_event, resolution=res)
    card = op.result["card"]
    eid = op.result["event_id"]

    # With max_card_revisions=1, even one shrink should terminalize
    r = k.respond(make_response(card, "shrink"), resolution=resolution_tasks)
    assert r.result["terminal_status"] == "completed"

    s = k.show(eid)
    assert s["terminal_status"] is not None


# ===========================================================================
# P05: max_resolution_tasks enforcement
# ===========================================================================


def test_M2_P05_max_resolution_tasks(
    temp_state_dir: Any, kernel: Any, stuck_event: Any
) -> None:
    """Resolution with too many tasks is refused per policy."""
    pol = KernelPolicy(max_resolution_tasks=1)

    # 2 tasks with max_resolution_tasks=1 → rejected
    with pytest.raises(KernelRefusalError):
        make_resolution_input(
            temp_state_dir,
            {
                "Tasks/a.md": {"label": "A", "revision": REV_FIXTURE},
                "Tasks/b.md": {"label": "B", "revision": REV_FIXTURE},
            },
            policy=pol,
        )


# ===========================================================================
# P06: Owner scoping (second response refused)
# ===========================================================================


def test_M2_P06_owner_scoping(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """First-response-wins: second responder is refused."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]

    r1 = k.respond(make_response(card, "start"), resolution=resolution_tasks)
    assert r1.result["status"] == "accepted"

    # Second response with different ID must be refused
    with pytest.raises(KernelRefusalError):
        k.respond(make_response(card, "dismiss"), resolution=resolution_tasks)


# ===========================================================================
# P07: Persisted policy survives restart with different policy
# ===========================================================================


def test_M2_P07_policy_survives_restart(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Policy snapshot persisted at Stuck time governs even after restart with different policy."""
    pol_write = KernelPolicy(card_ttl_seconds=900, observation_seconds=900, max_card_revisions=5)
    k_write = reopen_kernel(temp_state_dir, policy=pol_write)
    k_write.initialize()
    res = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "P07", "revision": REV_FIXTURE}},
        policy=pol_write,
    )
    op = k_write.ingest_stuck(stuck_event, resolution=res)
    card = op.result["card"]
    eid = op.result["event_id"]
    k_write.respond(make_response(card, "start"), resolution=resolution_tasks)

    # Reopen with restrictive policy — interaction should still obey original policy
    pol_restrict = KernelPolicy(max_card_revisions=1)
    k_read = reopen_kernel(temp_state_dir, policy=pol_restrict)
    s = k_read.show(eid)
    assert s["phase"] == "observing"
    assert s["terminal_status"] is None

    cdb = k_read.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# P08: Non-default policy task limits work
# ===========================================================================


def test_M2_P08_custom_task_limits(
    temp_state_dir: Any, kernel: Any, stuck_event: Any
) -> None:
    """Resolution with fewer tasks than max is accepted."""
    pol = KernelPolicy(max_resolution_tasks=10)
    res = make_resolution_input(
        temp_state_dir,
        {
            "Tasks/a.md": {"label": "A", "revision": REV_FIXTURE},
            "Tasks/b.md": {"label": "B", "revision": REV_FIXTURE},
            "Tasks/c.md": {"label": "C", "revision": REV_FIXTURE},
        },
        policy=pol,
    )
    assert len(res.tasks) == 3
    op = kernel.ingest_stuck(make_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/a.md"}), resolution=res)
    assert op.result["status"] == "card_published"


# ===========================================================================
# P09: Conflict detection survives policy restart
# ===========================================================================


def test_M2_P09_conflict_detection_restart(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Conflicting Stuck replay is refused even after restart with different policy."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    eid = op.result["event_id"]

    k2 = reopen_kernel(temp_state_dir, policy=KernelPolicy(max_card_revisions=10))
    with pytest.raises(KernelRefusalError):
        k2.ingest_stuck(
            make_stuck(event_id=eid, task_description="changed"),
            resolution=resolution_tasks,
        )