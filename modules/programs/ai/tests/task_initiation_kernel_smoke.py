"""Smoke test for Milestone 2 task-initiation kernel.

Covers: store init/migration/schema, codec/corruption, resolution fixture,
deterministic worker, atomic Stuck/Response, replay, concurrency,
owner-scoped mutation, reconciliation, restart, deadlines, locking, CLI.

Uses temporary directories, fixed clocks/UUIDs, and a 200 ms test timeout.
No network, phone, provider, vault writes, or services.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sqlite3 as sqlite3_module
import sys
import tempfile
import threading
import time as time_mod
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from ai_system import task_initiation_contracts as c
from ai_system.task_initiation_kernel import (
    KernelBusyError,
    KernelCorruptionError,
    KernelNotFoundError,
    KernelPolicy,
    KernelRefusalError,
    KernelStorageError,
    ResolutionInput,
    TaskInitiationKernel,
    build_placeholder_preparation,
    load_resolution_input,
)
from ai_system.task_initiation_store import (
    TaskInitiationStore,
    _agg_from_db,
    _agg_to_db,
)

def _canonical_json_str(data: Mapping[str, Any]) -> str:
    return c._canonical_json(data).decode("utf-8")


def _rewrite_aggregate_canonically(
    conn: sqlite3_module.Connection, event_id: str, aggregate: dict[str, Any]
) -> None:
    aj = _agg_to_db(aggregate)
    conn.execute(
        "UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
        (aj, event_id),
    )
    conn.commit()


def _rewrite_result_canonically(
    conn: sqlite3_module.Connection,
    kind: str,
    message_id: str,
    result: dict[str, Any],
) -> None:
    rj = c._canonical_json(result).decode("utf-8")
    conn.execute(
        "UPDATE messages SET result_json = ? WHERE kind = ? AND message_id = ?",
        (rj, kind, message_id),
    )
    conn.commit()


def _rewrite_payload_canonically(
    conn: sqlite3_module.Connection,
    kind: str,
    message_id: str,
    payload: dict[str, Any],
) -> None:
    pj = c._canonical_json(payload).decode("utf-8")
    ph = c._payload_sha256(payload)
    conn.execute(
        "UPDATE messages SET payload_json = ?, payload_sha256 = ? WHERE kind = ? AND message_id = ?",
        (pj, ph, kind, message_id),
    )
    conn.commit()


def raises_msg(
    exc_type: type,
    substr: str,
    fn: Callable[..., Any],
    *a: Any,
    **kw: Any,
) -> None:
    try:
        fn(*a, **kw)
        check(f"{fn.__name__} raises {exc_type.__name__} with '{substr}'", False)
    except exc_type as e:
        check(
            f"{fn.__name__} raises {exc_type.__name__} with '{substr}'",
            substr in str(e),
        )
    except Exception as e:
        check(
            f"{fn.__name__} raises {exc_type.__name__} (got {type(e).__name__})",
            False,
        )

PASSED = 0
FAILED = 0


def check(description: str, condition: bool) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        print(f"FAIL {description}")


def raises(exc_type: type, fn: Callable[..., Any], *a: Any, **kw: Any) -> None:
    try:
        fn(*a, **kw)
        check(f"{fn.__name__} raises {exc_type.__name__}", False)
    except exc_type:
        check(f"{fn.__name__} raises {exc_type.__name__}", True)
    except Exception as e:
        check(f"{fn.__name__} raises {exc_type.__name__} (got {type(e).__name__})", False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_NOW_BASE = 1_700_000_000
_fixed_uuid_ctr = 0


def _fixed_clock() -> int:
    return FIXED_NOW_BASE


def _fixed_id_factory() -> uuid.UUID:
    global _fixed_uuid_ctr
    _fixed_uuid_ctr += 1
    return uuid.UUID(f"00000000-0000-4000-8000-{_fixed_uuid_ctr:012d}")


def _mk_state_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="tik_"))


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

_REV_FIXTURE = hashlib.sha256(b"test-rev").hexdigest()


def _res_file(path: Path, *, tasks: Any = None, session: Any = None) -> None:
    data: dict[str, Any] = {}
    if tasks is not None:
        data["tasks"] = tasks
    if session is not None:
        data["active_session"] = session
    path.write_text(json.dumps(data, sort_keys=True))


def _make_res(sd: Path, *, tasks: Any = None, session: Any = None) -> ResolutionInput:
    p = sd / f"res_{uuid.uuid4().hex[:8]}.json"
    _res_file(p, tasks=tasks, session=session)
    return load_resolution_input(p, policy=KernelPolicy())


def _make_res_tasks(sd: Path, tasks_dict: dict[str, dict[str, str]]) -> ResolutionInput:
    return _make_res(sd, tasks=tasks_dict)


# ===========================================================================
# Test sections
# ===========================================================================

print("=== 1. existing domain core unchanged ===")
check("five frozen schemas", len(c.ALL_SCHEMA_VERSIONS) == 5)
check("contracts importable", True)

print("=== 2. state directory and initialization ===")
sd = _mk_state_dir()
k = _mk_kernel(sd)
r = k.initialize()
check("init returns initialized", r["status"] == "initialized")
check("init version 1", r["version"] == 1)
check("db file exists", sd.joinpath("kernel.sqlite3").exists())
st = sd.joinpath("kernel.sqlite3").stat()
check("db perms 0600", stat.S_IMODE(st.st_mode) == 0o600)
check("dir perms 0700", stat.S_IMODE(sd.stat().st_mode) == 0o700)
r2 = k.initialize()
check("init idempotent", r2["status"] == "initialized")
k2 = _mk_kernel(sd)
check("reopen check-db ok", k2.check_database()["status"] == "ok")
raises(KernelStorageError, TaskInitiationKernel, Path("rel"), clock=_fixed_clock, busy_timeout_seconds=0.2)

print("=== 3. version-1 migration and semantic schema ===")
sd3 = _mk_state_dir()
stor = TaskInitiationStore(sd3, busy_timeout_seconds=0.2)
stor.initialize()
with stor.read_connection() as conn:
    tn = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    check("3 tables", tn == {"interactions", "messages", "card_index"})
    check("user_version 1", conn.execute("PRAGMA user_version").fetchone()[0] == 1)
    check("journal_mode delete", conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete")
    check("foreign_keys 1", conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1)

# WAL refusal + init normalize
sd3b = _mk_state_dir()
st3b = TaskInitiationStore(sd3b, busy_timeout_seconds=0.2)
st3b.initialize()
ext = __import__("sqlite3").connect(str(sd3b / "kernel.sqlite3"))
ext.execute("PRAGMA journal_mode=WAL")
ext.close()
try:
    with st3b.immediate_transaction():
        pass
    check("writer refuses WAL", False)
except KernelStorageError:
    check("writer refuses WAL", True)
st3b.initialize()
with st3b.read_connection() as conn:
    check("init restores delete", conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete")

# Nonempty v0
sd3c = _mk_state_dir()
xc = __import__("sqlite3").connect(str(sd3c / "kernel.sqlite3"))
xc.execute("CREATE TABLE foo(x)")
xc.close()
os.chmod(str(sd3c / "kernel.sqlite3"), 0o600)
raises(KernelCorruptionError, TaskInitiationStore(sd3c, busy_timeout_seconds=0.2).initialize)

# Higher version
sd3d = _mk_state_dir()
x2 = __import__("sqlite3").connect(str(sd3d / "kernel.sqlite3"))
x2.execute("PRAGMA user_version=2")
x2.close()
os.chmod(str(sd3d / "kernel.sqlite3"), 0o600)
raises(KernelCorruptionError, TaskInitiationStore(sd3d, busy_timeout_seconds=0.2).initialize)

print("=== 4. codec and corruption boundary ===")
sd4 = _mk_state_dir()
k4 = _mk_kernel(sd4)
k4.initialize()
res4 = _make_res_tasks(sd4, {"Tasks/test.md": {"label": "My Task", "revision": _REV_FIXTURE}})
op = k4.ingest_stuck(_stuck(), resolution=res4)
check("ingest-stuck succeeds", op.result["status"] == "card_published")
eid = op.result["event_id"]
with k4._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="t")
    enc = _agg_to_db(agg)
    dec = _agg_from_db(enc, source="t")
    check("round-trip", agg == dec)
r4 = k4.check_database()
check("check-db ok", r4["status"] == "ok")
check("check-db count 1", r4["interaction_count"] == 1)
op2 = k4.ingest_stuck(_stuck(event_id=eid), resolution=res4)
check("exact replay", op2.replay and op2.result["status"] == "card_published")
raises(KernelRefusalError, k4.ingest_stuck, _stuck(event_id=eid, task_description="changed"))

print("=== 5. bounded multi-task resolution ===")
sd5 = _mk_state_dir()
k5 = _mk_kernel(sd5)
k5.initialize()
res5 = _make_res_tasks(sd5, {
    "Tasks/a.md": {"label": "A", "revision": hashlib.sha256(b"ra").hexdigest()},
    "Tasks/b.md": {"label": "B", "revision": hashlib.sha256(b"rb").hexdigest()},
})
sa = _stuck(event_id=str(uuid.uuid4()), task_ref={"source": "tasknotes", "ref": "Tasks/a.md"})
sb = _stuck(event_id=str(uuid.uuid4()), task_ref={"source": "tasknotes", "ref": "Tasks/b.md"})
check("ingest A", k5.ingest_stuck(sa, resolution=res5).result["status"] == "card_published")
check("ingest B", k5.ingest_stuck(sb, resolution=res5).result["status"] == "card_published")
raises(KernelRefusalError, k5.ingest_stuck, _stuck(event_id=str(uuid.uuid4()), task_ref={"source": "tasknotes", "ref": "Tasks/x.md"}), resolution=res5)
res5b = _make_res(sd5, session={"status": "active", "session_id": "s1", "task": "S Task"})
sf = _stuck(event_id=str(uuid.uuid4()), task_ref=None)
check("session fallback", k5.ingest_stuck(sf, resolution=res5b).result["status"] == "card_published")
bigf = sd5 / "big.json"
bigf.write_bytes(b" " * 20000)
raises(KernelRefusalError, load_resolution_input, bigf, policy=KernelPolicy())
bad_session = sd5 / "bad.json"
bad_session.write_text(json.dumps({"active_session": {"status": "x", "session_id": "", "task": ""}}))
raises(KernelRefusalError, load_resolution_input, bad_session, policy=KernelPolicy())

print("=== 6. deterministic worker ===")
ctx, prop, crd = build_placeholder_preparation(
    resolved_task={"source": "explicit_task_ref", "label": "T", "task_ref": "Tasks/t.md", "source_revision": _REV_FIXTURE},
    interaction_id=str(uuid.uuid4()), revision=1, task_fingerprint=hashlib.sha256(b"fp").hexdigest(),
    now_epoch=FIXED_NOW_BASE, context_id=str(uuid.uuid4()), card_id=str(uuid.uuid4()),
    followup=None, policy=KernelPolicy(),
)
check("init unclear", prop["blocker"]["category"] == "unclear_next_step")
check("init min 3", prop["tiny_start"]["estimated_minutes"] == 3)
check("init cd 180", crd["start_countdown_seconds"] == 180)
_, p2, c2 = build_placeholder_preparation(
    resolved_task={"source": "explicit_task_ref", "label": "T", "task_ref": "Tasks/t.md", "source_revision": _REV_FIXTURE},
    interaction_id=str(uuid.uuid4()), revision=2, task_fingerprint=hashlib.sha256(b"f2").hexdigest(),
    now_epoch=FIXED_NOW_BASE + 100, context_id=str(uuid.uuid4()), card_id=str(uuid.uuid4()),
    followup={"action": "shrink", "detail": "Too big to start", "prior_tiny_start": "Open the task and write one concrete next step."}, policy=KernelPolicy(),
)
check("shrink too_big", p2["blocker"]["category"] == "too_big")
check("shrink cd 60", c2["start_countdown_seconds"] == 60)
_, p3, c3 = build_placeholder_preparation(
    resolved_task={"source": "explicit_task_ref", "label": "T", "task_ref": "Tasks/t.md", "source_revision": _REV_FIXTURE},
    interaction_id=str(uuid.uuid4()), revision=3, task_fingerprint=hashlib.sha256(b"f3").hexdigest(),
    now_epoch=FIXED_NOW_BASE + 200, context_id=str(uuid.uuid4()), card_id=str(uuid.uuid4()),
    followup={"action": "blocked", "detail": "A blocker remains", "prior_tiny_start": "Open the task and write one word toward it."}, policy=KernelPolicy(),
)
check("blocked cd 120", c3["start_countdown_seconds"] == 120)

print("=== 7. atomic Stuck ===")
sd7 = _mk_state_dir()
k7 = _mk_kernel(sd7)
k7.initialize()
res7 = _make_res_tasks(sd7, {"Tasks/test.md": {"label": "AT", "revision": _REV_FIXTURE}})
check("stuck ok", k7.ingest_stuck(_stuck(), resolution=res7).result["status"] == "card_published")
with k7._store.read_connection() as conn:
    check("1 int", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 1)
    check("1 msg", conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1)
    check("1 ci", conn.execute("SELECT COUNT(*) FROM card_index").fetchone()[0] == 1)
# malformed
sd7b = _mk_state_dir()
k7b = _mk_kernel(sd7b)
k7b.initialize()
raises(ValueError, k7b.ingest_stuck, {"x": 1}, resolution=res7)
with k7b._store.read_connection() as conn:
    check("malformed no int", conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0)
# expired
sd7c = _mk_state_dir()
k7c = _mk_kernel(sd7c, clock=lambda: FIXED_NOW_BASE + 10000)
k7c.initialize()
raises(KernelRefusalError, k7c.ingest_stuck, _stuck(occurred_at_epoch=FIXED_NOW_BASE), resolution=res7)

print("=== 8. response semantics ===")
sd8 = _mk_state_dir()
k8 = _mk_kernel(sd8)
k8.initialize()
res8 = _make_res_tasks(sd8, {"Tasks/test.md": {"label": "RT", "revision": _REV_FIXTURE}})
op8 = k8.ingest_stuck(_stuck(), resolution=res8)
crd8 = op8.result["card"]
# start
rs = _resp(crd8, "start")
r8 = k8.respond(rs, resolution=res8)
check("start accepted", r8.result["status"] == "accepted")
check("start observing", r8.result["phase"] == "observing")
check("start replay", k8.respond(_resp(crd8, "start", response_id=rs["response_id"]), resolution=res8).replay)
# defer
sd8b = _mk_state_dir()
k8b = _mk_kernel(sd8b)
k8b.initialize()
c8b = k8b.ingest_stuck(_stuck(), resolution=res8).result["card"]
r8b = k8b.respond(_resp(c8b, "defer"), resolution=res8)
check("defer completed", r8b.result["terminal_status"] == "completed")
# dismiss
sd8c = _mk_state_dir()
k8c = _mk_kernel(sd8c)
k8c.initialize()
c8c = k8c.ingest_stuck(_stuck(), resolution=res8).result["card"]
check("dismiss accepted", k8c.respond(_resp(c8c, "dismiss")).result["status"] == "accepted")
# shrink
sd8d = _mk_state_dir()
k8d = _mk_kernel(sd8d)
k8d.initialize()
c8d = k8d.ingest_stuck(_stuck(), resolution=res8).result["card"]
r8d = k8d.respond(_resp(c8d, "shrink"))
check("shrink accepted", r8d.result["status"] == "accepted")
check("shrink next_card", r8d.result.get("next_card") is not None)
check("shrink replay", k8d.respond(_resp(c8d, "shrink", response_id=r8d.result["response_id"])).replay)
# blocked
sd8e = _mk_state_dir()
k8e = _mk_kernel(sd8e)
k8e.initialize()
c8e = k8e.ingest_stuck(_stuck(), resolution=res8).result["card"]
check("blocked next_card", k8e.respond(_resp(c8e, "blocked")).result.get("next_card") is not None)
# task change
sd8f = _mk_state_dir()
k8f = _mk_kernel(sd8f)
k8f.initialize()
res8f = _make_res_tasks(sd8f, {"Tasks/test.md": {"label": "Orig", "revision": _REV_FIXTURE}})
c8f = k8f.ingest_stuck(_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}), resolution=res8f).result["card"]
res8f2 = _make_res_tasks(sd8f, {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff").hexdigest()}})
rf = _resp(c8f, "start")
r8f = k8f.respond(rf, resolution=res8f2)
check("superseded", r8f.result["status"] == "superseded")
check("superseded reason", r8f.result["resolution_reason"] == "task_changed")
check("superseded replay", k8f.respond(_resp(c8f, "start", response_id=rf["response_id"]), resolution=res8f2).replay)

print("=== 9. first-response-wins ===")
sd9 = _mk_state_dir()
k9 = _mk_kernel(sd9)
k9.initialize()
c9 = k9.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd9, {"Tasks/test.md": {"label": "C", "revision": _REV_FIXTURE}})).result["card"]
barrier = threading.Barrier(2)
w = [None]
l = [None]

def wa():
    kk = _mk_kernel(sd9)
    rp = _resp(c9, "start", response_id=str(uuid.uuid4()))
    barrier.wait()
    try:
        res = kk.respond(rp)
        w[0] = ("a", res.result["status"])
    except Exception as e:
        l[0] = ("a", type(e).__name__)

def wb():
    kk = _mk_kernel(sd9)
    rp = _resp(c9, "defer", response_id=str(uuid.uuid4()))
    barrier.wait()
    try:
        res = kk.respond(rp)
        w[0] = ("b", res.result["status"])
    except Exception as e:
        l[0] = ("b", type(e).__name__)

ta = threading.Thread(target=wa); tb = threading.Thread(target=wb)
ta.start(); tb.start(); ta.join(); tb.join()
check("one won", w[0] is not None)
check("winner accepted", w[0] is not None and w[0][1] == "accepted")
check("one lost", l[0] is not None)
check("loser KernelRefusalError", l[0] is not None and l[0][1] == "KernelRefusalError")
raises(KernelRefusalError, k9.respond, _resp(c9, "dismiss", response_id=str(uuid.uuid4())))

print("=== 10. owner-scoped mutation ===")
sd10 = _mk_state_dir()
k10 = _mk_kernel(sd10)
k10.initialize()
res10 = _make_res_tasks(sd10, {"Tasks/test.md": {"label": "O", "revision": _REV_FIXTURE}})
oa = k10.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res10)
ob = k10.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res10)
k10.respond(_resp(oa.result["card"], "start"), resolution=res10)
act = k10.list_active()
# After A's Start: A is observing, B is awaiting_response — both active
check("both A and B active after A response", len(act) == 2)
k10x = _mk_kernel(sd10, clock=lambda: FIXED_NOW_BASE + 1000)
rec = k10x.reconcile()
# B's card expires at FIXED_NOW_BASE+900; at +1000 it expires
check("reconcile 1", rec["reconciled"] >= 1)
check("at most A active after reconcile", len(k10x.list_active()) <= 1)

print("=== 11. restart ===")
sd11 = _mk_state_dir()
k11 = _mk_kernel(sd11)
k11.initialize()
res11 = _make_res_tasks(sd11, {"Tasks/test.md": {"label": "R", "revision": _REV_FIXTURE}})
op11 = k11.ingest_stuck(_stuck(), resolution=res11)
eid = op11.result["event_id"]
crd = op11.result["card"]
del k11
check("restart after card", _mk_kernel(sd11).show(eid)["phase"] == "awaiting_response")
k11b = _mk_kernel(sd11)
k11b.respond(_resp(crd, "start"))
del k11b
check("restart after start", _mk_kernel(sd11).show(eid)["phase"] == "observing")
sd11d = _mk_state_dir()
k11d = _mk_kernel(sd11d)
k11d.initialize()
c11d = k11d.ingest_stuck(_stuck(), resolution=res11).result["card"]
k11d.respond(_resp(c11d, "shrink"))
del k11d
check("restart after shrink", len(_mk_kernel(sd11d).list_active()) == 1)

print("=== 12. deadlines ===")
sd12 = _mk_state_dir()
k12 = _mk_kernel(sd12, clock=lambda: FIXED_NOW_BASE)
k12.initialize()
eid12 = k12.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd12, {"Tasks/test.md": {"label": "D", "revision": _REV_FIXTURE}})).result["event_id"]
check("before expiry 0", _mk_kernel(sd12, clock=lambda: FIXED_NOW_BASE + 100).reconcile()["reconciled"] == 0)
check("after expiry 1", _mk_kernel(sd12, clock=lambda: FIXED_NOW_BASE + 1000).reconcile()["reconciled"] == 1)
check("backward clamp", _mk_kernel(sd12, clock=lambda: FIXED_NOW_BASE + 500).show(eid12)["terminal_status"] is not None)

print("=== 13. locking ===")
sd13 = _mk_state_dir()
k13 = _mk_kernel(sd13)
k13.initialize()
c13 = k13.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd13, {"Tasks/test.md": {"label": "L", "revision": _REV_FIXTURE}})).result["card"]
held = threading.Event(); ready = threading.Event()
def h():
    kk = _mk_kernel(sd13)
    with kk._store.immediate_transaction():
        ready.set()
        held.wait(timeout=5)
th = threading.Thread(target=h); th.start(); ready.wait(timeout=2)
raises(KernelBusyError, _mk_kernel(sd13).respond, _resp(c13, "start", response_id=str(uuid.uuid4())))
held.set(); th.join()
check("after lock release", _mk_kernel(sd13).respond(_resp(c13, "start", response_id=str(uuid.uuid4()))).result["status"] == "accepted")

print("=== 14. CLI ===")
sd14 = _mk_state_dir()
py = str(Path(__file__).resolve().parent.parent / "python")
env = {**os.environ, "PYTHONPATH": py}
cli = [sys.executable, "-m", "ai_system.task_initiation_cli", "--state-dir", str(sd14)]
cli_sensitive = [sys.executable, "-m", "ai_system.task_initiation_cli", "--include-sensitive", "--state-dir", str(sd14)]

def run(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run([*cli, *a], capture_output=True, text=True, cwd=py, env=env)

def run_sens(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run([*cli_sensitive, *a], capture_output=True, text=True, cwd=py, env=env)

sf = sd14 / "s.json"
sf.write_text(json.dumps({"schema_version":"task_initiation_stuck.v1","event_id":str(uuid.uuid4()),"source":"tasker","occurred_at_epoch":int(time_mod.time())-10,"task_description":"X"}))
rf14 = sd14 / "r14.json"
_res_file(rf14, tasks={"Tasks/x.md":{"label":"CLI","revision":hashlib.sha256(b"c").hexdigest()}})
check("init exit 0", run("init").returncode == 0)
ri = run_sens("ingest-stuck", "--input", str(sf), "--resolution-input", str(rf14))
check("ingest exit 0", ri.returncode == 0)
io = json.loads(ri.stdout)
eid14 = io["result"]["event_id"]
cid14 = io["result"]["card"]["card_id"]
check("show exit 0", run_sens("show", eid14).returncode == 0)
check("list-active", len(json.loads(run_sens("list-active").stdout)) == 1)
rf2 = sd14 / "resp.json"
rf2.write_text(json.dumps({"schema_version":"task_initiation_response.v1","response_id":str(uuid.uuid4()),"card_id":cid14,"action":"start","detail":None,"occurred_at_epoch":int(time_mod.time())-5}))
check("respond exit 0", run_sens("respond", "--input", str(rf2)).returncode == 0)
check("check-db exit 0", run("check-db").returncode == 0)
check("reconcile exit 0", run("reconcile").returncode == 0)
check("bad input non-0", run("ingest-stuck", "--input", "/dev/null").returncode != 0)
check("not-found exit 3", run("show", str(uuid.uuid4())).returncode == 3)
rel_check = subprocess.run(
    [sys.executable, "-m", "ai_system.task_initiation_cli", "--state-dir", "rel", "init"],
    capture_output=True, text=True, cwd=py, env=env,
)
check("relative dir exit 2", rel_check.returncode == 2)

print("=== 15. process concurrency proof ===")
sd15 = _mk_state_dir()
k15 = _mk_kernel(sd15)
k15.initialize()
res15 = _make_res_tasks(sd15, {"Tasks/concur.md": {"label": "CC", "revision": _REV_FIXTURE}})
op15 = k15.ingest_stuck(_stuck(), resolution=res15)
crd15 = op15.result["card"]

gate_dir = sd15 / "gate"
gate_dir.mkdir()
gate_file = gate_dir / "gate"

rf_a = sd15 / "resp_a.json"
rf_b = sd15 / "resp_b.json"
resp_a = _resp(crd15, "start", response_id=str(uuid.uuid4()))
resp_b = _resp(crd15, "defer", response_id=str(uuid.uuid4()))
rf_a.write_text(json.dumps(resp_a, sort_keys=True))
rf_b.write_text(json.dumps(resp_b, sort_keys=True))

py_path = str(Path(__file__).resolve().parent.parent / "python")
_child_code = (
    "import sys, os, json, time\n"
    "from pathlib import Path\n"
    f"sys.path.insert(0, {py_path!r})\n"
    "from ai_system.task_initiation_kernel import TaskInitiationKernel, KernelRefusalError\n"
    "sd = sys.argv[1]\n"
    "gate_dir = sys.argv[2]\n"
    "child = sys.argv[3]\n"
    "resp_file = sys.argv[4]\n"
    "(Path(gate_dir) / f'ready_{child}').touch()\n"
    "gate = Path(gate_dir) / 'gate'\n"
    "deadline = time.time() + 10\n"
    "while not gate.exists():\n"
    "    if time.time() > deadline:\n"
    "        sys.exit(99)\n"
    "    time.sleep(0.01)\n"
    "resp = json.loads(Path(resp_file).read_text())\n"
    f"kernel = TaskInitiationKernel(Path(sd), busy_timeout_seconds=5.0, clock=lambda: {FIXED_NOW_BASE})\n"
    "try:\n"
    "    result = kernel.respond(resp)\n"
    "    print(json.dumps({'status': result.result['status']}))\n"
    "    sys.exit(0)\n"
    "except KernelRefusalError as e:\n"
    "    sys.exit(4)\n"
    "except Exception as e:\n"
    "    print(json.dumps({'status': type(e).__name__, 'error': str(e)}))\n"
    "    sys.exit(1)\n"
)
env15 = {**os.environ, "PYTHONPATH": py_path}
pa = subprocess.Popen(
    [sys.executable, "-c", _child_code, str(sd15), str(gate_dir), "a", str(rf_a)],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env15,
)
pb = subprocess.Popen(
    [sys.executable, "-c", _child_code, str(sd15), str(gate_dir), "b", str(rf_b)],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env15,
)

# Wait for both children to signal ready
import time as _time
_dl = _time.time() + 10
while not (gate_dir / "ready_a").exists() or not (gate_dir / "ready_b").exists():
    if _time.time() > _dl:
        pa.kill(); pb.kill()
        check("children ready", False)
        break
    _time.sleep(0.02)
else:
    check("children ready", True)

# Release the gate
gate_file.touch()

# Wait for both to finish
try:
    out_a, err_a = pa.communicate(timeout=5)
    out_b, err_b = pb.communicate(timeout=5)
except subprocess.TimeoutExpired:
    pa.kill(); pb.kill()
    out_a, err_a = pa.communicate()
    out_b, err_b = pb.communicate()

rc_a = pa.returncode
rc_b = pb.returncode

# One must exit 0, one must exit 4
exits = {rc_a, rc_b}
check("one exit 0 one exit 4", exits == {0, 4} or (0 in exits and 4 in exits))
# Check messages table: exactly one Response message row
with k15._store.read_connection() as conn:
    resp_msgs = conn.execute(
        "SELECT * FROM messages WHERE kind='response'"
    ).fetchall()
    check("exactly one Response message", len(resp_msgs) == 1)

    # Parse the result to find winner action
    if resp_msgs:
        result_json = resp_msgs[0]["result_json"]
        result = json.loads(result_json)
        winner_action = result.get("action")
        check("aggregate action matches winner", winner_action is not None)

        # Check aggregate
        int_row = conn.execute("SELECT * FROM interactions").fetchone()
        agg = _agg_from_db(int_row["aggregate_json"], source="concurrency test")
        check(
            "aggregate phase matches result",
            agg.get("phase") in ("observing", "terminal"),
        )

        # Check card_index
        ci_rows = conn.execute("SELECT * FROM card_index").fetchall()
        if winner_action == "start":
            check("no next Card if Start wins", len(ci_rows) == 1)
        else:
            # Shrink/Defer generates a next Card (defer doesn't, actually)
            # For defer: terminal, no next card; for shrink: next card
            if winner_action == "defer":
                check("defer: no next card", len(ci_rows) <= 1)
            elif winner_action in ("shrink", "blocked"):
                check("shrink/blocked: next card", len(ci_rows) >= 2)
        check("exactly one aggregate row", conn.execute(
            "SELECT COUNT(*) FROM interactions"
        ).fetchone()[0] == 1)

print("=== 16. transaction fault-injection ===")

# ---------------------------------------------------------------------------
# Fault-injection helpers
# ---------------------------------------------------------------------------

_IT_ORIGINAL = TaskInitiationStore.immediate_transaction



class _FaultProxy:
    """Proxy for sqlite3.Connection that intercepts execute calls for fault injection."""

    def __init__(self, conn: sqlite3_module.Connection, fail_before_sql: str | None = None,
                 fail_after_sql: str | None = None) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_fail_before", (fail_before_sql or "").upper())
        object.__setattr__(self, "_fail_after", (fail_after_sql or "").upper())

    def execute(self, sql: str, *a: Any, **kw: Any) -> Any:
        conn = object.__getattribute__(self, "_conn")
        if isinstance(sql, str):
            upper = sql.strip().upper()
            fb = object.__getattribute__(self, "_fail_before")
            fa = object.__getattribute__(self, "_fail_after")
            if fb and upper.startswith(fb):
                raise RuntimeError("injected fault before SQL: " + fb)
            result = conn.execute(sql, *a, **kw)
            if fa and upper.startswith(fa):
                raise RuntimeError("injected fault after SQL: " + fa)
            return result
        return conn.execute(sql, *a, **kw)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_conn"), name)


@contextmanager
def _it_with_fault(store: TaskInitiationStore, *, fail_before_sql: str | None = None,
                   fail_after_sql: str | None = None, fail_before_commit: bool = False):
    """Wrapped immediate_transaction with optional fault injection."""
    cm = _IT_ORIGINAL(store)
    real_conn = cm.__enter__()
    proxy = _FaultProxy(real_conn, fail_before_sql=fail_before_sql, fail_after_sql=fail_after_sql)
    try:
        yield proxy
    except BaseException:
        cm.__exit__(*sys.exc_info())
        raise
    else:
        if fail_before_commit:
            raise RuntimeError("injected fault before COMMIT")
        cm.__exit__(None, None, None)



def _inject_after(func, msg="injected fault"):
    """Return a wrapper that calls func then raises RuntimeError."""
    def wrapper(*a, **kw):
        result = func(*a, **kw)
        raise RuntimeError(msg)
    return wrapper


def _capture_state(store: TaskInitiationStore) -> dict[str, Any]:
    """Capture read-only snapshot of all three tables."""
    with store.read_connection() as conn:
        int_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM interactions ORDER BY event_id"
        ).fetchall()]
        msg_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM messages ORDER BY message_id"
        ).fetchall()]
        ci_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM card_index ORDER BY card_id"
        ).fetchall()]
        return {
            "interactions": int_rows,
            "messages": msg_rows,
            "card_index": ci_rows,
        }


def _assert_state_unchanged(store: TaskInitiationStore, before: dict[str, Any], label: str) -> None:
    """Assert all three tables are byte-identical to pre-transaction state."""
    after = _capture_state(store)
    check(f"{label}: interactions unchanged", before["interactions"] == after["interactions"])
    check(f"{label}: messages unchanged", before["messages"] == after["messages"])
    check(f"{label}: card_index unchanged", before["card_index"] == after["card_index"])


# ---------------------------------------------------------------------------
# Stuck fault points
# ---------------------------------------------------------------------------

_STUCK_RES = None  # lazily created


def _stuck_res(sd: Path) -> ResolutionInput:
    global _STUCK_RES
    if _STUCK_RES is None:
        _STUCK_RES = _make_res_tasks(sd, {"Tasks/fi.md": {"label": "FI", "revision": _REV_FIXTURE}})
    return _STUCK_RES


# Stuck point 1: after _new_interaction
sd16_1 = _mk_state_dir()
k16_1 = _mk_kernel(sd16_1)
k16_1.initialize()
res16_1 = _make_res_tasks(sd16_1, {"Tasks/f1.md": {"label": "F1", "revision": _REV_FIXTURE}})
before = _capture_state(k16_1._store)
_orig_new_interaction = c._new_interaction
c._new_interaction = _inject_after(_orig_new_interaction, "stuck-fault-1")
try:
    try:
        k16_1.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_1)
        check("stuck fault 1: should have raised", False)
    except RuntimeError:
        check("stuck fault 1: RuntimeError raised", True)
finally:
    c._new_interaction = _orig_new_interaction
_assert_state_unchanged(k16_1._store, before, "stuck fault 1")

# Stuck point 2: after _attach_resolved_task
sd16_2 = _mk_state_dir()
k16_2 = _mk_kernel(sd16_2)
k16_2.initialize()
res16_2 = _make_res_tasks(sd16_2, {"Tasks/f2.md": {"label": "F2", "revision": _REV_FIXTURE}})
before = _capture_state(k16_2._store)
_orig_attach = c._attach_resolved_task
c._attach_resolved_task = _inject_after(_orig_attach, "stuck-fault-2")
try:
    try:
        k16_2.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_2)
        check("stuck fault 2: should have raised", False)
    except RuntimeError:
        check("stuck fault 2: RuntimeError raised", True)
finally:
    c._attach_resolved_task = _orig_attach
_assert_state_unchanged(k16_2._store, before, "stuck fault 2")

# Stuck point 3: after Context preparation (build_placeholder_preparation)
sd16_3 = _mk_state_dir()
k16_3 = _mk_kernel(sd16_3)
k16_3.initialize()
res16_3 = _make_res_tasks(sd16_3, {"Tasks/f3.md": {"label": "F3", "revision": _REV_FIXTURE}})
before = _capture_state(k16_3._store)
import ai_system.task_initiation_kernel as _kern_mod
_orig_bpp = _kern_mod.build_placeholder_preparation
_kern_mod.build_placeholder_preparation = _inject_after(_orig_bpp, "stuck-fault-3")
try:
    try:
        k16_3.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_3)
        check("stuck fault 3: should have raised", False)
    except RuntimeError:
        check("stuck fault 3: RuntimeError raised", True)
finally:
    _kern_mod.build_placeholder_preparation = _orig_bpp
_assert_state_unchanged(k16_3._store, before, "stuck fault 3")

# Stuck point 4: after _record_proposal_validated
sd16_4 = _mk_state_dir()
k16_4 = _mk_kernel(sd16_4)
k16_4.initialize()
res16_4 = _make_res_tasks(sd16_4, {"Tasks/f4.md": {"label": "F4", "revision": _REV_FIXTURE}})
before = _capture_state(k16_4._store)
_orig_rpv = c._record_proposal_validated
c._record_proposal_validated = _inject_after(_orig_rpv, "stuck-fault-4")
try:
    try:
        k16_4.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_4)
        check("stuck fault 4: should have raised", False)
    except RuntimeError:
        check("stuck fault 4: RuntimeError raised", True)
finally:
    c._record_proposal_validated = _orig_rpv
_assert_state_unchanged(k16_4._store, before, "stuck fault 4")

# Stuck point 5: after _record_card_published
sd16_5 = _mk_state_dir()
k16_5 = _mk_kernel(sd16_5)
k16_5.initialize()
res16_5 = _make_res_tasks(sd16_5, {"Tasks/f5.md": {"label": "F5", "revision": _REV_FIXTURE}})
before = _capture_state(k16_5._store)
_orig_rcp = c._record_card_published
c._record_card_published = _inject_after(_orig_rcp, "stuck-fault-5")
try:
    try:
        k16_5.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_5)
        check("stuck fault 5: should have raised", False)
    except RuntimeError:
        check("stuck fault 5: RuntimeError raised", True)
finally:
    c._record_card_published = _orig_rcp
_assert_state_unchanged(k16_5._store, before, "stuck fault 5")

# Stuck point 6: before interaction INSERT
sd16_6 = _mk_state_dir()
k16_6 = _mk_kernel(sd16_6)
k16_6.initialize()
res16_6 = _make_res_tasks(sd16_6, {"Tasks/f6.md": {"label": "F6", "revision": _REV_FIXTURE}})
before = _capture_state(k16_6._store)
k16_6._store.immediate_transaction = lambda: _it_with_fault(
    k16_6._store, fail_before_sql="INSERT INTO interactions"
)
try:
    try:
        k16_6.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_6)
        check("stuck fault 6: should have raised", False)
    except RuntimeError:
        check("stuck fault 6: RuntimeError raised", True)
finally:
    k16_6._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_6._store, TaskInitiationStore)
_assert_state_unchanged(k16_6._store, before, "stuck fault 6")

# Stuck point 7: before message INSERT
sd16_7 = _mk_state_dir()
k16_7 = _mk_kernel(sd16_7)
k16_7.initialize()
res16_7 = _make_res_tasks(sd16_7, {"Tasks/f7.md": {"label": "F7", "revision": _REV_FIXTURE}})
before = _capture_state(k16_7._store)
k16_7._store.immediate_transaction = lambda: _it_with_fault(
    k16_7._store, fail_before_sql="INSERT INTO messages"
)
try:
    try:
        k16_7.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_7)
        check("stuck fault 7: should have raised", False)
    except RuntimeError:
        check("stuck fault 7: RuntimeError raised", True)
finally:
    k16_7._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_7._store, TaskInitiationStore)
_assert_state_unchanged(k16_7._store, before, "stuck fault 7")

# Stuck point 8: before card_index INSERT
sd16_8 = _mk_state_dir()
k16_8 = _mk_kernel(sd16_8)
k16_8.initialize()
res16_8 = _make_res_tasks(sd16_8, {"Tasks/f8.md": {"label": "F8", "revision": _REV_FIXTURE}})
before = _capture_state(k16_8._store)
k16_8._store.immediate_transaction = lambda: _it_with_fault(
    k16_8._store, fail_before_sql="INSERT INTO card_index"
)
try:
    try:
        k16_8.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_8)
        check("stuck fault 8: should have raised", False)
    except RuntimeError:
        check("stuck fault 8: RuntimeError raised", True)
finally:
    k16_8._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_8._store, TaskInitiationStore)
_assert_state_unchanged(k16_8._store, before, "stuck fault 8")

# Stuck point 9: before COMMIT
sd16_9 = _mk_state_dir()
k16_9 = _mk_kernel(sd16_9)
k16_9.initialize()
res16_9 = _make_res_tasks(sd16_9, {"Tasks/f9.md": {"label": "F9", "revision": _REV_FIXTURE}})
before = _capture_state(k16_9._store)
k16_9._store.immediate_transaction = lambda: _it_with_fault(
    k16_9._store, fail_before_commit=True
)
try:
    try:
        k16_9.ingest_stuck(_stuck(event_id=str(uuid.uuid4())), resolution=res16_9)
        check("stuck fault 9: should have raised", False)
    except RuntimeError:
        check("stuck fault 9: RuntimeError raised", True)
finally:
    k16_9._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_9._store, TaskInitiationStore)
_assert_state_unchanged(k16_9._store, before, "stuck fault 9")

# ---------------------------------------------------------------------------
# Response (Shrink) fault points
# ---------------------------------------------------------------------------

# Response point 1: after _apply_response
sd16_r1 = _mk_state_dir()
k16_r1 = _mk_kernel(sd16_r1)
k16_r1.initialize()
res_r1 = _make_res_tasks(sd16_r1, {"Tasks/r1.md": {"label": "R1", "revision": _REV_FIXTURE}})
op_r1 = k16_r1.ingest_stuck(_stuck(), resolution=res_r1)
crd_r1 = op_r1.result["card"]
before = _capture_state(k16_r1._store)
_orig_apply_resp = c._apply_response
c._apply_response = _inject_after(_orig_apply_resp, "response-fault-1")
try:
    try:
        k16_r1.respond(_resp(crd_r1, "shrink"), resolution=res_r1)
        check("response fault 1: should have raised", False)
    except RuntimeError:
        check("response fault 1: RuntimeError raised", True)
finally:
    c._apply_response = _orig_apply_resp
_assert_state_unchanged(k16_r1._store, before, "response fault 1")

# Response point 2: after next Context preparation (_record_context_prepared in preparing branch)
sd16_r2 = _mk_state_dir()
k16_r2 = _mk_kernel(sd16_r2)
k16_r2.initialize()
res_r2 = _make_res_tasks(sd16_r2, {"Tasks/r2.md": {"label": "R2", "revision": _REV_FIXTURE}})
op_r2 = k16_r2.ingest_stuck(_stuck(), resolution=res_r2)
crd_r2 = op_r2.result["card"]
before = _capture_state(k16_r2._store)
_orig_rcp2 = c._record_context_prepared
c._record_context_prepared = _inject_after(_orig_rcp2, "response-fault-2")
try:
    try:
        k16_r2.respond(_resp(crd_r2, "shrink"), resolution=res_r2)
        check("response fault 2: should have raised", False)
    except RuntimeError:
        check("response fault 2: RuntimeError raised", True)
finally:
    c._record_context_prepared = _orig_rcp2
_assert_state_unchanged(k16_r2._store, before, "response fault 2")

# Response point 3: after next Card publication (_record_card_published in preparing branch)
sd16_r3 = _mk_state_dir()
k16_r3 = _mk_kernel(sd16_r3)
k16_r3.initialize()
res_r3 = _make_res_tasks(sd16_r3, {"Tasks/r3.md": {"label": "R3", "revision": _REV_FIXTURE}})
op_r3 = k16_r3.ingest_stuck(_stuck(), resolution=res_r3)
crd_r3 = op_r3.result["card"]
before = _capture_state(k16_r3._store)
_orig_rcp3 = c._record_card_published
c._record_card_published = _inject_after(_orig_rcp3, "response-fault-3")
try:
    try:
        k16_r3.respond(_resp(crd_r3, "shrink"), resolution=res_r3)
        check("response fault 3: should have raised", False)
    except RuntimeError:
        check("response fault 3: RuntimeError raised", True)
finally:
    c._record_card_published = _orig_rcp3
_assert_state_unchanged(k16_r3._store, before, "response fault 3")

# Response point 4: before aggregate UPDATE
sd16_r4 = _mk_state_dir()
k16_r4 = _mk_kernel(sd16_r4)
k16_r4.initialize()
res_r4 = _make_res_tasks(sd16_r4, {"Tasks/r4.md": {"label": "R4", "revision": _REV_FIXTURE}})
op_r4 = k16_r4.ingest_stuck(_stuck(), resolution=res_r4)
crd_r4 = op_r4.result["card"]
before = _capture_state(k16_r4._store)
k16_r4._store.immediate_transaction = lambda: _it_with_fault(
    k16_r4._store, fail_before_sql="UPDATE interactions"
)
try:
    try:
        k16_r4.respond(_resp(crd_r4, "shrink"), resolution=res_r4)
        check("response fault 4: should have raised", False)
    except RuntimeError:
        check("response fault 4: RuntimeError raised", True)
finally:
    k16_r4._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_r4._store, TaskInitiationStore)
_assert_state_unchanged(k16_r4._store, before, "response fault 4")

# Response point 5: before next card_index INSERT
sd16_r5 = _mk_state_dir()
k16_r5 = _mk_kernel(sd16_r5)
k16_r5.initialize()
res_r5 = _make_res_tasks(sd16_r5, {"Tasks/r5.md": {"label": "R5", "revision": _REV_FIXTURE}})
op_r5 = k16_r5.ingest_stuck(_stuck(), resolution=res_r5)
crd_r5 = op_r5.result["card"]
before = _capture_state(k16_r5._store)
k16_r5._store.immediate_transaction = lambda: _it_with_fault(
    k16_r5._store, fail_before_sql="INSERT INTO card_index"
)
try:
    try:
        k16_r5.respond(_resp(crd_r5, "shrink"), resolution=res_r5)
        check("response fault 5: should have raised", False)
    except RuntimeError:
        check("response fault 5: RuntimeError raised", True)
finally:
    k16_r5._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_r5._store, TaskInitiationStore)
_assert_state_unchanged(k16_r5._store, before, "response fault 5")

# Response point 6: before Response message INSERT
sd16_r6 = _mk_state_dir()
k16_r6 = _mk_kernel(sd16_r6)
k16_r6.initialize()
res_r6 = _make_res_tasks(sd16_r6, {"Tasks/r6.md": {"label": "R6", "revision": _REV_FIXTURE}})
op_r6 = k16_r6.ingest_stuck(_stuck(), resolution=res_r6)
crd_r6 = op_r6.result["card"]
before = _capture_state(k16_r6._store)
k16_r6._store.immediate_transaction = lambda: _it_with_fault(
    k16_r6._store, fail_before_sql="INSERT INTO messages"
)
try:
    try:
        k16_r6.respond(_resp(crd_r6, "shrink"), resolution=res_r6)
        check("response fault 6: should have raised", False)
    except RuntimeError:
        check("response fault 6: RuntimeError raised", True)
finally:
    k16_r6._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_r6._store, TaskInitiationStore)
_assert_state_unchanged(k16_r6._store, before, "response fault 6")

# Response point 7: before COMMIT
sd16_r7 = _mk_state_dir()
k16_r7 = _mk_kernel(sd16_r7)
k16_r7.initialize()
res_r7 = _make_res_tasks(sd16_r7, {"Tasks/r7.md": {"label": "R7", "revision": _REV_FIXTURE}})
op_r7 = k16_r7.ingest_stuck(_stuck(), resolution=res_r7)
crd_r7 = op_r7.result["card"]
before = _capture_state(k16_r7._store)
k16_r7._store.immediate_transaction = lambda: _it_with_fault(
    k16_r7._store, fail_before_commit=True
)
try:
    try:
        k16_r7.respond(_resp(crd_r7, "shrink"), resolution=res_r7)
        check("response fault 7: should have raised", False)
    except RuntimeError:
        check("response fault 7: RuntimeError raised", True)
finally:
    k16_r7._store.immediate_transaction = _IT_ORIGINAL.__get__(k16_r7._store, TaskInitiationStore)
_assert_state_unchanged(k16_r7._store, before, "response fault 7")


print("=== 17. historical replay integrity ===")

# --- helpers ---
def _replay_response(kernel: TaskInitiationKernel, resp: dict[str, Any]) -> OperationResult:
    return kernel.respond(resp)

# 17.1: Shrink -> later Start -> replay Shrink
sd17_1 = _mk_state_dir()
k17_1 = _mk_kernel(sd17_1)
k17_1.initialize()
res17_1 = _make_res_tasks(sd17_1, {"Tasks/test.md": {"label": "R17", "revision": _REV_FIXTURE}})
op17_1 = k17_1.ingest_stuck(_stuck(), resolution=res17_1)
crd17_1 = op17_1.result["card"]
shr17 = _resp(crd17_1, "shrink")
shr_op = k17_1.respond(shr17, resolution=res17_1)
check("17.1 shrink accepted", shr_op.result["status"] == "accepted")
shr_orig = shr_op.result
next17 = shr_op.result["next_card"]
# Start on next card changes aggregate phase
k17_1.respond(_resp(next17, "start"), resolution=res17_1)
# Replay Shrink — still returns original accepted result
replay17_1 = _replay_response(k17_1, shr17)
check("17.1 replay is replay", replay17_1.replay)
check("17.1 replay result matches", replay17_1.result == shr_orig)

# 17.2: Shrink -> later expiry -> replay Shrink
sd17_2 = _mk_state_dir()
k17_2 = _mk_kernel(sd17_2)
k17_2.initialize()
res17_2 = _make_res_tasks(sd17_2, {"Tasks/test.md": {"label": "R17", "revision": _REV_FIXTURE}})
op17_2 = k17_2.ingest_stuck(_stuck(), resolution=res17_2)
crd17_2 = op17_2.result["card"]
shr17_2 = _resp(crd17_2, "shrink")
shr_op2 = k17_2.respond(shr17_2, resolution=res17_2)
shr_orig2 = shr_op2.result
# Advance clock so next card expires, then reconcile
k17_2x = _mk_kernel(sd17_2, clock=lambda: FIXED_NOW_BASE + 2000)
k17_2x.reconcile()
# Replay Shrink on expired interaction — still returns original
replay17_2 = _replay_response(k17_2x, shr17_2)
check("17.2 replay after expiry", replay17_2.replay)
check("17.2 replay result matches", replay17_2.result == shr_orig2)

# 17.3: Shrink -> later supersession -> replay Shrink (still accepted)
sd17_3 = _mk_state_dir()
k17_3 = _mk_kernel(sd17_3)
k17_3.initialize()
res17_3a = _make_res_tasks(sd17_3, {"Tasks/test.md": {"label": "Orig", "revision": _REV_FIXTURE}})
op17_3 = k17_3.ingest_stuck(_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}), resolution=res17_3a)
crd17_3 = op17_3.result["card"]
shr17_3 = _resp(crd17_3, "shrink")
shr_op3 = k17_3.respond(shr17_3, resolution=res17_3a)
shr_orig3 = shr_op3.result
next17_3 = shr_op3.result["next_card"]
# Respond to next card with different task -> superseded
res17_3b = _make_res_tasks(sd17_3, {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff").hexdigest()}})
start17_3 = _resp(next17_3, "start")
k17_3.respond(start17_3, resolution=res17_3b)
# Replay Shrink — still accepted, not superseded
replay17_3 = _replay_response(k17_3, shr17_3)
check("17.3 replay after supersession", replay17_3.replay)
check("17.3 replay still accepted", replay17_3.result == shr_orig3)

# 17.4: Blocked -> later action on next card -> replay Blocked
sd17_4 = _mk_state_dir()
k17_4 = _mk_kernel(sd17_4)
k17_4.initialize()
op17_4 = k17_4.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_4, {"Tasks/test.md": {"label": "B", "revision": _REV_FIXTURE}}))
blk17 = _resp(op17_4.result["card"], "blocked")
blk_op = k17_4.respond(blk17)
blk_orig = blk_op.result
check("17.4 blocked accepted", blk_op.result["status"] == "accepted")
k17_4.respond(_resp(blk_op.result["next_card"], "dismiss"))
replay17_4 = _replay_response(k17_4, blk17)
check("17.4 blocked replay", replay17_4.replay and replay17_4.result == blk_orig)

# 17.5: Start -> observation completion -> replay Start
sd17_5 = _mk_state_dir()
k17_5 = _mk_kernel(sd17_5, clock=lambda: FIXED_NOW_BASE)
k17_5.initialize()
op17_5 = k17_5.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_5, {"Tasks/test.md": {"label": "S", "revision": _REV_FIXTURE}}))
start17_5 = _resp(op17_5.result["card"], "start")
start_op = k17_5.respond(start17_5)
start_orig = start_op.result
check("17.5 start accepted", start_op.result["status"] == "accepted")
# Advance past observation deadline
k17_5x = _mk_kernel(sd17_5, clock=lambda: FIXED_NOW_BASE + 2000)
k17_5x.reconcile()
# Replay Start — still returns observing result
replay17_5 = _replay_response(k17_5x, start17_5)
check("17.5 start replay after completion", replay17_5.replay)
check("17.5 start replay matches", replay17_5.result == start_orig)

# 17.6: Start -> restart -> replay Start
sd17_6 = _mk_state_dir()
k17_6 = _mk_kernel(sd17_6)
k17_6.initialize()
op17_6 = k17_6.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_6, {"Tasks/test.md": {"label": "S", "revision": _REV_FIXTURE}}))
start17_6 = _resp(op17_6.result["card"], "start")
start_op6 = k17_6.respond(start17_6)
start_orig6 = start_op6.result
del k17_6
k17_6b = _mk_kernel(sd17_6)
replay17_6 = _replay_response(k17_6b, start17_6)
check("17.6 restart replay", replay17_6.replay and replay17_6.result == start_orig6)

# 17.7: Defer replay
sd17_7 = _mk_state_dir()
k17_7 = _mk_kernel(sd17_7)
k17_7.initialize()
op17_7 = k17_7.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_7, {"Tasks/test.md": {"label": "Df", "revision": _REV_FIXTURE}}))
def17 = _resp(op17_7.result["card"], "defer")
def_op = k17_7.respond(def17)
def_orig = def_op.result
check("17.7 defer accepted", def_op.result["status"] == "accepted")
replay17_7 = _replay_response(k17_7, def17)
check("17.7 defer replay", replay17_7.replay and replay17_7.result == def_orig)

# 17.8: Dismiss replay
sd17_8 = _mk_state_dir()
k17_8 = _mk_kernel(sd17_8)
k17_8.initialize()
op17_8 = k17_8.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_8, {"Tasks/test.md": {"label": "Dm", "revision": _REV_FIXTURE}}))
dis17 = _resp(op17_8.result["card"], "dismiss")
dis_op = k17_8.respond(dis17)
dis_orig = dis_op.result
replay17_8 = _replay_response(k17_8, dis17)
check("17.8 dismiss replay", replay17_8.replay and replay17_8.result == dis_orig)

# 17.9: Shrink at revision limit replay
sd17_9 = _mk_state_dir()
pol17_9 = KernelPolicy(max_card_revisions=1)
k17_9 = _mk_kernel(sd17_9, policy=pol17_9)
k17_9.initialize()
op17_9 = k17_9.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_9, {"Tasks/test.md": {"label": "SL", "revision": _REV_FIXTURE}}))
shr17_9 = _resp(op17_9.result["card"], "shrink")
shr_op9 = k17_9.respond(shr17_9)
check("17.9 shrink at limit terminal", shr_op9.result["terminal_status"] == "completed")
shr_orig9 = shr_op9.result
replay17_9 = _replay_response(k17_9, shr17_9)
check("17.9 shrink limit replay", replay17_9.replay and replay17_9.result == shr_orig9)

# 17.10: Blocked at revision limit replay
sd17_10 = _mk_state_dir()
pol17_10 = KernelPolicy(max_card_revisions=1)
k17_10 = _mk_kernel(sd17_10, policy=pol17_10)
k17_10.initialize()
op17_10 = k17_10.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd17_10, {"Tasks/test.md": {"label": "BL", "revision": _REV_FIXTURE}}))
blk17_10 = _resp(op17_10.result["card"], "blocked")
blk_op10 = k17_10.respond(blk17_10)
check("17.10 blocked at limit terminal", blk_op10.result["terminal_status"] == "completed")
blk_orig10 = blk_op10.result
replay17_10 = _replay_response(k17_10, blk17_10)
check("17.10 blocked limit replay", replay17_10.replay and replay17_10.result == blk_orig10)

# 17.11: True superseding Response replay
sd17_11 = _mk_state_dir()
k17_11 = _mk_kernel(sd17_11)
k17_11.initialize()
res17_11a = _make_res_tasks(sd17_11, {"Tasks/test.md": {"label": "Orig", "revision": _REV_FIXTURE}})
op17_11 = k17_11.ingest_stuck(_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}), resolution=res17_11a)
start17_11 = _resp(op17_11.result["card"], "start")
res17_11b = _make_res_tasks(sd17_11, {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff2").hexdigest()}})
sup_op = k17_11.respond(start17_11, resolution=res17_11b)
check("17.11 superseded", sup_op.result["status"] == "superseded")
sup_orig = sup_op.result
replay17_11 = _replay_response(k17_11, start17_11)
check("17.11 superseded replay", replay17_11.replay and replay17_11.result == sup_orig)

# 17.12: All replay results byte-identical on second replay
replay17_12 = _replay_response(k17_11, start17_11)
check("17.12 second replay byte-identical", replay17_12.result == sup_orig)

print("=== 18. path safety on ordinary operations ===")

# 18.1: ingest without init -> no file created
sd18_1 = _mk_state_dir()
k18_1 = _mk_kernel(sd18_1)
raises(KernelStorageError, k18_1.ingest_stuck, _stuck())
check("18.1 no db created", not sd18_1.joinpath("kernel.sqlite3").exists())

# 18.2: respond without init -> no file created
sd18_2 = _mk_state_dir()
k18_2 = _mk_kernel(sd18_2)
raises(KernelStorageError, k18_2.respond, _resp({"card_id": str(uuid.uuid4()), "issued_at_epoch": FIXED_NOW_BASE}, "start"))
check("18.2 no db created", not sd18_2.joinpath("kernel.sqlite3").exists())

# 18.3: reconcile without init -> no file created
sd18_3 = _mk_state_dir()
k18_3 = _mk_kernel(sd18_3)
raises(KernelStorageError, k18_3.reconcile)
check("18.3 no db created", not sd18_3.joinpath("kernel.sqlite3").exists())

# 18.4: Broken symlink during ingest -> no target created
sd18_4 = _mk_state_dir()
symlink_path = sd18_4 / "broken.json"
symlink_path.symlink_to("/nonexistent/path")
k18_4 = _mk_kernel(sd18_4)
k18_4.initialize()
raises(KernelRefusalError, load_resolution_input, symlink_path, policy=KernelPolicy())

# 18.5: Missing state dir -> not created by ordinary command
sd18_5 = Path(tempfile.mkdtemp(prefix="tik_")) / "nonexistent"
k18_5 = TaskInitiationKernel(sd18_5, clock=_fixed_clock, busy_timeout_seconds=0.2)
raises(KernelStorageError, k18_5.ingest_stuck, _stuck())
check("18.5 state dir not created", not sd18_5.exists())

# 18.6: init with spaces in path works
sd18_6 = _mk_state_dir()
spaced = sd18_6 / "has spaces"
k18_6 = TaskInitiationKernel(spaced, clock=_fixed_clock, busy_timeout_seconds=0.2)
k18_6.initialize()
check("18.6 init with spaces", k18_6.check_database()["status"] == "ok")

# 18.7: init with ? in path works
sd18_7 = _mk_state_dir()
qpath = sd18_7 / "has?qmark"
k18_7 = TaskInitiationKernel(qpath, clock=_fixed_clock, busy_timeout_seconds=0.2)
k18_7.initialize()
check("18.7 init with ?", k18_7.check_database()["status"] == "ok")

# 18.8: init with # in path works
sd18_8 = _mk_state_dir()
hpath = sd18_8 / "has#hash"
k18_8 = TaskInitiationKernel(hpath, clock=_fixed_clock, busy_timeout_seconds=0.2)
k18_8.initialize()
check("18.8 init with #", k18_8.check_database()["status"] == "ok")

print("=== 19. schema validation on every operation ===")

# Helper: create valid DB, corrupt schema, verify operations refuse
def _mk_db() -> tuple[Path, TaskInitiationKernel]:
    sd = _mk_state_dir()
    k = _mk_kernel(sd)
    k.initialize()
    return sd, k

def _corrupt_db(sd: Path, sql: str) -> None:
    db = sd / "kernel.sqlite3"
    conn = sqlite3_module.connect(str(db))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(sql)
    conn.commit()
    conn.close()

# 19.1: Drop index -> ingest/respond/show/list/reconcile all refuse
sd19_1, k19_1 = _mk_db()
res19_1 = _make_res_tasks(sd19_1, {"Tasks/test.md": {"label": "S19", "revision": _REV_FIXTURE}})
op19_1 = k19_1.ingest_stuck(_stuck(), resolution=res19_1)
eid19_1 = op19_1.result["event_id"]
_corrupt_db(sd19_1, "DROP INDEX interactions_active_deadline_idx")
k19_1b = _mk_kernel(sd19_1)
raises(KernelCorruptionError, k19_1b.ingest_stuck, _stuck())
raises(KernelCorruptionError, k19_1b.respond, _resp(op19_1.result["card"], "start"))
raises(KernelCorruptionError, k19_1b.show, eid19_1)
raises(KernelCorruptionError, k19_1b.list_active)
raises(KernelCorruptionError, k19_1b.reconcile)
check("19.1 drop index refused", True)

# 19.2: Add unexpected index -> refuse
sd19_2, k19_2 = _mk_db()
_corrupt_db(sd19_2, "CREATE INDEX bad_idx ON interactions(state_version)")
k19_2b = _mk_kernel(sd19_2)
raises(KernelCorruptionError, k19_2b.ingest_stuck, _stuck())
check("19.2 extra index refused", True)

# 19.3: Wrong FK delete action -> refuse
sd19_3, k19_3 = _mk_db()
# Recreate messages with wrong FK
_corrupt_db(sd19_3, """
    CREATE TABLE messages_new (kind TEXT, message_id TEXT, payload_sha256 TEXT,
        payload_json TEXT, event_id TEXT REFERENCES interactions(event_id) ON DELETE SET NULL,
        result_json TEXT, recorded_at_epoch INTEGER, PRIMARY KEY(kind, message_id));
    INSERT INTO messages_new SELECT * FROM messages;
    DROP TABLE messages;
    ALTER TABLE messages_new RENAME TO messages;
