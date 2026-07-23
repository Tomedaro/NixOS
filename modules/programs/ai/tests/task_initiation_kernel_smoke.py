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
import sys
import tempfile
import threading
import time as time_mod
import uuid
from pathlib import Path
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
        clock=kw.get("clock", _fixed_clock),
        id_factory=kw.get("id_factory", _fixed_id_factory),
        busy_timeout_seconds=kw.get("busy_timeout_seconds", 0.2),
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
        "detail": None,
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
    return load_resolution_input(p)


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
raises(KernelCorruptionError, TaskInitiationStore(sd3c, busy_timeout_seconds=0.2).initialize)

# Higher version
sd3d = _mk_state_dir()
x2 = __import__("sqlite3").connect(str(sd3d / "kernel.sqlite3"))
x2.execute("PRAGMA user_version=2")
x2.close()
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
raises(KernelRefusalError, load_resolution_input, bigf, max_bytes=16384)
bad_session = sd5 / "bad.json"
bad_session.write_text(json.dumps({"active_session": {"status": "x", "session_id": "", "task": ""}}))
raises(KernelRefusalError, load_resolution_input, bad_session)

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
    followup={"action": "shrink"}, policy=KernelPolicy(),
)
check("shrink too_big", p2["blocker"]["category"] == "too_big")
check("shrink cd 60", c2["start_countdown_seconds"] == 60)
_, p3, c3 = build_placeholder_preparation(
    resolved_task={"source": "explicit_task_ref", "label": "T", "task_ref": "Tasks/t.md", "source_revision": _REV_FIXTURE},
    interaction_id=str(uuid.uuid4()), revision=3, task_fingerprint=hashlib.sha256(b"f3").hexdigest(),
    now_epoch=FIXED_NOW_BASE + 200, context_id=str(uuid.uuid4()), card_id=str(uuid.uuid4()),
    followup={"action": "blocked"}, policy=KernelPolicy(),
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

print()
print(f"=== {PASSED} passed, {FAILED} failed ===")
if FAILED:
    raise SystemExit(1)
print("ALL PASS")
