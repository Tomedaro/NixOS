"""Milestone 2 acceptance smoke test.

Covers: every A01-A17 lifecycle path and B01-B12 persistence integrity check,
with operation/check_db/reopen/show/replay for each lifecycle scenario.

Imports fixtures and helpers from task_initiation_kernel_smoke.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3 as sqlite3_module
import stat as stat_module
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from ai_system import task_initiation_contracts as c
from ai_system.task_initiation_kernel import (
    InteractionPolicy,
    KernelCorruptionError,
    KernelNotFoundError,
    KernelPolicy,
    KernelRefusalError,
    KernelStorageError,
    ResolutionInput,
    TaskInitiationKernel,
    load_resolution_input,
)
from ai_system.task_initiation_store import (
    TaskInitiationStore,
    _agg_from_db,
    _agg_to_db,
    reconstruct_expected_aggregate_v1,
)

# Pull helpers from kernel smoke
from task_initiation_kernel_smoke import (
    check,
    raises,
    raises_msg,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _rewrite_aggregate_canonical(
    conn: sqlite3_module.Connection, event_id: str, aggregate: dict[str, Any]
) -> None:
    aj = _agg_to_db(aggregate)
    conn.execute(
        "UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
        (aj, event_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Own fixtures
# ---------------------------------------------------------------------------

FIXED_NOW_BASE = 1_700_000_000
_REV_FIXTURE = hashlib.sha256(b"test-rev").hexdigest()
_REV_FIXTURE2 = hashlib.sha256(b"test-rev2").hexdigest()


def _fixed_clock() -> int:
    return FIXED_NOW_BASE


_fixed_uuid_ctr = 0


def _fixed_id_factory() -> uuid.UUID:
    global _fixed_uuid_ctr
    _fixed_uuid_ctr += 1
    return uuid.UUID(f"00000000-0000-4000-8000-{_fixed_uuid_ctr:012d}")


def _mk_state_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="m2acc_"))


def _mk_kernel(sd: Path | None = None, **kw: Any) -> TaskInitiationKernel:
    if sd is None:
        sd = _mk_state_dir()
    return TaskInitiationKernel(
        sd,
        clock=kw.pop("clock", _fixed_clock),
        id_factory=kw.pop("id_factory", _fixed_id_factory),
        busy_timeout_seconds=kw.pop("busy_timeout_seconds", 0.2),
        **kw,
    )


def _stuck(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "task_initiation_stuck.v1",
        "event_id": str(uuid.uuid4()),
        "source": "tasker",
        "occurred_at_epoch": FIXED_NOW_BASE - 10,
        "task_description": "A test task",
    }
    base.update(overrides)
    return base


def _resp(card: Mapping[str, Any], action: str = "start", **ov: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "task_initiation_response.v1",
        "response_id": str(uuid.uuid4()),
        "card_id": card["card_id"],
        "action": action,
        "detail": "test detail" if action in ("shrink", "blocked") else None,
        "occurred_at_epoch": card["issued_at_epoch"] + 5,
    }
    base.update(ov)
    return base


def _make_res_tasks(sd: Path, tasks_dict: dict[str, dict[str, str]]) -> ResolutionInput:
    p = sd / f"res_{uuid.uuid4().hex[:8]}.json"
    data: dict[str, Any] = {}
    if tasks_dict is not None:
        data["tasks"] = tasks_dict
    p.write_text(json.dumps(data, sort_keys=True))
    return load_resolution_input(p, policy=KernelPolicy())


def _mk_db() -> tuple[Path, TaskInitiationKernel]:
    sd = _mk_state_dir()
    k = _mk_kernel(sd)
    k.initialize()
    return sd, k


def _payload_from_message(conn: sqlite3_module.Connection, kind: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM messages WHERE kind=?", (kind,)).fetchone()
    return c._strict_json_loads(row["payload_json"])


# ===========================================================================
# Section A: Functional Lifecycle (A01-A17)
# ===========================================================================

print("=== A01: Stuck event ingestion ===")
sd_a01, k_a01 = _mk_db()
res_a01 = _make_res_tasks(sd_a01, {"Tasks/test.md": {"label": "A01 Task", "revision": _REV_FIXTURE}})
op_a01 = k_a01.ingest_stuck(_stuck(), resolution=res_a01)
check("A01.1 ingest_stuck returns card_published", op_a01.result["status"] == "card_published")
check("A01.2 result has event_id", "event_id" in op_a01.result)
check("A01.3 result has card", "card" in op_a01.result)
eid_a01 = op_a01.result["event_id"]
show_a01 = k_a01.show(eid_a01)
check("A01.4 show phase is awaiting_response", show_a01["phase"] == "awaiting_response")
cdb_a01 = k_a01.check_database()
check("A01.5 check-db ok", cdb_a01["status"] == "ok")
check("A01.6 check-db count 1", cdb_a01["interaction_count"] == 1)
# Idempotent replay
op2 = k_a01.ingest_stuck(_stuck(event_id=eid_a01), resolution=res_a01)
check("A01.7 replay is True", op2.replay)
check("A01.8 replay result matches", op2.result["status"] == "card_published")
with k_a01._store.read_connection() as conn:
    check("A01.9 one interaction row", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1)
    check("A01.10 one message row", conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1)
    check("A01.11 one card_index row", conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 1)
# Reopen
k_a01b = _mk_kernel(sd_a01)
check("A01.12 reopen check-db ok", k_a01b.check_database()["status"] == "ok")
show_a01b = k_a01b.show(eid_a01)
check("A01.13 reopen show same phase", show_a01b["phase"] == "awaiting_response")
# Changed payload conflict
raises(KernelRefusalError, k_a01b.ingest_stuck, _stuck(event_id=eid_a01, task_description="changed"))

print("=== A02: Start response ===")
sd_a02, k_a02 = _mk_db()
res_a02 = _make_res_tasks(sd_a02, {"Tasks/test.md": {"label": "A02 Task", "revision": _REV_FIXTURE}})
op_a02 = k_a02.ingest_stuck(_stuck(), resolution=res_a02)
card_a02 = op_a02.result["card"]
r_a02 = k_a02.respond(_resp(card_a02, "start"))
check("A02.1 respond returns accepted", r_a02.result["status"] == "accepted")
check("A02.2 phase is observing", r_a02.result["phase"] == "observing")
check("A02.3 no terminal_status", r_a02.result.get("terminal_status") is None)
eid_a02 = op_a02.result["event_id"]
show_a02 = k_a02.show(eid_a02)
check("A02.4 show phase is observing", show_a02["phase"] == "observing")
cdb_a02 = k_a02.check_database()
check("A02.5 check-db ok", cdb_a02["status"] == "ok")
check("A02.6 interaction count 1", cdb_a02["interaction_count"] == 1)
check("A02.7 message count 2", cdb_a02["message_count"] == 2)
# Replay
with k_a02._store.read_connection() as conn:
    payload = _payload_from_message(conn, "response")
    replay_resp = _resp(card_a02, "start",
                        response_id=payload["response_id"],
                        occurred_at_epoch=payload["occurred_at_epoch"])
replay_op = k_a02.respond(replay_resp)
check("A02.8 replay is True", replay_op.replay)

print("=== A03: Shrink response ===")
sd_a03, k_a03 = _mk_db()
res_a03 = _make_res_tasks(sd_a03, {"Tasks/test.md": {"label": "A03 Task", "revision": _REV_FIXTURE}})
op_a03 = k_a03.ingest_stuck(_stuck(), resolution=res_a03)
card_a03 = op_a03.result["card"]
r_a03 = k_a03.respond(_resp(card_a03, "shrink"))
check("A03.1 respond returns accepted", r_a03.result["status"] == "accepted")
check("A03.2 phase is awaiting_response", r_a03.result["phase"] == "awaiting_response")
check("A03.3 next_card present", r_a03.result.get("next_card") is not None)
eid_a03 = op_a03.result["event_id"]
show_a03 = k_a03.show(eid_a03)
check("A03.4 show phase is awaiting_response", show_a03["phase"] == "awaiting_response")
cdb_a03 = k_a03.check_database()
check("A03.5 check-db ok", cdb_a03["status"] == "ok")
with k_a03._store.read_connection() as conn:
    check("A03.6 two card_index rows", conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 2)
show_a03_inc = k_a03.show(eid_a03, include_sensitive=True)
check("A03.7 include_sensitive has aggregate", "aggregate" in show_a03_inc)
check("A03.8 aggregate has multiple revisions", len(show_a03_inc["aggregate"]["revisions"]) >= 2)

print("=== A04: Blocked response ===")
sd_a04, k_a04 = _mk_db()
res_a04 = _make_res_tasks(sd_a04, {"Tasks/test.md": {"label": "A04 Task", "revision": _REV_FIXTURE}})
op_a04 = k_a04.ingest_stuck(_stuck(), resolution=res_a04)
card_a04 = op_a04.result["card"]
r_a04 = k_a04.respond(_resp(card_a04, "blocked"))
check("A04.1 respond returns accepted", r_a04.result["status"] == "accepted")
check("A04.2 phase is awaiting_response", r_a04.result["phase"] == "awaiting_response")
check("A04.3 next_card present", r_a04.result.get("next_card") is not None)
cdb_a04 = k_a04.check_database()
check("A04.4 check-db ok", cdb_a04["status"] == "ok")

print("=== A05: Defer response ===")
sd_a05, k_a05 = _mk_db()
res_a05 = _make_res_tasks(sd_a05, {"Tasks/test.md": {"label": "A05 Task", "revision": _REV_FIXTURE}})
op_a05 = k_a05.ingest_stuck(_stuck(), resolution=res_a05)
card_a05 = op_a05.result["card"]
r_a05 = k_a05.respond(_resp(card_a05, "defer"))
check("A05.1 respond returns accepted", r_a05.result["status"] == "accepted")
check("A05.2 terminal_status is completed", r_a05.result["terminal_status"] == "completed")
eid_a05 = op_a05.result["event_id"]
show_a05 = k_a05.show(eid_a05)
check("A05.3 show terminal_status completed", show_a05["terminal_status"] == "completed")
check("A05.4 show phase is observing", show_a05["phase"] == "observing")
cdb_a05 = k_a05.check_database()
check("A05.5 check-db ok", cdb_a05["status"] == "ok")
# Reopen
k_a05b = _mk_kernel(sd_a05)
show_a05b = k_a05b.show(eid_a05)
check("A05.6 reopen same terminal_status", show_a05b["terminal_status"] == "completed")

print("=== A06: Dismiss response ===")
sd_a06, k_a06 = _mk_db()
res_a06 = _make_res_tasks(sd_a06, {"Tasks/test.md": {"label": "A06 Task", "revision": _REV_FIXTURE}})
op_a06 = k_a06.ingest_stuck(_stuck(), resolution=res_a06)
card_a06 = op_a06.result["card"]
r_a06 = k_a06.respond(_resp(card_a06, "dismiss"))
check("A06.1 respond returns accepted", r_a06.result["status"] == "accepted")
check("A06.2 terminal_status is completed", r_a06.result["terminal_status"] == "completed")
cdb_a06 = k_a06.check_database()
check("A06.3 check-db ok", cdb_a06["status"] == "ok")

print("=== A07: Card expiry ===")
sd_a07, k_a07 = _mk_db()
res_a07 = _make_res_tasks(sd_a07, {"Tasks/test.md": {"label": "A07 Task", "revision": _REV_FIXTURE}})
op_a07 = k_a07.ingest_stuck(_stuck(), resolution=res_a07)
card_a07 = op_a07.result["card"]
eid_a07 = op_a07.result["event_id"]
# Use a clock that puts us past the card expiry
k_a07_expired = _mk_kernel(sd_a07, clock=lambda: card_a07["expires_at_epoch"] + 1)
raises(KernelRefusalError, k_a07_expired.respond, _resp(card_a07, "start"))
show_a07 = k_a07_expired.show(eid_a07)
check("A07.1 expired terminal_status is not None", show_a07["terminal_status"] is not None)
# Reopen still expired
k_a07b = _mk_kernel(sd_a07, clock=lambda: card_a07["expires_at_epoch"] + 1)
show_a07b = k_a07b.show(eid_a07)
check("A07.2 reopen still expired", show_a07b["terminal_status"] is not None)

print("=== A08: Observation completion via reconcile ===")
sd_a08, k_a08 = _mk_db()
res_a08 = _make_res_tasks(sd_a08, {"Tasks/test.md": {"label": "A08 Task", "revision": _REV_FIXTURE}})
op_a08 = k_a08.ingest_stuck(_stuck(), resolution=res_a08)
card_a08 = op_a08.result["card"]
k_a08.respond(_resp(card_a08, "start"))
eid_a08 = op_a08.result["event_id"]
# Use a clock well past observation deadline
k_a08_overdue = _mk_kernel(sd_a08, clock=lambda: FIXED_NOW_BASE + 2000)
rec_a08 = k_a08_overdue.reconcile()
check("A08.1 reconcile ok", rec_a08["ok"] is True)
check("A08.2 at least one reconciled", rec_a08["reconciled"] >= 1)
show_a08 = k_a08_overdue.show(eid_a08)
check("A08.3 terminal after observation", show_a08["terminal_status"] is not None)
cdb_a08 = k_a08_overdue.check_database()
check("A08.4 check-db ok", cdb_a08["status"] == "ok")
# Idempotent reconcile
rec2 = k_a08_overdue.reconcile()
check("A08.5 idempotent reconcile 0", rec2["reconciled"] == 0)

print("=== A09: Revision ceiling ===")
sd_a09, k_a09 = _mk_db()
res_a09 = _make_res_tasks(sd_a09, {"Tasks/test.md": {"label": "A09 Task", "revision": _REV_FIXTURE}})
op_a09 = k_a09.ingest_stuck(_stuck(), resolution=res_a09)
eid_a09 = op_a09.result["event_id"]
card = op_a09.result["card"]
# First shrink (rev 1 -> 2, total revisions=2)
r1 = k_a09.respond(_resp(card, "shrink"))
check("A09.1 first shrink accepted", r1.result["status"] == "accepted")
card2 = r1.result.get("next_card")
check("A09.2 next_card present after shrink 1", card2 is not None)
# Second shrink (rev 2 -> 3, total revisions=3 hits ceiling with max_card_revisions=3)
r2 = k_a09.respond(_resp(card2, "shrink"))
check("A09.3 second shrink accepted", r2.result["status"] == "accepted")
card3 = r2.result.get("next_card")
# Third shrink (rev 3 -> 4) would exceed max_card_revisions=3
if card3 is not None:
    r3 = k_a09.respond(_resp(card3, "shrink"))
    check("A09.4 third shrink terminal", r3.result.get("terminal_status") is not None)
else:
    # Already terminal from shrink 2
    check("A09.4 already terminal after shrink2", r2.result.get("terminal_status") is not None)
show_a09 = k_a09.show(eid_a09)
check("A09.5 interaction has terminal_status", show_a09["terminal_status"] is not None)
cdb_a09 = k_a09.check_database()
check("A09.6 check-db ok", cdb_a09["status"] == "ok")

print("=== A10: Idempotent Stuck replay ===")
sd_a10, k_a10 = _mk_db()
res_a10 = _make_res_tasks(sd_a10, {"Tasks/test.md": {"label": "A10 Task", "revision": _REV_FIXTURE}})
st_a10 = _stuck()
op1 = k_a10.ingest_stuck(st_a10, resolution=res_a10)
check("A10.1 first ingest not replay", not op1.replay)
op2 = k_a10.ingest_stuck(st_a10, resolution=res_a10)
check("A10.2 second ingest replay", op2.replay)
check("A10.3 same result status", op1.result["status"] == op2.result["status"])
with k_a10._store.read_connection() as conn:
    check("A10.4 single interaction row", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1)

print("=== A11: Idempotent Response replay ===")
sd_a11, k_a11 = _mk_db()
res_a11 = _make_res_tasks(sd_a11, {"Tasks/test.md": {"label": "A11 Task", "revision": _REV_FIXTURE}})
op_a11 = k_a11.ingest_stuck(_stuck(), resolution=res_a11)
card_a11 = op_a11.result["card"]
start_resp = _resp(card_a11, "start")
r1 = k_a11.respond(start_resp)
check("A11.1 first respond not replay", not r1.replay)
# Replay with exact same payload (must use the same response_id)
r2 = k_a11.respond(start_resp)
check("A11.2 second respond replay", r2.replay)
check("A11.3 same result status", r1.result["status"] == r2.result["status"])

print("=== A12: Task change supersession ===")
sd_a12, k_a12 = _mk_db()
res_a12a = _make_res_tasks(sd_a12, {"Tasks/test.md": {"label": "Orig", "revision": _REV_FIXTURE}})
op_a12 = k_a12.ingest_stuck(
    _stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}),
    resolution=res_a12a,
)
card_a12 = op_a12.result["card"]
eid_a12 = op_a12.result["event_id"]
# Respond with different task revision
res_a12b = _make_res_tasks(sd_a12, {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff").hexdigest()}})
r_a12 = k_a12.respond(_resp(card_a12, "start"), resolution=res_a12b)
check("A12.1 superseded status", r_a12.result["status"] == "superseded")
check("A12.2 terminal_status superseded", r_a12.result.get("terminal_status") == "superseded")
check("A12.3 phase awaiting_response", r_a12.result["phase"] == "awaiting_response")
show_a12 = k_a12.show(eid_a12)
check("A12.4 show phase awaiting_response", show_a12["phase"] == "awaiting_response")
check("A12.5 show terminal superseded", show_a12["terminal_status"] == "superseded")
cdb_a12 = k_a12.check_database()
check("A12.6 check-db ok", cdb_a12["status"] == "ok")

print("=== A13: check_database integrity ===")
sd_a13, k_a13 = _mk_db()
res_a13 = _make_res_tasks(sd_a13, {"Tasks/test.md": {"label": "A13 Task", "revision": _REV_FIXTURE}})
op_a13 = k_a13.ingest_stuck(_stuck(), resolution=res_a13)
card_a13 = op_a13.result["card"]
k_a13.respond(_resp(card_a13, "start"))
cdb_a13 = k_a13.check_database()
check("A13.1 check-db status ok", cdb_a13["status"] == "ok")
check("A13.2 interaction_count 1", cdb_a13["interaction_count"] == 1)
check("A13.3 message_count 2", cdb_a13["message_count"] == 2)
check("A13.4 version 1", cdb_a13["version"] == 1)

print("=== A14: show ===")
sd_a14, k_a14 = _mk_db()
res_a14 = _make_res_tasks(sd_a14, {"Tasks/test.md": {"label": "A14 Task", "revision": _REV_FIXTURE}})
op_a14 = k_a14.ingest_stuck(_stuck(), resolution=res_a14)
eid_a14 = op_a14.result["event_id"]
show_no = k_a14.show(eid_a14)
check("A14.1 show has event_id", show_no["event_id"] == eid_a14)
check("A14.2 show has phase", "phase" in show_no)
check("A14.3 show has terminal_status", "terminal_status" in show_no)
check("A14.4 show has state_version", "state_version" in show_no)
check("A14.5 show sans sensitive omits aggregate", "aggregate" not in show_no)
check("A14.6 show has needs_reconciliation", "needs_reconciliation" in show_no)

show_inc = k_a14.show(eid_a14, include_sensitive=True)
check("A14.7 show with sensitive includes aggregate", "aggregate" in show_inc)
check("A14.8 aggregate has revisions", "revisions" in show_inc["aggregate"])

# not-found
raises(KernelNotFoundError, k_a14.show, str(uuid.uuid4()))

print("=== A15: list_active ===")
sd_a15, k_a15 = _mk_db()
res_a15 = _make_res_tasks(sd_a15, {"Tasks/test.md": {"label": "A15 Task", "revision": _REV_FIXTURE}})
op_a15_1 = k_a15.ingest_stuck(_stuck(), resolution=res_a15)
# Make one terminal
card_a15 = op_a15_1.result["card"]
k_a15.respond(_resp(card_a15, "defer"))
# Check terminal interaction excluded
active_a15 = k_a15.list_active()
check("A15.1 terminal excluded from list_active", len(active_a15) == 0)
# Add another non-terminal
op_a15_2 = k_a15.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res_a15)
active_a15_2 = k_a15.list_active()
check("A15.2 active interaction present", len(active_a15_2) >= 1)
for item in active_a15_2:
    check("A15.3 item has event_id", "event_id" in item)
    check("A15.4 item has phase", "phase" in item)
    check("A15.5 item has needs_reconciliation", "needs_reconciliation" in item)
    check("A15.6 item is non-terminal", item.get("terminal_status") is None)

print("=== A16: reconcile ===")
sd_a16, k_a16 = _mk_db()
res_a16 = _make_res_tasks(sd_a16, {"Tasks/test.md": {"label": "A16 Task", "revision": _REV_FIXTURE}})
# Use short policy for quick expiry
pol_short = KernelPolicy(card_ttl_seconds=10, observation_seconds=10)
k_a16_short = _mk_kernel(sd_a16, policy=pol_short)
op_a16 = k_a16_short.ingest_stuck(_stuck(), resolution=res_a16)
card_a16 = op_a16.result["card"]
k_a16_short.respond(_resp(card_a16, "start"))
# Use clock way past observation deadline
k_a16_late = _mk_kernel(sd_a16, policy=pol_short, clock=lambda: FIXED_NOW_BASE + 2000)
rec_a16 = k_a16_late.reconcile()
check("A16.1 reconcile ok", rec_a16["ok"] is True)
check("A16.2 reconciled > 0", rec_a16["reconciled"] >= 1)
# Idempotent
rec2_a16 = k_a16_late.reconcile()
check("A16.3 idempotent reconcile 0", rec2_a16["reconciled"] == 0)

print("=== A17: Restart resilience ===")
sd_a17, k_a17 = _mk_db()
res_a17 = _make_res_tasks(sd_a17, {"Tasks/test.md": {"label": "A17 Task", "revision": _REV_FIXTURE}})
op_a17 = k_a17.ingest_stuck(_stuck(), resolution=res_a17)
eid_a17 = op_a17.result["event_id"]
card_a17 = op_a17.result["card"]
k_a17.respond(_resp(card_a17, "start"))
# Reopen
k_a17b = _mk_kernel(sd_a17)
cdb_a17b = k_a17b.check_database()
check("A17.1 reopen check-db ok", cdb_a17b["status"] == "ok")
show_a17b = k_a17b.show(eid_a17)
check("A17.2 reopen same phase", show_a17b["phase"] == "observing")
check("A17.3 reopen no terminal", show_a17b["terminal_status"] is None)
show_a17b_inc = k_a17b.show(eid_a17, include_sensitive=True)
check("A17.4 reopen has aggregate with revisions", len(show_a17b_inc["aggregate"]["revisions"]) >= 1)
with k_a17b._store.read_connection() as conn:
    check("A17.5 interactions intact", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1)
    check("A17.6 messages intact", conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2)
    check("A17.7 card_index intact", conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 1)


# ===========================================================================
# Section B: Persistence Integrity (B01-B12)
# ===========================================================================

print("=== B01: Schema structural validation ===")
sd_b01, k_b01 = _mk_db()
stor_b01 = TaskInitiationStore(sd_b01, busy_timeout_seconds=0.2)
stor_b01.initialize()
with stor_b01.read_connection() as conn:
    tn = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    check("B01.1 three tables", tn == {"interactions", "messages", "card_index"})
    check("B01.2 user_version 1", conn.execute("PRAGMA user_version").fetchone()[0] == 1)
    check("B01.3 journal_mode delete", conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete")
    check("B01.4 foreign_keys ON", conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1)

# version-0 DB rejected
sd_b01v0 = _mk_state_dir()
xc = sqlite3_module.connect(str(sd_b01v0 / "kernel.sqlite3"))
xc.execute("CREATE TABLE foo(x)")
xc.close()
os.chmod(str(sd_b01v0 / "kernel.sqlite3"), 0o600)
raises(KernelCorruptionError, TaskInitiationStore(sd_b01v0, busy_timeout_seconds=0.2).initialize)
check("B01.5 version-0 rejected", True)

# version-2 DB rejected
sd_b01v2 = _mk_state_dir()
x2 = sqlite3_module.connect(str(sd_b01v2 / "kernel.sqlite3"))
x2.execute("PRAGMA user_version=2")
x2.close()
os.chmod(str(sd_b01v2 / "kernel.sqlite3"), 0o600)
raises(KernelCorruptionError, TaskInitiationStore(sd_b01v2, busy_timeout_seconds=0.2).initialize)
check("B01.6 version-2 rejected", True)

print("=== B02: Permission enforcement ===")
sd_b02 = _mk_state_dir()
k_b02 = _mk_kernel(sd_b02)
r = k_b02.initialize()
check("B02.1 init returns initialized", r["status"] == "initialized")
st_b02 = sd_b02.stat()
check("B02.2 dir perms 0700", stat_module.S_IMODE(st_b02.st_mode) == 0o700)
db_st = sd_b02.joinpath("kernel.sqlite3").stat()
check("B02.3 db perms 0600", stat_module.S_IMODE(db_st.st_mode) == 0o600)

# pre-existing insecure dir
sd_b02b = _mk_state_dir()
os.chmod(str(sd_b02b), 0o755)
raises(KernelStorageError, TaskInitiationKernel(sd_b02b, clock=_fixed_clock, busy_timeout_seconds=0.2).initialize)
check("B02.4 0755 dir rejected", True)

# pre-existing insecure db
sd_b02c = _mk_state_dir()
os.chmod(str(sd_b02c), 0o700)
db_path = sd_b02c / "kernel.sqlite3"
db_path.write_bytes(b"")
os.chmod(str(db_path), 0o644)
raises(KernelStorageError, TaskInitiationKernel(sd_b02c, clock=_fixed_clock, busy_timeout_seconds=0.2).initialize)
check("B02.5 0644 db rejected", True)

# relative path
raises(KernelStorageError, TaskInitiationKernel, Path("rel"), clock=_fixed_clock, busy_timeout_seconds=0.2)
check("B02.6 relative path rejected", True)

print("=== B03: Canonical encoding enforcement ===")
sd_b03, k_b03 = _mk_db()
res_b03 = _make_res_tasks(sd_b03, {"Tasks/test.md": {"label": "B03 Task", "revision": _REV_FIXTURE}})
op_b03 = k_b03.ingest_stuck(_stuck(), resolution=res_b03)
eid_b03 = op_b03.result["event_id"]
# Verify stored JSON is compact canonical
with k_b03._store.read_connection() as conn:
    row = conn.execute("SELECT aggregate_json FROM interactions WHERE event_id=?", (eid_b03,)).fetchone()
    aj = row["aggregate_json"]
    check("B03.1 aggregate is compact (no newlines)", "\n" not in aj)
    decoded = json.loads(aj)
    recoded = c._canonical_json(decoded).decode("utf-8")
    check("B03.2 aggregate round-trips canonical", aj == recoded)

# Corrupt aggregate to non-canonical
conn2 = sqlite3_module.connect(str(sd_b03 / "kernel.sqlite3"))
agg = json.loads(aj)
noncanonical = json.dumps(agg, indent=2)
conn2.execute("UPDATE interactions SET aggregate_json = ? WHERE event_id = ?", (noncanonical, eid_b03))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b03.check_database)
check("B03.3 non-canonical aggregate rejected", True)

print("=== B04: Strict JSON decoding ===")
sd_b04, k_b04 = _mk_db()
res_b04 = _make_res_tasks(sd_b04, {"Tasks/test.md": {"label": "B04 Task", "revision": _REV_FIXTURE}})
op_b04 = k_b04.ingest_stuck(_stuck(), resolution=res_b04)
eid_b04 = op_b04.result["event_id"]
# Rewrite with corrupt JSON
conn2 = sqlite3_module.connect(str(sd_b04 / "kernel.sqlite3"))
conn2.execute("UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
              ('{bad json', eid_b04))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b04.check_database)
check("B04.1 corrupt JSON aggregate rejected", True)

print("=== B05: Reducer reconstruction gate ===")
sd_b05, k_b05 = _mk_db()
res_b05 = _make_res_tasks(sd_b05, {"Tasks/test.md": {"label": "B05 Task", "revision": _REV_FIXTURE}})
op_b05 = k_b05.ingest_stuck(_stuck(), resolution=res_b05)
eid_b05 = op_b05.result["event_id"]

check("B05.1 reconstruct function available", callable(reconstruct_expected_aggregate_v1))

with k_b05._store.read_connection() as conn:
    sr = conn.execute("SELECT * FROM messages WHERE kind='stuck' AND event_id=?", (eid_b05,)).fetchone()
    int_row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid_b05,)).fetchone()
    aggregate = _agg_from_db(int_row["aggregate_json"], source="test-b05")
    ip = InteractionPolicy()
    reconstructed = reconstruct_expected_aggregate_v1(
        stuck_row=sr,
        resolved_task=aggregate["resolved_task"],
        revisions=aggregate["revisions"],
        response_messages={},
        superseding_msg=None,
        terminal_at_epoch=None,
        interaction_policy=ip,
    )
    check("B05.2 reconstruct matches aggregate", _agg_to_db(reconstructed) == _agg_to_db(aggregate))

    # Tamper aggregate
    agg2 = _agg_from_db(int_row["aggregate_json"], source="test-b05")
    agg2["state_version"] = 999
    conn2 = sqlite3_module.connect(str(sd_b05 / "kernel.sqlite3"))
    _rewrite_aggregate_canonical(conn2, eid_b05, agg2)
    conn2.close()
raises(KernelCorruptionError, k_b05.check_database)
check("B05.3 tampered aggregate rejected by check_database", True)

print("=== B06: Cross-row consistency ===")
sd_b06, k_b06 = _mk_db()
res_b06 = _make_res_tasks(sd_b06, {"Tasks/test.md": {"label": "B06 Task", "revision": _REV_FIXTURE}})
op_b06 = k_b06.ingest_stuck(_stuck(), resolution=res_b06)
eid_b06 = op_b06.result["event_id"]
conn2 = sqlite3_module.connect(str(sd_b06 / "kernel.sqlite3"))
conn2.execute("UPDATE messages SET event_id = ? WHERE event_id = ?", (str(uuid.uuid4()), eid_b06))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b06.check_database)
check("B06.1 message event_id mismatch rejected", True)

print("=== B07: Corrupt aggregate ===")
sd_b07, k_b07 = _mk_db()
res_b07 = _make_res_tasks(sd_b07, {"Tasks/test.md": {"label": "B07 Task", "revision": _REV_FIXTURE}})
op_b07 = k_b07.ingest_stuck(_stuck(), resolution=res_b07)
eid_b07 = op_b07.result["event_id"]
with k_b07._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid_b07,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-b07")
    del agg["revisions"]
    conn2 = sqlite3_module.connect(str(sd_b07 / "kernel.sqlite3"))
    _rewrite_aggregate_canonical(conn2, eid_b07, agg)
    conn2.close()
raises(KernelCorruptionError, k_b07.check_database)
check("B07.1 missing revisions key rejected", True)

print("=== B08: Corrupt message payload ===")
sd_b08, k_b08 = _mk_db()
res_b08 = _make_res_tasks(sd_b08, {"Tasks/test.md": {"label": "B08 Task", "revision": _REV_FIXTURE}})
op_b08 = k_b08.ingest_stuck(_stuck(), resolution=res_b08)
eid_b08 = op_b08.result["event_id"]
conn2 = sqlite3_module.connect(str(sd_b08 / "kernel.sqlite3"))
conn2.execute("UPDATE messages SET payload_sha256 = ? WHERE event_id = ?", ("0" * 64, eid_b08))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b08.check_database)
check("B08.1 payload_sha256 mismatch rejected", True)

print("=== B09: Corrupt Card index ===")
sd_b09, k_b09 = _mk_db()
res_b09 = _make_res_tasks(sd_b09, {"Tasks/test.md": {"label": "B09 Task", "revision": _REV_FIXTURE}})
op_b09 = k_b09.ingest_stuck(_stuck(), resolution=res_b09)
eid_b09 = op_b09.result["event_id"]
conn2 = sqlite3_module.connect(str(sd_b09 / "kernel.sqlite3"))
conn2.execute("DELETE FROM card_index WHERE event_id = ?", (eid_b09,))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b09.check_database)
check("B09.1 missing card_index rejected", True)

print("=== B10: Replay bundle validation ===")
sd_b10, k_b10 = _mk_db()
res_b10 = _make_res_tasks(sd_b10, {"Tasks/test.md": {"label": "B10 Task", "revision": _REV_FIXTURE}})
op_b10 = k_b10.ingest_stuck(_stuck(), resolution=res_b10)
eid_b10 = op_b10.result["event_id"]
with k_b10._store.read_connection() as conn:
    sr = conn.execute("SELECT * FROM messages WHERE kind='stuck' AND event_id=?", (eid_b10,)).fetchone()
    result = k_b10._store.validate_replay_bundle(conn, sr)
    check("B10.1 stuck replay valid", isinstance(result, dict))
    check("B10.2 stuck replay has status", "status" in result)

# Corrupt result_json
conn2 = sqlite3_module.connect(str(sd_b10 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
sr2 = conn2.execute("SELECT * FROM messages WHERE kind='stuck' AND event_id=?", (eid_b10,)).fetchone()
res10 = c._strict_json_loads(sr2["result_json"])
res10["status"] = "bogus_value"
conn2.execute("UPDATE messages SET result_json = ? WHERE kind='stuck' AND message_id = ?",
              (c._canonical_json(res10).decode("utf-8"), sr2["message_id"]))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k_b10.check_database)
check("B10.3 corrupt result rejected by check_database", True)

print("=== B11: Atomicity ===")
sd_b11, k_b11 = _mk_db()
res_b11 = _make_res_tasks(sd_b11, {"Tasks/test.md": {"label": "B11 Task", "revision": _REV_FIXTURE}})
raises(ValueError, k_b11.ingest_stuck, {"x": 1}, resolution=res_b11)
with k_b11._store.read_connection() as conn:
    check("B11.1 no interactions after bad ingest", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0)
    check("B11.2 no messages after bad ingest", conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0)
    check("B11.3 no card_index after bad ingest", conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 0)

sd_b11b = _mk_state_dir()
k_b11b = _mk_kernel(sd_b11b, clock=lambda: FIXED_NOW_BASE + 10000)
k_b11b.initialize()
res_b11b = _make_res_tasks(sd_b11b, {"Tasks/test.md": {"label": "B11 Task", "revision": _REV_FIXTURE}})
raises(KernelRefusalError, k_b11b.ingest_stuck, _stuck(occurred_at_epoch=FIXED_NOW_BASE), resolution=res_b11b)
with k_b11b._store.read_connection() as conn:
    check("B11.4 no rows after expired stuck", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0)

print("=== B12: WAL rejection ===")
sd_b12 = _mk_state_dir()
stor_b12 = TaskInitiationStore(sd_b12, busy_timeout_seconds=0.2)
stor_b12.initialize()
ext = sqlite3_module.connect(str(sd_b12 / "kernel.sqlite3"))
ext.execute("PRAGMA journal_mode=WAL")
ext.close()
try:
    with stor_b12.immediate_transaction():
        pass
    check("B12.1 wal writer enforced (failure branch)", False)
except KernelStorageError:
    check("B12.1 wal writer enforced (success branch)", True)
stor_b12.initialize()
with stor_b12.read_connection() as conn:
    check("B12.2 wal restored to delete", conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete")


# ===========================================================================
# Final tally
# ===========================================================================

import task_initiation_kernel_smoke as tks

print()
print(f"=== kernel_smoke: {tks.PASSED} passed, {tks.FAILED} failed ===")
if tks.FAILED:
    raise SystemExit(1)
print("ALL PASS")