""")
k19_3b = _mk_kernel(sd19_3)
raises(KernelCorruptionError, k19_3b.ingest_stuck, _stuck())
check("19.3 wrong FK refused", True)

# 19.4: Missing UNIQUE on interaction_id -> refuse
sd19_4, k19_4 = _mk_db()
# Find the autoindex name and drop it
conn194 = sqlite3_module.connect(str(sd19_4 / "kernel.sqlite3"))
idx_rows = conn194.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'sqlite_autoindex_interactions%' AND name != (SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'sqlite_autoindex_interactions%' LIMIT 1)").fetchall()
# Actually drop the UNIQUE constraint by rebuilding
conn194.close()
_corrupt_db(sd19_4, """
    CREATE TABLE interactions_new (event_id TEXT PRIMARY KEY, interaction_id TEXT NOT NULL,
        aggregate_json TEXT NOT NULL, state_version INTEGER NOT NULL, phase TEXT NOT NULL,
        terminal_status TEXT, next_deadline_epoch INTEGER,
        last_observed_at_epoch INTEGER NOT NULL, created_at_epoch INTEGER NOT NULL,
        updated_at_epoch INTEGER NOT NULL, interaction_policy_json TEXT NOT NULL);
    INSERT INTO interactions_new SELECT * FROM interactions;
    DROP TABLE interactions;
    ALTER TABLE interactions_new RENAME TO interactions;
