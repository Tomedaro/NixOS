"""M2 cross-surface validation acceptance tests (V01-V04).

V01: prove check_database, show, list_active, replay all use the same
     validation bundle boundary.
V02-V03: corruption rejected by check_database is also rejected by
         show/replay (no silent acceptance).
V04: successful write validated before commit.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3 as sqlite3_module
import uuid
from typing import Any

import pytest

from m2_support import (
    FIXED_NOW_BASE,
    REV_FIXTURE,
    KernelCorruptionError,
    KernelRefusalError,
    KernelPolicy,
    TaskInitiationKernel,
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)


# ===========================================================================
# V01: check_database, show, list_active, replay share bundle boundary
# ===========================================================================


def test_M2_V01_bundle_boundary_shared(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """Prove that check_database, show, list_active, and replay all reject the
    same corruption — confirming they share one validation bundle boundary."""
    op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    eid = op.result["event_id"]
    card = op.result["card"]
    kernel.respond(make_response(card, "start"), resolution=resolution_tasks)

    # Corrupt: drop the active deadline index
    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.execute("DROP INDEX interactions_active_deadline_idx")
    conn.commit()
    conn.close()

    k2 = reopen_kernel(temp_state_dir)

    # All four surfaces must reject
    with pytest.raises(KernelCorruptionError):
        k2.check_database()
    with pytest.raises(KernelCorruptionError):
        k2.show(eid)
    with pytest.raises(KernelCorruptionError):
        k2.list_active()
    with pytest.raises(KernelCorruptionError):
        k2.respond(make_response(card, "dismiss"), resolution=resolution_tasks)


# ===========================================================================
# V02: Corrupt aggregate rejected by check_database AND show
# ===========================================================================


def test_M2_V02_corrupt_aggregate_rejected_by_show(
    temp_state_dir: Any, stuck_with_resolution: Any
) -> None:
    """Corruption that check_database finds must also be rejected by show."""
    k = stuck_with_resolution["kernel"]
    eid = stuck_with_resolution["event_id"]

    # Corrupt: remove a required key from aggregate
    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    row = conn.execute("SELECT * FROM interactions WHERE event_id = ?", (eid,)).fetchone()
    agg = json.loads(row[2])  # aggregate_json column
    del agg["revisions"]
    conn.execute(
        "UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
        (json.dumps(agg, sort_keys=True, separators=(",", ":")), eid),
    )
    conn.commit()
    conn.close()

    k2 = reopen_kernel(temp_state_dir)
    with pytest.raises(KernelCorruptionError):
        k2.check_database()
    with pytest.raises(KernelCorruptionError):
        k2.show(eid)


# ===========================================================================
# V03: Corrupt message rejected by check_database AND replay
# ===========================================================================


def test_M2_V03_corrupt_message_rejected_by_replay(
    temp_state_dir: Any, stuck_with_resolution: Any
, resolution_tasks: Any) -> None:
    """Corruption in message table that check_database finds must also
    be rejected by replay."""
    k = stuck_with_resolution["kernel"]
    eid = stuck_with_resolution["event_id"]
    card = stuck_with_resolution["card"]

    resp = make_response(card, "start")
    k.respond(resp, resolution=resolution_tasks)

    # Corrupt: change message payload_sha256
    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.execute(
        "UPDATE messages SET payload_sha256 = ? WHERE event_id = ?",
        ("0" * 64, eid),
    )
    conn.commit()
    conn.close()

    k2 = reopen_kernel(temp_state_dir)
    with pytest.raises(KernelCorruptionError):
        k2.check_database()
    with pytest.raises(KernelCorruptionError):
        k2.respond(make_response(card, "dismiss"), resolution=resolution_tasks)


# ===========================================================================
# V04: Write validated before commit
# ===========================================================================


def test_M2_V04_write_validated_before_commit(
    temp_state_dir: Any, kernel: Any, stuck_event: Any, resolution_tasks: Any
) -> None:
    """A successful write is validated at persistence time.  A failing write
    (e.g. malformed payload) must leave no trace."""
    # Malformed stuck — should leave NO rows
    with pytest.raises(ValueError):
        kernel.ingest_stuck({"x": 1}, resolution=resolution_tasks)

    with kernel._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 0

    # Expired stuck must also leave no trace
    k_exp = reopen_kernel(
        temp_state_dir, clock=lambda: FIXED_NOW_BASE + 10000
    )
    k_exp.initialize()
    res = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "V04", "revision": REV_FIXTURE}},
    )
    with pytest.raises(KernelRefusalError):
        k_exp.ingest_stuck(
            make_stuck(occurred_at_epoch=FIXED_NOW_BASE),
            resolution=res,
        )

    with k_exp._store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0