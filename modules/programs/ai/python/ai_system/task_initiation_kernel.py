"""Synchronous deterministic task-initiation lifecycle kernel.

Owns: atomic Stuck/Response flows, deterministic no-model worker,
owner-only reconciliation, and fixture-free all-row deadline advancement.

No transport, model, daemon, or task execution.
"""

from __future__ import annotations

import hashlib
import json
import re as _re
import sqlite3 as sqlite3_module
import time as time_mod
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai_system import task_initiation_contracts as c
from ai_system.task_initiation_store import (
    KernelBusyError,
    KernelCorruptionError,
    KernelNotFoundError,
    KernelRefusalError,
    KernelStorageError,
    TaskInitiationStore,
    _agg_from_db,
    _agg_to_db,
    _canonical_json,
    _convert_evidence_issues,
    _payload_sha256,
)

# ---------------------------------------------------------------------------
Clock = Callable[[], int]
IdFactory = Callable[[], uuid.UUID]


@dataclass(frozen=True)
class KernelPolicy:
    stuck_ttl_seconds: int = 7200
    max_future_skew_seconds: int = 300
    max_card_revisions: int = 3
    start_countdown_seconds_cap: int = 600
    observation_seconds: int = 600
    context_ttl_seconds: int = 300
    card_ttl_seconds: int = 900
    max_resolution_tasks: int = 32
    max_input_bytes: int = 65536
    max_resolution_bytes: int = 16384

    def reducer_policy(self) -> dict[str, int]:
        return {
            "max_card_revisions": self.max_card_revisions,
            "start_countdown_seconds_cap": self.start_countdown_seconds_cap,
            "observation_seconds": self.observation_seconds,
            "context_ttl_seconds": self.context_ttl_seconds,
            "card_ttl_seconds": self.card_ttl_seconds,
            "stuck_ttl_seconds": self.stuck_ttl_seconds,
            "max_future_skew_seconds": self.max_future_skew_seconds,
        }


@dataclass(frozen=True)
class ResolutionInput:
    tasks: Mapping[str, Mapping[str, str]]
    active_session: Mapping[str, str] | None


@dataclass(frozen=True)
class OperationResult:
    result: dict[str, Any]
    replay: bool


# ---------------------------------------------------------------------------
# Resolution fixture helpers
# ---------------------------------------------------------------------------

_TASK_REF_RE = _re.compile(r"^Tasks(/[\w ._@+%!-]+)+\.md$")
_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")


def _validate_task_ref(ref: str) -> str:
    if not isinstance(ref, str) or not _TASK_REF_RE.match(ref):
        raise KernelRefusalError(f"invalid task_ref: {ref!r}")
    return ref


def _validate_revision(rev: str) -> str:
    if not isinstance(rev, str) or not _SHA256_RE.match(rev):
        raise KernelRefusalError(f"invalid revision: {rev!r}")
    return rev


