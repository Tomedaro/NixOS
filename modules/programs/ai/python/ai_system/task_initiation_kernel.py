"""Synchronous deterministic task-initiation lifecycle kernel.

Owns: atomic Stuck/Response flows, deterministic no-model worker,
owner-only reconciliation, and fixture-free all-row deadline advancement.

No transport, model, daemon, or task execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import math
import re as _re
import sqlite3 as sqlite3_module
import stat
import time as time_mod
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

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
    _convert_evidence_issues,
    _expected_response_result,
    _expected_stuck_result,
    _interaction_policy_from_json,
    _translate_sqlite_error,
    InteractionPolicy,
    reconstruct_expected_aggregate_v1,
)

# ---------------------------------------------------------------------------
Clock = Callable[[], int]
IdFactory = Callable[[], uuid.UUID]



@dataclass(frozen=True)
class KernelPolicy:
    stuck_ttl_seconds: int = 7200
    max_future_skew_seconds: int = 300
    max_card_revisions: int = 3
    tiny_start_minutes_cap: int = 10
    start_countdown_seconds_cap: int = 600
    observation_seconds: int = 600
    context_ttl_seconds: int = 300
    card_ttl_seconds: int = 900
    max_resolution_tasks: int = 32
    max_input_bytes: int = 65536
    max_resolution_bytes: int = 16384

    def __post_init__(self) -> None:
        for name, value, min_val in [
            ("stuck_ttl_seconds", self.stuck_ttl_seconds, 1),
            ("max_future_skew_seconds", self.max_future_skew_seconds, 0),
            ("max_card_revisions", self.max_card_revisions, 1),
            ("tiny_start_minutes_cap", self.tiny_start_minutes_cap, 1),
            ("start_countdown_seconds_cap", self.start_countdown_seconds_cap, 1),
            ("observation_seconds", self.observation_seconds, 1),
            ("context_ttl_seconds", self.context_ttl_seconds, 1),
            ("card_ttl_seconds", self.card_ttl_seconds, 1),
            ("max_resolution_tasks", self.max_resolution_tasks, 1),
            ("max_input_bytes", self.max_input_bytes, 1),
            ("max_resolution_bytes", self.max_resolution_bytes, 1),
        ]:
            if isinstance(value, bool) or not isinstance(value, int) or value < min_val:
                raise ValueError(f"KernelPolicy.{name} must be int >= {min_val}, got {value!r}")

    def reducer_policy(self) -> dict[str, int]:
        return {
            "max_card_revisions": self.max_card_revisions,
            "start_countdown_seconds_cap": self.start_countdown_seconds_cap,
            "observation_seconds": self.observation_seconds,
            "context_ttl_seconds": self.context_ttl_seconds,
            "card_ttl_seconds": self.card_ttl_seconds,
            "stuck_ttl_seconds": self.stuck_ttl_seconds,
            "max_future_skew_seconds": self.max_future_skew_seconds,
            "tiny_start_minutes_cap": self.tiny_start_minutes_cap,
        }


@dataclass(frozen=True)
class OperationResult:
    result: dict[str, Any]
    replay: bool


@dataclass(frozen=True)
class ResolutionInput:
    tasks: Mapping[str, Mapping[str, str]]
    active_session: Mapping[str, str] | None

# ---------------------------------------------------------------------------
# Resolution fixture helpers
# ---------------------------------------------------------------------------
_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")


def _validate_revision(rev: str) -> str:
    if not isinstance(rev, str) or not _SHA256_RE.match(rev):
        raise KernelRefusalError(f"invalid revision: {rev!r}")
    return rev


def _normalize_text(value: str, max_len: int = 500) -> str:
    if "\x00" in value:
        raise KernelRefusalError("contains_nul")
    text = " ".join(value.split()).strip()
    if len(text) > max_len:
        raise KernelRefusalError("resolution_input: value too long")
    return text


def load_resolution_input(path: Path, *, policy: KernelPolicy) -> ResolutionInput:
    # Open with O_NOFOLLOW (when available) to reject symlinks at the OS level.
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags)
    except OSError:
        raise KernelRefusalError("resolution_input: cannot access file")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise KernelRefusalError("resolution_input: not a regular file")
        if st.st_size > policy.max_resolution_bytes:
            raise KernelRefusalError("resolution_input: file exceeds size limit")
        limit = policy.max_resolution_bytes + 1
        raw = os.read(fd, limit)
        if len(raw) > policy.max_resolution_bytes:
            raise KernelRefusalError("resolution_input: exceeds size limit")
    finally:
        os.close(fd)
    try:
        data = c._strict_json_loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise KernelRefusalError("resolution_input: invalid JSON") from exc
    if not isinstance(data, dict):
        raise KernelRefusalError("resolution_input: must be a JSON object")
    for key in data:
        if key not in {"tasks", "active_session"}:
            raise KernelRefusalError("resolution_input: unknown key")
    tasks: dict[str, dict[str, str]] = {}
    raw_tasks = data.get("tasks")
    if raw_tasks is not None:
        if not isinstance(raw_tasks, dict):
            raise KernelRefusalError("resolution_input.tasks: must be an object")
        if len(raw_tasks) > policy.max_resolution_tasks:
            raise KernelRefusalError("resolution_input.tasks: too many entries")
        for key, value in raw_tasks.items():
            if not isinstance(key, str):
                raise KernelRefusalError("resolution_input: invalid task_ref")
            try:
                c._validate_inline_task_ref({"source": "tasknotes", "ref": key})
            except c.TaskInitiationContractError:
                raise KernelRefusalError("resolution_input: invalid task_ref")
            if not isinstance(value, dict):
                raise KernelRefusalError("resolution_input.tasks: must be an object")
            for tk in value:
                if tk not in {"label", "revision"}:
                    raise KernelRefusalError("resolution_input.tasks: unknown key")
            label = value.get("label")
            rev = value.get("revision")
            if not isinstance(label, str):
                raise KernelRefusalError("resolution_input.tasks.label: must be a string")
            if not isinstance(rev, str):
                raise KernelRefusalError("resolution_input.tasks.revision: must be a string")
            tasks[key] = {"label": _normalize_text(label), "revision": _validate_revision(rev)}
    active_session: dict[str, str] | None = None
    raw_session = data.get("active_session")
    if raw_session is not None:
        if not isinstance(raw_session, dict):
            raise KernelRefusalError("resolution_input.active_session: must be an object")
        for sk in raw_session:
            if sk not in {"status", "session_id", "task"}:
                raise KernelRefusalError("resolution_input.active_session: unknown key")
        status = raw_session.get("status")
        session_id = raw_session.get("session_id")
        task_label = raw_session.get("task")
        if status != "active":
            raise KernelRefusalError("resolution_input.active_session.status: invalid")
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
            "followup": followup,
            "project_summary": None,
            "session_capsule": None,
            "recent_interactions": [],
            "helper_material": [],
        },
        "provenance": [{
            "category": "task",
            "source_ref_sha256": task_fingerprint,
            "observed_at_epoch": now_epoch,
            "fresh_until_epoch": context_expiry,
        }],
        "omissions": [],
        "task_fingerprint": task_fingerprint,
        "policy_version": "task_initiation_context_allowlist.v1",
        "model_content_sha256": "",
    }

    model_payload = c.api_payload_from_context(context)
    context["model_content_sha256"] = hashlib.sha256(c._canonical_json(model_payload)).hexdigest()
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




def _interaction_policy_to_json(policy: KernelPolicy) -> str:
    """Produce canonical JSON snapshot of lifecycle policy fields via InteractionPolicy."""
    ip = InteractionPolicy(
        stuck_ttl_seconds=policy.stuck_ttl_seconds,
        max_future_skew_seconds=policy.max_future_skew_seconds,
        max_card_revisions=policy.max_card_revisions,
        tiny_start_minutes_cap=policy.tiny_start_minutes_cap,
        start_countdown_seconds_cap=policy.start_countdown_seconds_cap,
        observation_seconds=policy.observation_seconds,
        context_ttl_seconds=policy.context_ttl_seconds,
        card_ttl_seconds=policy.card_ttl_seconds,
    )
    return ip.to_canonical_json()




class TaskInitiationKernel:
    def __init__(self, state_dir: Path, *, policy: KernelPolicy = KernelPolicy(),
                 clock: Clock = wall_clock_epoch, id_factory: IdFactory = uuid.uuid4,
                 busy_timeout_seconds: float = 5.0) -> None:
        if isinstance(busy_timeout_seconds, bool) or not isinstance(busy_timeout_seconds, (int, float)):
            raise ValueError(f"busy_timeout_seconds must be a number, got {busy_timeout_seconds!r}")
        if not math.isfinite(busy_timeout_seconds) or busy_timeout_seconds < 0:
            raise ValueError(f"busy_timeout_seconds must be finite and nonnegative, got {busy_timeout_seconds!r}")
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
        pj = c._canonical_json(validated)
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
                aj = _agg_to_db(state)
                dl = cd.get("expires_at_epoch")
                policy_json = _interaction_policy_to_json(self._policy)
                conn.execute("INSERT INTO interactions (event_id,interaction_id,aggregate_json,state_version,phase,terminal_status,next_deadline_epoch,last_observed_at_epoch,created_at_epoch,updated_at_epoch,interaction_policy_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (event_id, iid, aj, state["state_version"], state["phase"], state.get("terminal_status"), dl, now, now, now, policy_json))
                conn.execute("INSERT INTO card_index (card_id,event_id,revision) VALUES (?,?,?)", (cd_id, event_id, 1))
                result = _expected_stuck_result(event_id, iid, state, conn)
                result_json = c._canonical_json(result).decode("utf-8")
                conn.execute("INSERT INTO messages (kind,message_id,payload_sha256,payload_json,event_id,result_json,recorded_at_epoch) VALUES (?,?,?,?,?,?,?)",
                             ("stuck", event_id, ph, pjs, event_id, result_json, now))
                # --- write-before-commit gate: validate and reconstruct ---
                self._load_validated_interaction(conn, event_id)
                interaction_pol = InteractionPolicy(
                    stuck_ttl_seconds=self._policy.stuck_ttl_seconds,
                    max_future_skew_seconds=self._policy.max_future_skew_seconds,
                    max_card_revisions=self._policy.max_card_revisions,
                    tiny_start_minutes_cap=self._policy.tiny_start_minutes_cap,
                    start_countdown_seconds_cap=self._policy.start_countdown_seconds_cap,
                    observation_seconds=self._policy.observation_seconds,
                    context_ttl_seconds=self._policy.context_ttl_seconds,
                    card_ttl_seconds=self._policy.card_ttl_seconds,
                )
                sr = conn.execute(
                    "SELECT * FROM messages WHERE kind='stuck' AND event_id=?", (event_id,)
                ).fetchone()
                if sr is None:
                    raise KernelCorruptionError(f"ingest_stuck: no Stuck row for {event_id}")
                reconstructed = reconstruct_expected_aggregate_v1(
                    stuck_row=sr,
                    resolved_task=resolved,
                    revisions=state["revisions"],
                    response_messages={},
                    superseding_msg=None,
                    terminal_at_epoch=None,
                    interaction_policy=interaction_pol,
                )
                if _agg_to_db(reconstructed) != _agg_to_db(state):
                    raise KernelCorruptionError(
                        "ingest_stuck: reducer reconstruction mismatch"
                    )
                return OperationResult(result=result, replay=False)
        except c.TaskInitiationContractError as exc:
            raise KernelRefusalError(str(exc)) from exc
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.Error as exc:
            raise _translate_sqlite_error(exc)

    # --- respond ---

    def respond(self, response: Mapping[str, Any], *, resolution: ResolutionInput | None = None) -> OperationResult:
        validated = c.validate_response(response)
        pj = c._canonical_json(validated)
        ph = c._payload_sha256(validated)
        pjs = pj.decode("utf-8")
        rid = validated["response_id"]
        cid_card = validated["card_id"]
        try:
            with self._store.immediate_transaction() as conn:
                # --- exact replay ---
                ex = conn.execute(
                    "SELECT * FROM messages WHERE kind='response' AND message_id=?", (rid,)
                ).fetchone()
                if ex is not None:
                    if ex["payload_sha256"] == ph:
                        return OperationResult(
                            result=self._store.validate_replay_bundle(conn, ex), replay=True
                        )
                    raise KernelRefusalError(f"idempotency_conflict: {rid}")
                # --- route Card -> interaction ---
                cr = conn.execute(
                    "SELECT * FROM card_index WHERE card_id=?", (cid_card,)
                ).fetchone()
                if cr is None:
                    raise KernelRefusalError(f"unknown card_id: {cid_card}")
                event_id = cr["event_id"]
                card_revision = cr["revision"]
                # --- load and validate owner ---
                int_row, aggregate = self._load_validated_interaction(conn, event_id)
                persisted_policy_ip = self._load_interaction_policy(conn, event_id)
                persisted_policy = persisted_policy_ip.reducer_policy()
                now = self._clock()
                eff = max(now, int_row["last_observed_at_epoch"])
                state = c._advance_time(aggregate, now_epoch=eff, policy=persisted_policy)
                post_commit_refusal: KernelRefusalError | None = None
                # --- deadline check ---
                if state.get("terminal_status") is not None:
                    if state["state_version"] != aggregate["state_version"]:
                        # Deadline advancement just made it terminal
                        self._persist_state(conn, state, event_id, eff)
                        self._load_validated_interaction(conn, event_id)
                        post_commit_refusal = KernelRefusalError(
                            f"interaction {event_id} became terminal: {state.get('terminal_status')}"
                        )
                    else:
                        # Already terminal before deadline check
                        raise KernelRefusalError(
                            f"interaction {event_id} is terminal: {state.get('terminal_status')}"
                        )
                else:
                    sr = conn.execute(
                        "SELECT * FROM messages WHERE kind='stuck' AND event_id=?", (event_id,)
                    ).fetchone()
                    if sr is None:
                        raise KernelCorruptionError(f"interaction {event_id}: no Stuck message")
                    stuck_payload = c._strict_json_loads(sr["payload_json"])
                    if not isinstance(stuck_payload, dict):
                        raise KernelCorruptionError(f"interaction {event_id}: Stuck payload is not a dict")
                    # --- resolve and apply ---
                    lookup = _build_resolution_lookup(resolution)
                    session = _get_resolution_session(resolution)
                    resolved = c.resolve_task(stuck_payload, session=session, lookup=lookup)
                    state = c._apply_response(state, validated, received_at_epoch=eff, resolved_task=resolved, policy=persisted_policy)
                    iid = state["interaction_id"]
                    # --- build result ---
                    next_card: dict[str, Any] | None = None
                    if state["phase"] == "preparing":
                        # Find targeted revision for followup
                        targeted_revision: dict[str, Any] | None = None
                        for rv in aggregate.get("revisions", []):
                            if rv["revision"] == card_revision:
                                targeted_revision = rv
                                break
                        nrev = (state.get("current_revision") or 0) + 1
                        fp = state.get("task_fingerprint")
                        nctx = str(self._id_factory())
                        ncd = str(self._id_factory())
                        followup: dict[str, Any] = {
                            "action": validated["action"],
                            "detail": validated["detail"],
                            "prior_tiny_start": (
                                targeted_revision["card"]["tiny_start"]["instruction"]
                                if targeted_revision is not None
                                else ""
                            ),
                        }
                        ctx2, prop2, cd2 = build_placeholder_preparation(
                            resolved_task=resolved, interaction_id=iid, revision=nrev,
                            task_fingerprint=fp, now_epoch=eff, context_id=nctx, card_id=ncd,
                            followup=followup, policy=KernelPolicy(**persisted_policy),
                        )
                        state = c._record_context_prepared(state, ctx2, resolved, now_epoch=eff, policy=persisted_policy)
                        state = c._record_proposal_validated(state, prop2, now_epoch=eff, policy=persisted_policy)
                        state = c._record_card_published(state, cd2, now_epoch=eff, resolved_task=resolved, policy=persisted_policy)
                        next_card = cd2
                    # --- persist state and next card before building result ---
                    self._persist_state(conn, state, event_id, eff)
                    if next_card is not None:
                        conn.execute(
                            "INSERT INTO card_index (card_id,event_id,revision) VALUES (?,?,?)",
                            (next_card["card_id"], event_id, next_card["revision"]),
                        )
                    result = _expected_response_result(rid, state, conn, payload=validated)
                    result_json = c._canonical_json(result).decode("utf-8")
                    conn.execute(
                        "INSERT INTO messages (kind,message_id,payload_sha256,payload_json,event_id,result_json,recorded_at_epoch) VALUES (?,?,?,?,?,?,?)",
                        ("response", rid, ph, pjs, event_id, result_json, eff),
                    )
                    # --- post-commit validation ---
                    self._load_validated_interaction(conn, event_id)
                    # --- reducer reconstruction gate ---
                    all_resp_rows = conn.execute(
                        "SELECT * FROM messages WHERE kind='response' AND event_id=?",
                        (event_id,),
                    ).fetchall()
                    resp_msg_map: dict[str, Any] = {}
                    superseding: Any = None
                    for rrow in all_resp_rows:
                        rpay = c._strict_json_loads(rrow["payload_json"])
                        if isinstance(rpay, dict):
                            resp_msg_map[rpay.get("response_id", rrow["message_id"])] = rrow
                    for rrow in all_resp_rows:
                        rpay = c._strict_json_loads(rrow["payload_json"])
                        if isinstance(rpay, dict):
                            rid_key = rpay.get("response_id")
                            in_rev = any(
                                (rev.get("response") or {}).get("response_id") == rid_key
                                for rev in state.get("revisions", [])
                            )
                            if not in_rev:
                                superseding = rrow
                    rec_policy = persisted_policy_ip
                    # Use original resolved_task from aggregate for reconstruction,
                    # not the current resolution (which may differ for task_changed).
                    rec_agg = reconstruct_expected_aggregate_v1(
                        stuck_row=sr,
                        resolved_task=aggregate.get("resolved_task", resolved),
                        revisions=state["revisions"],
                        response_messages=resp_msg_map,
                        superseding_msg=superseding,
                        terminal_at_epoch=state.get("terminal_at_epoch"),
                        interaction_policy=rec_policy,
                    )
                    if _agg_to_db(rec_agg) != _agg_to_db(state):
                        raise KernelCorruptionError(
                            "respond: reducer reconstruction mismatch"
                        )
                    return OperationResult(result=result, replay=False)
                # If we reach here with a post_commit_refusal, let the with block exit normally
                # so it commits, then raise after
            if post_commit_refusal is not None:
                raise post_commit_refusal
        except c.TaskInitiationContractError as exc:
            raise KernelRefusalError(str(exc)) from exc
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.Error as exc:
            raise _translate_sqlite_error(exc)
    def _load_validated_interaction(
        self, conn: sqlite3.Connection, event_id: str
    ) -> tuple[sqlite3.Row, dict[str, Any]]:
        """Load and fully validate an interaction row and its aggregate."""
        int_row = conn.execute(
            "SELECT * FROM interactions WHERE event_id = ?", (event_id,)
        ).fetchone()
        if int_row is None:
            raise KernelNotFoundError(f"interaction {event_id} not found")
        aggregate = _agg_from_db(int_row["aggregate_json"], source=f"interaction {event_id}")
        self._store._validate_interaction_row(conn, event_id)
        return int_row, aggregate

    def _load_interaction_policy(
        self, conn: sqlite3.Connection, event_id: str
    ) -> InteractionPolicy:
        """Load and validate the persisted interaction policy snapshot."""
        row = conn.execute(
            "SELECT interaction_policy_json FROM interactions WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KernelCorruptionError(f"interaction {event_id}: not found")
        return _interaction_policy_from_json(row["interaction_policy_json"])

    def _persist_state(
        self,
        conn: sqlite3.Connection,
        state: Mapping[str, Any],
        event_id: str,
        last_observed: int,
    ) -> None:
        """Update the persisted interaction row from new state."""
        aj = _agg_to_db(state)
        dl = self._store._compute_next_deadline(state)
        conn.execute(
            "UPDATE interactions SET aggregate_json=?, state_version=?, phase=?, "
            "terminal_status=?, next_deadline_epoch=?, last_observed_at_epoch=?, "
            "updated_at_epoch=? WHERE event_id=?",
            (aj, state["state_version"], state["phase"], state.get("terminal_status"),
             dl, last_observed, last_observed, event_id),
        )

    # --- show ---

    def show(self, event_id: str, *, include_sensitive: bool = False) -> dict[str, Any]:
        with self._store.read_connection() as conn:
            now = self._clock()
            int_row, aggregate = self._load_validated_interaction(conn, event_id)
            result: dict[str, Any] = {
                "event_id": event_id, "interaction_id": aggregate.get("interaction_id"),
                "phase": int_row["phase"],
                "terminal_status": int_row["terminal_status"],
                "state_version": int_row["state_version"],
                "created_at_epoch": int_row["created_at_epoch"],
                "updated_at_epoch": int_row["updated_at_epoch"],
                "needs_reconciliation": self._needs_reconciliation(int_row, now_epoch=now),
            }
            if include_sensitive:
                result["aggregate"] = _convert_evidence_issues(aggregate)
            return result

    # --- list_active ---

    def list_active(self, *, include_sensitive: bool = False) -> list[dict[str, Any]]:
        with self._store.read_connection() as conn:
            now = self._clock()
            rows = conn.execute(
                "SELECT * FROM interactions WHERE terminal_status IS NULL ORDER BY event_id"
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                _, aggregate = self._load_validated_interaction(conn, row["event_id"])
                item: dict[str, Any] = {
                    "event_id": row["event_id"],
                    "interaction_id": aggregate.get("interaction_id"),
                    "phase": row["phase"],
                    "state_version": row["state_version"],
                    "created_at_epoch": row["created_at_epoch"],
                    "updated_at_epoch": row["updated_at_epoch"],
                    "needs_reconciliation": self._needs_reconciliation(row, now_epoch=now),
                }
                if include_sensitive:
                    item["aggregate"] = _convert_evidence_issues(aggregate)
                results.append(item)
            return results

    # --- reconcile ---

    def reconcile(self) -> dict[str, Any]:
        try:
            with self._store.immediate_transaction() as conn:
                now = self._clock()
                rows = conn.execute(
                    "SELECT * FROM interactions WHERE terminal_status IS NULL ORDER BY event_id"
                ).fetchall()
                # Pass 1: validate all owners, abort on any corruption
                owners: list[tuple[sqlite3.Row, dict[str, Any]]] = []
                for row in rows:
                    _, aggregate = self._load_validated_interaction(conn, row["event_id"])
                    owners.append((row, aggregate))
                # Pass 2: advance and persist
                changed = 0; expired = 0; completed = 0
                for row, aggregate in owners:
                    eff = max(now, row["last_observed_at_epoch"])
                    persisted_policy = self._load_interaction_policy(conn, row["event_id"])
                    ns = c._advance_time(aggregate, now_epoch=eff, policy=persisted_policy)
                    if ns["state_version"] != aggregate["state_version"]:
                        changed += 1
                        nt = ns.get("terminal_status")
                        if nt == "expired":
                            expired += 1
                        elif nt == "completed":
                            completed += 1
                        self._persist_state(conn, ns, row["event_id"], eff)
                        # Validate after persist
                        self._load_validated_interaction(conn, row["event_id"])
                        # P1: reconstruct expected aggregate for changed owners
                        event_id = row["event_id"]
                        stuck_row = conn.execute(
                            "SELECT * FROM messages WHERE kind='stuck' AND event_id=?",
                            (event_id,),
                        ).fetchone()
                        if stuck_row is not None:
                            resp_rows = conn.execute(
                                "SELECT * FROM messages WHERE kind='response' AND event_id=? ORDER BY message_id",
                                (event_id,),
                            ).fetchall()
                            resp_msg_map: dict[str, sqlite3.Row] = {}
                            superseding: sqlite3.Row | None = None
                            accepted_ids: set[str] = set()
                            for rev in ns.get("revisions", []):
                                rev_resp = rev.get("response")
                                if rev_resp is not None and isinstance(rev_resp, dict):
                                    accepted_ids.add(rev_resp.get("response_id", ""))
                            for rr in resp_rows:
                                rid = rr["message_id"]
                                try:
                                    rpay = c._strict_json_loads(rr["payload_json"])
                                except (json.JSONDecodeError, ValueError):
                                    raise KernelCorruptionError(f"reconcile: invalid response payload for {rid}")
                                if isinstance(rpay, dict):
                                    actual_rid = rpay.get("response_id", rid)
                                    if actual_rid in accepted_ids:
                                        resp_msg_map[actual_rid] = rr
                                    else:
                                        superseding = rr
                            rec_agg = reconstruct_expected_aggregate_v1(
                                stuck_row=stuck_row,
                                resolved_task=ns.get("resolved_task", aggregate.get("resolved_task", {})),
                                revisions=ns.get("revisions", []),
                                response_messages=resp_msg_map,
                                superseding_msg=superseding,
                                terminal_at_epoch=ns.get("terminal_at_epoch"),
                                interaction_policy=persisted_policy,
                            )
                            if _agg_to_db(rec_agg) != _agg_to_db(ns):
                                raise KernelCorruptionError(
                                    f"reconcile: reducer reconstruction mismatch for {event_id}"
                                )
                    elif eff > row["last_observed_at_epoch"]:
                        # No reducer change, but high-water must advance
                        conn.execute(
                            "UPDATE interactions SET last_observed_at_epoch=?, updated_at_epoch=? WHERE event_id=?",
                            (eff, eff, row["event_id"]),
                        )
                return {"ok": True, "reconciled": changed, "expired": expired,
                        "completed": completed, "checked_at_epoch": now}
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3_module.Error as exc:
            raise _translate_sqlite_error(exc)

    @staticmethod
    def _needs_reconciliation(row: sqlite3_module.Row, *, now_epoch: int) -> bool:
        if row["terminal_status"] is not None:
            return False
        if row["next_deadline_epoch"] is None:
            return False
        return max(now_epoch, row["last_observed_at_epoch"]) >= row["next_deadline_epoch"]