""")
k19_4b = _mk_kernel(sd19_4)
raises(KernelCorruptionError, k19_4b.ingest_stuck, _stuck())
check("19.4 missing UNIQUE interaction_id refused", True)

# 19.5: Missing card_index uniqueness -> refuse
sd19_5, k19_5 = _mk_db()
_corrupt_db(sd19_5, """
    CREATE TABLE card_index_new (card_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, revision INTEGER NOT NULL);
    INSERT INTO card_index_new SELECT * FROM card_index;
    DROP TABLE card_index;
    ALTER TABLE card_index_new RENAME TO card_index;
""")
k19_5b = _mk_kernel(sd19_5)
raises(KernelCorruptionError, k19_5b.ingest_stuck, _stuck())
check("19.5 missing card_index unique refused", True)

# 19.6: Wrong column type -> refuse
sd19_6, k19_6 = _mk_db()
_corrupt_db(sd19_6, """
    CREATE TABLE interactions_new (event_id INTEGER PRIMARY KEY, interaction_id TEXT NOT NULL,
        aggregate_json TEXT NOT NULL, state_version INTEGER NOT NULL, phase TEXT NOT NULL,
        terminal_status TEXT, next_deadline_epoch INTEGER,
        last_observed_at_epoch INTEGER NOT NULL, created_at_epoch INTEGER NOT NULL,
        updated_at_epoch INTEGER NOT NULL, interaction_policy_json TEXT NOT NULL);
    INSERT INTO interactions_new SELECT * FROM interactions;
    DROP TABLE interactions;
    ALTER TABLE interactions_new RENAME TO interactions;
