"""M2 verifier cross-surface validation tests.

Tests proving corruption is rejected consistently across all surfaces:
check_database, show, and replay all reject the same corruption.

Also validates write-before-commit: failed writes leave no rows.
"""

from __future__ import annotations

import json
import sqlite3 as sqlite3_module
import pytest
from typing import Any

from m2_verifier_support import (
    corrupt_aggregate,
    corrupt_message_payload,
    make_response,
    make_stuck,
    reopen_kernel,
    KernelCorruptionError,
    KernelRefusalError,
)


# ===========================================================================
# Bundle boundary: check_database, show, replay all reject same corruption
# ===========================================================================


def test_corruption_rejected_by_all_surfaces(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """check_database, show, and replay all reject the same aggregate corruption."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    eid = op.result["event_id"]
    card = op.result["card"]

    kernel.respond(make_response(card, "start"), resolution=resolution_tasks)

    corrupt_aggregate(temp_state_dir, eid, remove_key="revisions")

    with pytest.raises(KernelCorruptionError):
        kernel.check_database()

    # show detects
    with pytest.raises(KernelCorruptionError):
        kernel.show(eid)

    # replay detects
    k2 = reopen_kernel(temp_state_dir)
    with pytest.raises(KernelCorruptionError):
        k2.respond(make_response(card, "dismiss"), resolution=resolution_tasks)


# ===========================================================================
# Aggregate corruption: check_database and show both reject
# ===========================================================================


def test_corrupt_aggregate_rejected_by_show(
    temp_state_dir, stuck_with_resolution
) -> None:
    """Corruption that check_database finds must also be rejected by show."""
    eid = stuck_with_resolution["event_id"]
    kernel = stuck_with_resolution["kernel"]

    corrupt_aggregate(temp_state_dir, eid, remove_key="revisions")

    with pytest.raises(KernelCorruptionError):
        kernel.check_database()

    with pytest.raises(KernelCorruptionError):
        kernel.show(eid)


def test_non_canonical_aggregate_rejected(
    temp_state_dir, stuck_with_resolution
) -> None:
    """Non-canonical JSON in aggregate is rejected by both surfaces."""
    eid = stuck_with_resolution["event_id"]
    kernel = stuck_with_resolution["kernel"]

    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.row_factory = sqlite3_module.Row
    try:
        row = conn.execute(
            "SELECT aggregate_json FROM interactions WHERE event_id = ?", (eid,)
        ).fetchone()
        agg = json.loads(row["aggregate_json"])
        noncanonical = json.dumps(agg, indent=2)
        conn.execute(
            "UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
            (noncanonical, eid),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(KernelCorruptionError):
        kernel.check_database()

    with pytest.raises(KernelCorruptionError):
        kernel.show(eid)


# ===========================================================================
# Write validated before commit
# ===========================================================================


def test_write_validated_before_commit(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """Successful write is validated and persisted; failing write leaves no rows."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    eid = op.result["event_id"]
    assert kernel.check_database()["status"] == "ok"

    with pytest.raises((ValueError, KernelRefusalError)):
        kernel.ingest_stuck({"x": 1}, resolution=resolution_tasks)

    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.row_factory = sqlite3_module.Row
    try:
        count = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        assert count == 1, f"Expected 1 interaction after failed write, got {count}"
    finally:
        conn.close()


def test_atomic_transaction_on_conflict(
    temp_state_dir, kernel, stuck_event, resolution_tasks
) -> None:
    """Conflicting Stuck write (changed content) rolls back atomically."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    eid = op.result["event_id"]

    with pytest.raises(KernelRefusalError):
        kernel.ingest_stuck(
            make_stuck(event_id=eid, task_description="changed content"),
            resolution=resolution_tasks,
        )

    s = kernel.show(eid)
    assert s["phase"] == "awaiting_response"
    assert s["terminal_status"] is None
    assert kernel.check_database()["status"] == "ok"


def test_message_corruption_rejected_by_replay(
    temp_state_dir, stuck_with_resolution, resolution_tasks
) -> None:
    """Message corruption that check_database finds also blocks replay."""
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]
    kernel = stuck_with_resolution["kernel"]

    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.row_factory = sqlite3_module.Row
    try:
        msg_row = conn.execute(
            "SELECT message_id FROM messages WHERE kind='stuck' AND event_id=?",
            (eid,),
        ).fetchone()
        if msg_row:
            corrupt_message_payload(temp_state_dir, msg_row["message_id"])
    finally:
        conn.close()

    with pytest.raises(KernelCorruptionError):
        kernel.check_database()

    k2 = reopen_kernel(temp_state_dir)
    with pytest.raises(KernelCorruptionError):
        k2.respond(make_response(card, "dismiss"), resolution=resolution_tasks)