def _normalize_text(value: str, max_len: int = 500) -> str:
    if "\x00" in value:
        raise KernelRefusalError("contains_nul")
    text = " ".join(value.split()).strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def load_resolution_input(path: Path, *, max_bytes: int = 16384) -> ResolutionInput:
    if not path.is_file():
        raise KernelRefusalError("resolution_input: not a regular file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise KernelRefusalError(f"resolution_input: cannot read: {exc}")
    if len(raw) > max_bytes:
        raise KernelRefusalError(f"resolution_input: {len(raw)} bytes exceeds {max_bytes} limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise KernelRefusalError(f"resolution_input: invalid JSON: {exc}")
    if not isinstance(data, dict):
        raise KernelRefusalError("resolution_input: must be a JSON object")
    for key in data:
        if key not in {"tasks", "active_session"}:
            raise KernelRefusalError(f"resolution_input: unknown key: {key}")
    tasks: dict[str, dict[str, str]] = {}
    raw_tasks = data.get("tasks")
    if raw_tasks is not None:
        if not isinstance(raw_tasks, dict):
            raise KernelRefusalError("resolution_input.tasks: must be an object")
        if len(raw_tasks) > 32:
            raise KernelRefusalError(f"resolution_input.tasks: {len(raw_tasks)} entries exceeds 32 limit")
        for key, value in raw_tasks.items():
            key_str = str(key)
            _validate_task_ref(key_str)
            if not isinstance(value, dict):
                raise KernelRefusalError(f"resolution_input.tasks.{key_str}: must be an object")
            for tk in value:
                if tk not in {"label", "revision"}:
                    raise KernelRefusalError(f"resolution_input.tasks.{key_str}: unknown key: {tk}")
            label = value.get("label")
            rev = value.get("revision")
            if not isinstance(label, str):
                raise KernelRefusalError(f"resolution_input.tasks.{key_str}.label: must be a string")
            if not isinstance(rev, str):
                raise KernelRefusalError(f"resolution_input.tasks.{key_str}.revision: must be a string")
            tasks[key_str] = {"label": _normalize_text(label), "revision": _validate_revision(rev)}
    active_session: dict[str, str] | None = None
    raw_session = data.get("active_session")
    if raw_session is not None:
        if not isinstance(raw_session, dict):
            raise KernelRefusalError("resolution_input.active_session: must be an object")
        for sk in raw_session:
            if sk not in {"status", "session_id", "task"}:
                raise KernelRefusalError(f"resolution_input.active_session: unknown key: {sk}")
        status = raw_session.get("status")
        session_id = raw_session.get("session_id")
        task_label = raw_session.get("task")
        if status != "active":
            raise KernelRefusalError(f"resolution_input.active_session.status: expected 'active', got {status!r}")
        if not isinstance(session_id, str) or not session_id.strip():
            raise KernelRefusalError("resolution_input.active_session.session_id: must be nonempty")
        if not isinstance(task_label, str) or not task_label.strip():
            raise KernelRefusalError("resolution_input.active_session.task: must be nonempty")
        active_session = {"status": "active", "session_id": _normalize_text(session_id), "task": _normalize_text(task_label)}
    return ResolutionInput(tasks=tasks, active_session=active_session)


def _build_resolution_lookup(res: ResolutionInput | None) -> Callable[[str], dict[str, Any] | None]:
    m = res.tasks if res else {}
    return lambda ref: m.get(ref)


def _get_resolution_session(res: ResolutionInput | None) -> dict[str, str] | None:
    return res.active_session if res else None


# ---------------------------------------------------------------------------
# Deterministic placeholder worker
# ---------------------------------------------------------------------------


def build_placeholder_preparation(
    *,
    resolved_task: Mapping[str, Any],
    interaction_id: str,
    revision: int,
    task_fingerprint: str,
    now_epoch: int,
    context_id: str,
    card_id: str,
    followup: Mapping[str, Any] | None,
    policy: KernelPolicy,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    context_expiry = now_epoch + policy.context_ttl_seconds
    label = resolved_task.get("label", "Unknown task")

    context: dict[str, Any] = {
        "schema_version": "task_initiation_context.v1",
        "context_id": context_id,
        "interaction_id": interaction_id,
        "revision": revision,
        "generated_at_epoch": now_epoch,
        "expires_at_epoch": context_expiry,
        "privacy_class": "sensitive_personal",
        "disclosed_facts": {
            "task": {"label": label},
            "followup": None,
            "project_summary": None,
            "session_capsule": None,
            "recent_interactions": [],
            "helper_material": [],
        },
        "provenance": [{
            "category": "task",
            "source_ref_sha256": hashlib.sha256(b"placeholder_worker.v1").hexdigest(),
            "observed_at_epoch": now_epoch,
            "fresh_until_epoch": context_expiry,
        }],
        "omissions": [],
        "task_fingerprint": task_fingerprint,
        "policy_version": "task_initiation_context_allowlist.v1",
        "model_content_sha256": "",
    }

    model_payload = c.api_payload_from_context(context)
    context["model_content_sha256"] = hashlib.sha256(_canonical_json(model_payload)).hexdigest()
    context = c.validate_context(context)

    # Proposal
    if followup is None:
        proposal: dict[str, Any] = {
            "schema_version": "task_initiation_proposal.v1",
            "blocker": {"category": "unclear_next_step", "summary": "The next step needs to be made concrete."},
            "tiny_start": {"kind": "digital", "estimated_minutes": 3,
                           "instruction": "Open the task and write one concrete next step.",
                           "completion_signal": "One concrete next step is written."},
        }
    elif followup.get("action") == "shrink":
        proposal = {
            "schema_version": "task_initiation_proposal.v1",
            "blocker": {"category": "too_big", "summary": "The previous start was too large."},
            "tiny_start": {"kind": "digital", "estimated_minutes": 1,
                           "instruction": "Open the task and write one word toward it.",
                           "completion_signal": "One word is written."},
        }
    elif followup.get("action") == "blocked":
        proposal = {
            "schema_version": "task_initiation_proposal.v1",
            "blocker": {"category": "other", "summary": "A blocker remains."},
            "tiny_start": {"kind": "digital", "estimated_minutes": 2,
                           "instruction": "Write one sentence naming the blocker.",
                           "completion_signal": "One blocker sentence is written."},
        }
    else:
        raise KernelRefusalError(f"unknown followup action: {followup.get('action')}")
    proposal = c.validate_proposal(proposal)

    # Card
    start_cd = min(proposal["tiny_start"]["estimated_minutes"] * 60, policy.start_countdown_seconds_cap)
    card: dict[str, Any] = {
        "schema_version": "task_initiation_card.v1",
        "card_id": card_id, "interaction_id": interaction_id, "revision": revision,
        "title": "Take one small step", "task_label": label,
        "blocker": proposal["blocker"], "tiny_start": proposal["tiny_start"],
        "issued_at_epoch": now_epoch, "expires_at_epoch": now_epoch + policy.card_ttl_seconds,
        "start_countdown_seconds": start_cd,
        "actions": [
            {"id": "start", "label": "Start"}, {"id": "shrink", "label": "Shrink"},
            {"id": "blocked", "label": "Blocked"}, {"id": "defer", "label": "Defer"},
        ],
        "dismiss_action": "dismiss",
    }
    card = c.validate_card(card)
    return context, proposal, card


# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------


def wall_clock_epoch() -> int:
    return int(time_mod.time())


class TaskInitiationKernel:
    def __init__(self, state_dir: Path, *, policy: KernelPolicy = KernelPolicy(),
                 clock: Clock = wall_clock_epoch, id_factory: IdFactory = uuid.uuid4,
                 busy_timeout_seconds: float = 5.0) -> None:
        self._policy = policy
        self._clock = clock
        self._id_factory = id_factory
        self._store = TaskInitiationStore(state_dir, busy_timeout_seconds=busy_timeout_seconds)

    def initialize(self) -> dict[str, Any]:
        return self._store.initialize()

    def check_database(self) -> dict[str, Any]:
        return self._store.check_database()

    # --- ingest_stuck ---

    def ingest_stuck(self, stuck: Mapping[str, Any], *, resolution: ResolutionInput | None = None) -> OperationResult:
        validated = c.validate_stuck_event(stuck)
        pj = _canonical_json(validated)
        ph = hashlib.sha256(pj).hexdigest()
        pjs = pj.decode("utf-8")
        event_id = validated["event_id"]
        try:
            with self._store.immediate_transaction() as conn:
                ex = conn.execute("SELECT * FROM messages WHERE kind='stuck' AND message_id=?", (event_id,)).fetchone()
                if ex is not None:
                    if ex["payload_sha256"] == ph:
                        return OperationResult(result=self._store.validate_replay_bundle(conn, ex), replay=True)
                    raise KernelRefusalError(f"idempotency_conflict: {event_id}")
                now = self._clock()
                state = c._new_interaction(validated, received_at_epoch=now, policy=self._policy.reducer_policy())
                lookup = _build_resolution_lookup(resolution)
                session = _get_resolution_session(resolution)
                resolved = c.resolve_task(validated, session=session, lookup=lookup)
                state = c._attach_resolved_task(state, resolved, now_epoch=now)
                iid = str(self._id_factory())
                ctx_id = str(self._id_factory())
                cd_id = str(self._id_factory())
                fp = c.task_fingerprint(resolved)
                ctx, prop, cd = build_placeholder_preparation(
                    resolved_task=resolved, interaction_id=iid, revision=1,
                    task_fingerprint=fp, now_epoch=now, context_id=ctx_id, card_id=cd_id,
                    followup=None, policy=self._policy,
                )
                rp = self._policy.reducer_policy()
                state = c._record_context_prepared(state, ctx, resolved, now_epoch=now, policy=rp)
                state = c._record_proposal_validated(state, prop, now_epoch=now, policy=rp)
                state = c._record_card_published(state, cd, now_epoch=now, resolved_task=resolved, policy=rp)
                result: dict[str, Any] = {"kind": "stuck", "status": "card_published", "event_id": event_id, "interaction_id": iid, "card": cd}
                aj = _agg_to_db(state)
                dl = cd.get("expires_at_epoch")
                conn.execute("INSERT INTO interactions (event_id,interaction_id,aggregate_json,state_version,phase,terminal_status,next_deadline_epoch,last_observed_at_epoch,created_at_epoch,updated_at_epoch) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (event_id, iid, aj, state["state_version"], state["phase"], state.get("terminal_status"), dl, now, now, now))
                conn.execute("INSERT INTO messages (kind,message_id,payload_sha256,payload_json,event_id,result_json,recorded_at_epoch) VALUES (?,?,?,?,?,?,?)",
                             ("stuck", event_id, ph, pjs, event_id, json.dumps(result, sort_keys=True), now))
                conn.execute("INSERT INTO card_index (card_id,event_id,revision) VALUES (?,?,?)", (cd_id, event_id, 1))
                return OperationResult(result=result, replay=False)
        except c.TaskInitiationContractError as exc:
            raise KernelRefusalError(str(exc)) from exc
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.OperationalError as exc:
            if "database is locked" in str(exc).lower():
                raise KernelBusyError()
            raise KernelStorageError(str(exc))

    # --- respond ---

    def respond(self, response: Mapping[str, Any], *, resolution: ResolutionInput | None = None) -> OperationResult:
        validated = c.validate_response(response)
        pj = _canonical_json(validated)
        ph = hashlib.sha256(pj).hexdigest()
        pjs = pj.decode("utf-8")
        rid = validated["response_id"]
        cid_card = validated["card_id"]
        try:
            with self._store.immediate_transaction() as conn:
                ex = conn.execute("SELECT * FROM messages WHERE kind='response' AND message_id=?", (rid,)).fetchone()
                if ex is not None:
                    if ex["payload_sha256"] == ph:
                        return OperationResult(result=self._store.validate_replay_bundle(conn, ex), replay=True)
                    raise KernelRefusalError(f"idempotency_conflict: {rid}")
                now = self._clock()
                cr = conn.execute("SELECT * FROM card_index WHERE card_id=?", (cid_card,)).fetchone()
                if cr is None:
                    raise KernelRefusalError(f"unknown card_id: {cid_card}")
                event_id = cr["event_id"]
                ir = conn.execute("SELECT * FROM interactions WHERE event_id=?", (event_id,)).fetchone()
                if ir is None:
                    raise KernelCorruptionError(f"card_index {cid_card} references missing interaction {event_id}")
                aggregate = _agg_from_db(ir["aggregate_json"], source=f"interaction {event_id}")
                from ai_system.task_initiation_store import _validate_aggregate_structure, _validate_revision_contiguity
                _validate_aggregate_structure(aggregate, row_event_id=event_id)
                _validate_revision_contiguity(aggregate)
                eff = max(now, ir["last_observed_at_epoch"])
                state = c._advance_time(aggregate, now_epoch=eff, policy=self._policy.reducer_policy())
                if state.get("terminal_status") is not None:
                    if state["state_version"] != aggregate["state_version"]:
                        self._persist_state(conn, state, event_id, eff)
                    raise KernelRefusalError(f"interaction {event_id} is terminal: {state.get('terminal_status')}")
                sr = conn.execute("SELECT payload_json FROM messages WHERE kind='stuck' AND event_id=?", (event_id,)).fetchone()
                if sr is None:
                    raise KernelCorruptionError(f"interaction {event_id}: no Stuck message")
                stuck_payload = json.loads(sr["payload_json"])
                lookup = _build_resolution_lookup(resolution)
                session = _get_resolution_session(resolution)
                resolved = c.resolve_task(stuck_payload, session=session, lookup=lookup)
                rp = self._policy.reducer_policy()
                state = c._apply_response(state, validated, received_at_epoch=eff, resolved_task=resolved, policy=rp)
                # Handle Shrink/Blocked preparation
                if state["phase"] == "preparing":
                    action = validated["action"]
                    nrev = (state.get("current_revision") or 0) + 1
                    iid = state.get("interaction_id")
                    fp = state.get("task_fingerprint")
                    nctx = str(self._id_factory())
                    ncd = str(self._id_factory())
                    ctx2, prop2, cd2 = build_placeholder_preparation(
                        resolved_task=resolved, interaction_id=iid, revision=nrev,
                        task_fingerprint=fp, now_epoch=eff, context_id=nctx, card_id=ncd,
                        followup={"action": action}, policy=self._policy,
                    )
                    state = c._record_context_prepared(state, ctx2, resolved, now_epoch=eff, policy=rp)
                    state = c._record_proposal_validated(state, prop2, now_epoch=eff, policy=rp)
                    state = c._record_card_published(state, cd2, now_epoch=eff, resolved_task=resolved, policy=rp)
                    # Find response revision
                    frev = None
                    for rv in state.get("revisions", []):
                        if rv.get("response") and rv["response"].get("response_id") == rid:
                            frev = rv["revision"]; break
                    if frev is None:
                        frev = max(len(state.get("revisions", [])) - 1, 1)
                    result: dict[str, Any] = {
                        "kind": "response", "status": "accepted", "response_id": rid,
                        "card_id": cid_card, "interaction_id": iid, "revision": frev,
                        "action": action, "next_card": cd2, "phase": "awaiting_response",
                        "terminal_status": None, "resolution_reason": None, "observation_due_at_epoch": None,
                    }
                    self._persist_state(conn, state, event_id, eff)
                    conn.execute("INSERT INTO messages (kind,message_id,payload_sha256,payload_json,event_id,result_json,recorded_at_epoch) VALUES (?,?,?,?,?,?,?)",
                                 ("response", rid, ph, pjs, event_id, json.dumps(result, sort_keys=True), eff))
                    conn.execute("INSERT INTO card_index (card_id,event_id,revision) VALUES (?,?,?)", (ncd, event_id, nrev))
                    return OperationResult(result=result, replay=False)
                # Non-preparing
                result = self._static_result(state, validated, event_id, cid_card)
                self._persist_state(conn, state, event_id, eff)
                conn.execute("INSERT INTO messages (kind,message_id,payload_sha256,payload_json,event_id,result_json,recorded_at_epoch) VALUES (?,?,?,?,?,?,?)",
                             ("response", rid, ph, pjs, event_id, json.dumps(result, sort_keys=True), eff))
                return OperationResult(result=result, replay=False)
        except c.TaskInitiationContractError as exc:
            raise KernelRefusalError(str(exc)) from exc
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.OperationalError as exc:
            if "database is locked" in str(exc).lower():
                raise KernelBusyError()
            raise KernelStorageError(str(exc))

    def _static_result(self, state: dict[str, Any], validated: dict[str, Any], event_id: str, cid_card: str) -> dict[str, Any]:
        rid = validated["response_id"]
        action = validated["action"]
        iid = state.get("interaction_id")
        revision = None
        for rv in state.get("revisions", []):
            if rv.get("card_id") == cid_card:
                revision = rv["revision"]; break
        base: dict[str, Any] = {"kind": "response", "response_id": rid, "card_id": cid_card, "interaction_id": iid, "revision": revision}
        if state.get("terminal_status") == "superseded":
            base.update(status="superseded", requested_action=action, next_card=None, phase=state["phase"],
                        terminal_status="superseded", resolution_reason="task_changed", observation_due_at_epoch=None)
            return base
        base.update(status="accepted", action=action, phase=state["phase"],
                     terminal_status=state.get("terminal_status"), resolution_reason=state.get("resolution_reason"),
                     observation_due_at_epoch=state.get("observation_due_at_epoch"), next_card=None)
        return base

    def _persist_state(self, conn: Any, state: dict[str, Any], event_id: str, eff: int) -> None:
        dl = TaskInitiationStore._compute_next_deadline(state)
        aj = _agg_to_db(state)
        conn.execute("UPDATE interactions SET aggregate_json=?,state_version=?,phase=?,terminal_status=?,next_deadline_epoch=?,last_observed_at_epoch=?,updated_at_epoch=? WHERE event_id=?",
                     (aj, state["state_version"], state["phase"], state.get("terminal_status"), dl, eff, eff, event_id))

    # --- show ---

    def show(self, event_id: str, *, include_sensitive: bool = False) -> dict[str, Any]:
        with self._store.read_connection() as conn:
            row = conn.execute("SELECT * FROM interactions WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                raise KernelNotFoundError(f"interaction {event_id} not found")
            result: dict[str, Any] = {
                "event_id": event_id, "interaction_id": None, "phase": row["phase"],
                "terminal_status": row["terminal_status"], "state_version": row["state_version"],
                "created_at_epoch": row["created_at_epoch"], "updated_at_epoch": row["updated_at_epoch"],
                "needs_reconciliation": self._needs_reconciliation(row),
            }
            agg = _agg_from_db(row["aggregate_json"], source=f"interaction {event_id}")
            result["interaction_id"] = agg.get("interaction_id")
            if include_sensitive:
                result["aggregate"] = _convert_evidence_issues(agg)
            return result

    # --- list_active ---

    def list_active(self, *, include_sensitive: bool = False) -> list[dict[str, Any]]:
        with self._store.read_connection() as conn:
            rows = conn.execute("SELECT * FROM interactions WHERE terminal_status IS NULL ORDER BY event_id").fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                item: dict[str, Any] = {
                    "event_id": row["event_id"], "interaction_id": None, "phase": row["phase"],
                    "state_version": row["state_version"], "created_at_epoch": row["created_at_epoch"],
                    "updated_at_epoch": row["updated_at_epoch"], "needs_reconciliation": self._needs_reconciliation(row),
                }
                agg = _agg_from_db(row["aggregate_json"], source=f"interaction {row['event_id']}")
                item["interaction_id"] = agg.get("interaction_id")
                if include_sensitive:
                    item["aggregate"] = _convert_evidence_issues(agg)
                results.append(item)
            return results

    # --- reconcile ---

    def reconcile(self) -> dict[str, Any]:
        try:
            with self._store.immediate_transaction() as conn:
                now = self._clock()
                rows = conn.execute("SELECT * FROM interactions WHERE terminal_status IS NULL ORDER BY event_id").fetchall()
                changed = 0; expired = 0; completed = 0
                from ai_system.task_initiation_store import _validate_aggregate_structure, _validate_revision_contiguity
                for row in rows:
                    agg = _agg_from_db(row["aggregate_json"], source=f"interaction {row['event_id']}")
                    _validate_aggregate_structure(agg, row_event_id=row["event_id"])
                    _validate_revision_contiguity(agg)
                    eff = max(now, row["last_observed_at_epoch"])
                    ns = c._advance_time(agg, now_epoch=eff, policy=self._policy.reducer_policy())
                    if ns["state_version"] != agg["state_version"]:
                        changed += 1
                        nt = ns.get("terminal_status")
                        if nt == "expired": expired += 1
                        elif nt == "completed": completed += 1
                        self._persist_state(conn, ns, row["event_id"], eff)
                return {"ok": True, "reconciled": changed, "expired": expired, "completed": completed, "checked_at_epoch": now}
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.OperationalError as exc:
            if "database is locked" in str(exc).lower():
                raise KernelBusyError()
            raise KernelStorageError(str(exc))

    @staticmethod
    def _needs_reconciliation(row: sqlite3_module.Row) -> bool:
        if row["terminal_status"] is not None:
            return False
        if row["next_deadline_epoch"] is None:
            return False
        return int(time_mod.time()) >= row["next_deadline_epoch"]
