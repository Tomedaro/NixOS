"""M2 valid/degraded evidence acceptance tests (E01-E05).

Tests that the kernel correctly handles evidence with specific timestamps:
late observations, pre-Card observations, clock-skew boundaries, and
evidence durability through restart and show.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from m2_support import (
    FIXED_NOW_BASE,
    REV_FIXTURE,
    KernelPolicy,
    KernelCorruptionError,
    KernelRefusalError,
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)


# ===========================================================================
# E01: Observation evidence with exact timestamps
# ===========================================================================


def test_M2_E01_observation_with_exact_timestamps(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Observation start with specific timestamp is persisted and durable."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    ts = FIXED_NOW_BASE + 42
    k2 = reopen_kernel(temp_state_dir, clock=lambda: ts)
    resp = make_response(card, "start", occurred_at_epoch=ts)
    r = k2.respond(resp, resolution=resolution_tasks)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "observing"

    # verify via check_database
    cdb = k2.check_database()
    assert cdb["status"] == "ok"

    # verify via show
    s = k2.show(eid)
    assert s["phase"] == "observing"

    # reopen and verify persistence
    k3 = reopen_kernel(temp_state_dir, clock=lambda: ts + 1)
    s3 = k3.show(eid)
    assert s3["phase"] == "observing"


# ===========================================================================
# E02: Pre-Card observation (response before card issued)
# ===========================================================================


def test_M2_E02_pre_card_observation(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Response with timestamp beyond max-future-skew is refused."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    # Future-skew beyond 300s default should be refused
    future_ts = card["issued_at_epoch"] + 500
    with pytest.raises((KernelRefusalError, KernelCorruptionError)):
        k.respond(make_response(card, "start", occurred_at_epoch=future_ts), resolution=resolution_tasks)


# ===========================================================================
# E03: Clock-skew boundary (299 seconds — just within tolerance)
# ===========================================================================


def test_M2_E03_clock_skew_boundary(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Response timestamp within clock-skew tolerance is accepted."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    card = op.result["card"]
    eid = op.result["event_id"]

    # 299 seconds past card issued_at — within default 300s skew
    late_ts = card["issued_at_epoch"] + 299
    k2 = reopen_kernel(temp_state_dir, clock=lambda: late_ts)
    resp = make_response(card, "start", occurred_at_epoch=late_ts)
    r = k2.respond(resp, resolution=resolution_tasks)
    assert r.result["status"] == "accepted"

    cdb = k2.check_database()
    assert cdb["status"] == "ok"


# ===========================================================================
# E04: Evidence durability through restart
# ===========================================================================


def test_M2_E04_evidence_durability(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Response evidence survives close/reopen cycle."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]
    eid = stuck_with_resolution["event_id"]

    resp = make_response(card, "start", occurred_at_epoch=FIXED_NOW_BASE)
    r = k.respond(resp, resolution=resolution_tasks)
    assert r.result["status"] == "accepted"

    # reopen
    k2 = reopen_kernel(temp_state_dir)
    s = k2.show(eid, include_sensitive=True)
    assert s["phase"] == "observing"
    assert "aggregate" in s
    rev = s["aggregate"]["revisions"][-1]
    # Verify revision has a card_id (evidence of persisted response)
    assert "card_id" in rev


# ===========================================================================
# E05: Exact replay of response with specific timestamps
# ===========================================================================


def test_M2_E05_exact_replay_with_timestamps(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Replay of response with specific timestamp returns identical result."""
    k = stuck_with_resolution["kernel"]
    card = stuck_with_resolution["card"]

    resp = make_response(card, "start", occurred_at_epoch=FIXED_NOW_BASE - 5)
    r1 = k.respond(resp, resolution=resolution_tasks)
    assert not r1.replay
    assert r1.result["status"] == "accepted"

    # Exact replay
    r2 = k.respond(resp, resolution=resolution_tasks)
    assert r2.replay is True
    assert r1.result == r2.result