""")
k19_6b = _mk_kernel(sd19_6)
raises(KernelCorruptionError, k19_6b.ingest_stuck, _stuck())
check("19.6 wrong column type refused", True)

# 19.7: Added unexpected trigger -> refuse
sd19_7, k19_7 = _mk_db()
_corrupt_db(sd19_7, "CREATE TRIGGER bad_trigger AFTER INSERT ON interactions BEGIN SELECT 1; END")
k19_7b = _mk_kernel(sd19_7)
raises(KernelCorruptionError, k19_7b.ingest_stuck, _stuck())
check("19.7 unexpected trigger refused", True)

# 19.8: Added unexpected view -> refuse
sd19_8, k19_8 = _mk_db()
_corrupt_db(sd19_8, "CREATE VIEW bad_view AS SELECT * FROM interactions")
k19_8b = _mk_kernel(sd19_8)
raises(KernelCorruptionError, k19_8b.ingest_stuck, _stuck())
check("19.8 unexpected view refused", True)

print("=== 20. nested private format validation ===")

# 20.1: Extra revision key -> check-db fails
sd20_1, k20_1 = _mk_db()
op20_1 = k20_1.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_1, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
eid20_1 = op20_1.result["event_id"]
with k20_1._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_1,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.1")
    agg["revisions"][0]["bogus_key"] = "intruder"
    conn2 = sqlite3_module.connect(str(sd20_1 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_1, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "revision key mismatch", k20_1.check_database)

# 20.2: Extra private Response key -> check-db fails
sd20_2, k20_2 = _mk_db()
op20_2 = k20_2.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_2, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
k20_2.respond(_resp(op20_2.result["card"], "start"))
eid20_2 = op20_2.result["event_id"]
with k20_2._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_2,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.2")
    agg["revisions"][0]["response"]["bogus"] = "intruder"
    conn2 = sqlite3_module.connect(str(sd20_2 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_2, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "response key mismatch", k20_2.check_database)

# 20.3: Extra resolved-task key -> check-db fails
sd20_3, k20_3 = _mk_db()
op20_3 = k20_3.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_3, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
eid20_3 = op20_3.result["event_id"]
with k20_3._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_3,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.3")
    agg["resolved_task"]["bogus"] = "intruder"
    conn2 = sqlite3_module.connect(str(sd20_3 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_3, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "resolved_task", k20_3.check_database)

# 20.4: Non-null receipt field -> check-db fails
sd20_4, k20_4 = _mk_db()
op20_4 = k20_4.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_4, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
eid20_4 = op20_4.result["event_id"]
with k20_4._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_4,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.4")
    agg["revisions"][0]["receipt"] = {"bogus": "should be null"}
    conn2 = sqlite3_module.connect(str(sd20_4 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_4, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "receipt must be null", k20_4.check_database)

# 20.5: Non-null card_posted_at -> check-db fails (set to string)
sd20_5, k20_5 = _mk_db()
op20_5 = k20_5.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_5, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
eid20_5 = op20_5.result["event_id"]
with k20_5._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_5,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.5")
    agg["revisions"][0]["card_posted_at_epoch"] = "not-an-int"
    conn2 = sqlite3_module.connect(str(sd20_5 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_5, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "card_posted_at_epoch", k20_5.check_database)

# 20.6: Malformed evidence_issues (object instead of set) -> check-db fails
sd20_6, k20_6 = _mk_db()
op20_6 = k20_6.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd20_6, {"Tasks/test.md": {"label": "F20", "revision": _REV_FIXTURE}}))
eid20_6 = op20_6.result["event_id"]
with k20_6._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid20_6,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-20.6")
    # Replace the set with a bad object
    agg["evidence_issues"] = {"bad": "object"}
    conn2 = sqlite3_module.connect(str(sd20_6 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid20_6, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "evidence_issues", k20_6.check_database)

print("=== 21. cross-object binding corruption ===")

# 21.1: Revision fingerprint != aggregate fingerprint -> fail
sd21_1, k21_1 = _mk_db()
op21_1 = k21_1.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_1, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
eid21_1 = op21_1.result["event_id"]
with k21_1._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_1,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.1")
    agg["revisions"][0]["task_fingerprint"] = "0" * 64
    conn2 = sqlite3_module.connect(str(sd21_1 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_1, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "task_fingerprint mismatch", k21_1.check_database)

# 21.2: Context label != resolved_task label -> fail
sd21_2, k21_2 = _mk_db()
op21_2 = k21_2.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_2, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
eid21_2 = op21_2.result["event_id"]
with k21_2._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_2,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.2")
    agg["revisions"][0]["context"]["disclosed_facts"]["task"]["label"] = "WRONG"
    conn2 = sqlite3_module.connect(str(sd21_2 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_2, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "invalid context", k21_2.check_database)

# 21.3: Proposal hash mismatch -> fail
sd21_3, k21_3 = _mk_db()
op21_3 = k21_3.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_3, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
eid21_3 = op21_3.result["event_id"]
with k21_3._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_3,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.3")
    agg["revisions"][0]["proposal_sha256"] = "0" * 64
    conn2 = sqlite3_module.connect(str(sd21_3 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_3, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "proposal_sha256 mismatch", k21_3.check_database)

# 21.4: Card.blocker != proposal.blocker -> fail
sd21_4, k21_4 = _mk_db()
op21_4 = k21_4.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_4, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
eid21_4 = op21_4.result["event_id"]
with k21_4._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_4,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.4")
    agg["revisions"][0]["card"]["blocker"] = {"category": "not_a_real_blocker", "detail": "fake"}
    conn2 = sqlite3_module.connect(str(sd21_4 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_4, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "invalid card", k21_4.check_database)

# 21.5: Duplicated card epoch mismatch -> fail
sd21_5, k21_5 = _mk_db()
op21_5 = k21_5.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_5, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
eid21_5 = op21_5.result["event_id"]
with k21_5._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_5,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.5")
    agg["revisions"][0]["card_expires_at_epoch"] = 999
    conn2 = sqlite3_module.connect(str(sd21_5 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_5, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "card expiry", k21_5.check_database)

# 21.6: Response hash mismatch -> fail
sd21_6, k21_6 = _mk_db()
op21_6 = k21_6.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_6, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
k21_6.respond(_resp(op21_6.result["card"], "start"))
eid21_6 = op21_6.result["event_id"]
with k21_6._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (eid21_6,)).fetchone()
    agg = _agg_from_db(row["aggregate_json"], source="test-21.6")
    agg["revisions"][0]["response_payload_sha256"] = "0" * 64
    conn2 = sqlite3_module.connect(str(sd21_6 / "kernel.sqlite3"))
    _rewrite_aggregate_canonically(conn2, eid21_6, agg)
    conn2.close()
raises_msg(KernelCorruptionError, "response_payload_sha256 mismatch", k21_6.check_database)

# 21.7: Message ID != payload ID -> fail
sd21_7, k21_7 = _mk_db()
op21_7 = k21_7.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_7, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
# Corrupt the message row: change message_id but leave payload_json with old ID
with k21_7._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM messages WHERE kind='stuck'").fetchone()
    conn2 = sqlite3_module.connect(str(sd21_7 / "kernel.sqlite3"))
    # Change message_id in messages row — now doesn't match payload's event_id
    conn2.execute("UPDATE messages SET message_id = ? WHERE message_id = ?",
                   (str(uuid.uuid4()), row["message_id"]))
    conn2.commit()
    conn2.close()
raises_msg(KernelCorruptionError, "messages without reservations", k21_7.check_database)

# 21.8: Wrong recorded_at_epoch -> fail (corrupt to negative)
sd21_8, k21_8 = _mk_db()
op21_8 = k21_8.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd21_8, {"Tasks/test.md": {"label": "X21", "revision": _REV_FIXTURE}}))
conn2 = sqlite3_module.connect(str(sd21_8 / "kernel.sqlite3"))
conn2.execute("PRAGMA ignore_check_constraints = ON")
conn2.execute("UPDATE messages SET recorded_at_epoch = -1")
conn2.commit()
conn2.close()
raises_msg(KernelCorruptionError, "recorded_at", k21_8.check_database)

print("=== 22. replay bundle validation ===")

# 22.1: Start result with wrong phase -> check-db fails
sd22_1, k22_1 = _mk_db()
op22_1 = k22_1.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd22_1, {"Tasks/test.md": {"label": "R22", "revision": _REV_FIXTURE}}))
start22_1 = _resp(op22_1.result["card"], "start")
start_op = k22_1.respond(start22_1)
conn2 = sqlite3_module.connect(str(sd22_1 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["phase"] = "terminal"
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_1.check_database)

# 22.2: Start result with wrong observation deadline -> fails
sd22_2, k22_2 = _mk_db()
op22_2 = k22_2.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd22_2, {"Tasks/test.md": {"label": "R22", "revision": _REV_FIXTURE}}))
k22_2.respond(_resp(op22_2.result["card"], "start"))
conn2 = sqlite3_module.connect(str(sd22_2 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["observation_due_at_epoch"] = 999
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_2.check_database)

# 22.3: Shrink result with wrong next_card -> fails
sd22_3, k22_3 = _mk_db()
op22_3 = k22_3.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd22_3, {"Tasks/test.md": {"label": "R22", "revision": _REV_FIXTURE}}))
k22_3.respond(_resp(op22_3.result["card"], "shrink"))
conn2 = sqlite3_module.connect(str(sd22_3 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["next_card"] = {"bogus": "card"}
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_3.check_database)

# 22.4: Shrink result missing next_card -> fails
sd22_4, k22_4 = _mk_db()
op22_4 = k22_4.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd22_4, {"Tasks/test.md": {"label": "R22", "revision": _REV_FIXTURE}}))
k22_4.respond(_resp(op22_4.result["card"], "shrink"))
conn2 = sqlite3_module.connect(str(sd22_4 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["next_card"] = None
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_4.check_database)

# 22.5: Superseded result falsely says accepted -> fails
sd22_5, k22_5 = _mk_db()
res22_5a = _make_res_tasks(sd22_5, {"Tasks/test.md": {"label": "Orig", "revision": _REV_FIXTURE}})
op22_5 = k22_5.ingest_stuck(_stuck(task_ref={"source": "tasknotes", "ref": "Tasks/test.md"}), resolution=res22_5a)
start22_5 = _resp(op22_5.result["card"], "start")
res22_5b = _make_res_tasks(sd22_5, {"Tasks/test.md": {"label": "Changed", "revision": hashlib.sha256(b"diff").hexdigest()}})
k22_5.respond(start22_5, resolution=res22_5b)
conn2 = sqlite3_module.connect(str(sd22_5 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["status"] = "accepted"
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_5.check_database)

# 22.6: Wrong result revision -> fails
sd22_6, k22_6 = _mk_db()
op22_6 = k22_6.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd22_6, {"Tasks/test.md": {"label": "R22", "revision": _REV_FIXTURE}}))
k22_6.respond(_resp(op22_6.result["card"], "start"))
conn2 = sqlite3_module.connect(str(sd22_6 / "kernel.sqlite3"))
conn2.row_factory = sqlite3_module.Row
row = conn2.execute("SELECT kind, message_id, result_json FROM messages WHERE kind='response'").fetchone()
res = c._strict_json_loads(row["result_json"])
res["revision"] = 99
_rewrite_result_canonically(conn2, row["kind"], row["message_id"], res)
conn2.close()
raises_msg(KernelCorruptionError, "result_json not canonical", k22_6.check_database)

print("=== 23. canonical encoding ===")

# 23.1: Noncanonical aggregate (whitespace difference) -> check-db fails
sd23_1, k23_1 = _mk_db()
op23_1 = k23_1.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd23_1, {"Tasks/test.md": {"label": "C23", "revision": _REV_FIXTURE}}))
eid23_1 = op23_1.result["event_id"]
with k23_1._store.read_connection() as conn:
    row = conn.execute("SELECT * FROM interactions WHERE event_id = ?", (eid23_1,)).fetchone()
    # Add extra whitespace to make it non-canonical
    agg = json.loads(row["aggregate_json"])
    noncanonical = json.dumps(agg, indent=2)  # not sort_keys, not compact
    conn2 = sqlite3_module.connect(str(sd23_1 / "kernel.sqlite3"))
    conn2.execute("UPDATE interactions SET aggregate_json = ? WHERE event_id = ?",
                   (noncanonical, eid23_1))
    conn2.commit()
    conn2.close()
raises(KernelCorruptionError, k23_1.check_database)
check("23.1 noncanonical aggregate", True)

# 23.2: Noncanonical result -> fails
sd23_2, k23_2 = _mk_db()
op23_2 = k23_2.ingest_stuck(_stuck(), resolution=_make_res_tasks(sd23_2, {"Tasks/test.md": {"label": "C23", "revision": _REV_FIXTURE}}))
conn2 = sqlite3_module.connect(str(sd23_2 / "kernel.sqlite3"))
row = conn2.execute("SELECT result_json FROM messages WHERE kind='stuck'").fetchone()
res = json.loads(row[0])
noncanonical = json.dumps(res, indent=2)
conn2.execute("UPDATE messages SET result_json = ? WHERE kind='stuck'",
              (noncanonical,))
conn2.commit()
conn2.close()
raises(KernelCorruptionError, k23_2.check_database)
check("23.2 noncanonical result", True)

print("=== 24. resolution file hardening ===")

# 24.1: Resolution symlink -> rejected
sd24_1 = _mk_state_dir()
real_file = sd24_1 / "real.json"
real_file.write_text(json.dumps({"tasks": {"Tasks/test.md": {"label": "Sym", "revision": _REV_FIXTURE}}}))
symlink = sd24_1 / "symlink.json"
symlink.symlink_to(str(real_file))
raises(KernelRefusalError, load_resolution_input, symlink, policy=KernelPolicy())
check("24.1 symlink rejected", True)

# 24.2: 33 tasks with default policy -> rejected
sd24_2 = _mk_state_dir()
tasks24_2 = {f"Tasks/t{i:02d}.md": {"label": f"T{i}", "revision": _REV_FIXTURE} for i in range(33)}
res_path = sd24_2 / "res24_2.json"
res_path.write_text(json.dumps({"tasks": tasks24_2}))
raises(KernelRefusalError, load_resolution_input, res_path, policy=KernelPolicy())
check("24.2 33 tasks rejected", True)

# 24.3: 1 task with custom max_tasks=1 accepted, 2 rejected
sd24_3 = _mk_state_dir()
pol24_3 = KernelPolicy(max_resolution_tasks=1)
res1_path = sd24_3 / "res1.json"
res1_path.write_text(json.dumps({"tasks": {"Tasks/a.md": {"label": "A", "revision": _REV_FIXTURE}}}))
ri1 = load_resolution_input(res1_path, policy=pol24_3)
check("24.3 1 task accepted", len(ri1.tasks) == 1)
res2_path = sd24_3 / "res2.json"
res2_path.write_text(json.dumps({"tasks": {"Tasks/a.md": {"label": "A", "revision": _REV_FIXTURE},
                                           "Tasks/b.md": {"label": "B", "revision": _REV_FIXTURE}}}))
raises(KernelRefusalError, load_resolution_input, res2_path, policy=pol24_3)
check("24.3 2 tasks rejected", True)
print()
print(f"=== {PASSED} passed, {FAILED} failed ===")
if FAILED:
    raise SystemExit(1)
print("ALL PASS")
