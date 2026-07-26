"""Private SQLite store for the task-initiation kernel.

Owns: XDG path resolution, permission enforcement, journal-mode control,
explicit transaction boundaries, exact three-table migration, canonical
codec, owner-bundle replay validation, proportional corruption checking,
and read-only health inspection.

No public schema.  No ORM, framework, daemon, queue, or service.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from ai_system import task_initiation_contracts as c
from ai_system import task_initiation_private as p

# ---------------------------------------------------------------------------
# Error classes (re-exported from task_initiation_private)
# ---------------------------------------------------------------------------

KernelNotFoundError = p.KernelNotFoundError
KernelRefusalError = p.KernelRefusalError
KernelCorruptionError = p.KernelCorruptionError
KernelBusyError = p.KernelBusyError
KernelStorageError = p.KernelStorageError

def _translate_sqlite_error(exc: sqlite3.Error) -> Exception:
    """Map sqlite3 errors to kernel exceptions using error codes where available.

    Normalizes extended result codes to primary codes (code & 0xFF).
    """
    if isinstance(exc, sqlite3.IntegrityError):
        return KernelCorruptionError(str(exc))
    if hasattr(exc, "sqlite_errorcode") and exc.sqlite_errorcode is not None:
        code = exc.sqlite_errorcode
        primary = code & 0xFF
        # BUSY/LOCKED → KernelBusyError
        if primary == sqlite3.SQLITE_BUSY or primary == sqlite3.SQLITE_LOCKED:
            return KernelBusyError()
        # CORRUPT/NOTADB/FORMAT/SCHEMA → KernelCorruptionError
        if primary in (
            sqlite3.SQLITE_CORRUPT,
            sqlite3.SQLITE_NOTADB,
            getattr(sqlite3, 'SQLITE_FORMAT', 24),
            getattr(sqlite3, 'SQLITE_SCHEMA', 17),
        ):
            return KernelCorruptionError(str(exc))
        if primary in (
            sqlite3.SQLITE_FULL,
            sqlite3.SQLITE_IOERR,
            sqlite3.SQLITE_CANTOPEN,
            sqlite3.SQLITE_READONLY,
            sqlite3.SQLITE_PERM,
            sqlite3.SQLITE_AUTH,
        ):
            return KernelStorageError(str(exc))
    return KernelStorageError(str(exc))


def _safe_close(conn: sqlite3.Connection, *, active_exc: BaseException | None = None) -> None:
    """Close *conn*, translating SQLite errors.  If *active_exc* is set (or an
    exception is currently being handled) and close also fails, raise a combined
    KernelStorageError preserving both contexts.
    """
    import sys as _sys
    _existing = active_exc
    if _existing is None:
        _existing = _sys.exc_info()[1]
    try:
        conn.close()
    except sqlite3.Error as _ce:
        _classified = _translate_sqlite_error(_ce)
        if _existing is not None and _existing is not _ce:
            raise KernelStorageError(
                f"close failed ({type(_ce).__name__}: {_ce}) after original error: "
                f"{type(_existing).__name__}: {_existing}"
            ) from _existing
        raise _classified
    except Exception:
        raise

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXPECTED_TABLE_NAMES = frozenset({"interactions", "messages", "card_index"})
_EXPECTED_INDEX_NAMES = frozenset({"interactions_active_deadline_idx"})

# Columns for each table: (cid, name, type, notnull, dflt_value, pk, hidden)
_EXPECTED_INTERACTIONS_COLS = [
    (0, "event_id", "TEXT", 0, None, 1, 0),
    (1, "interaction_id", "TEXT", 1, None, 0, 0),
    (2, "aggregate_json", "TEXT", 1, None, 0, 0),
    (3, "state_version", "INTEGER", 1, None, 0, 0),
    (4, "phase", "TEXT", 1, None, 0, 0),
    (5, "terminal_status", "TEXT", 0, None, 0, 0),
    (6, "next_deadline_epoch", "INTEGER", 0, None, 0, 0),
    (7, "last_observed_at_epoch", "INTEGER", 1, None, 0, 0),
    (8, "created_at_epoch", "INTEGER", 1, None, 0, 0),
    (9, "updated_at_epoch", "INTEGER", 1, None, 0, 0),
    (10, "interaction_policy_json", "TEXT", 1, None, 0, 0),
]

_EXPECTED_MESSAGES_COLS = [
    (0, "kind", "TEXT", 1, None, 1, 0),
    (1, "message_id", "TEXT", 1, None, 2, 0),
    (2, "payload_sha256", "TEXT", 1, None, 0, 0),
    (3, "payload_json", "TEXT", 1, None, 0, 0),
    (4, "event_id", "TEXT", 1, None, 0, 0),
    (5, "result_json", "TEXT", 1, None, 0, 0),
    (6, "recorded_at_epoch", "INTEGER", 1, None, 0, 0),
]

_EXPECTED_CARD_INDEX_COLS = [
    (0, "card_id", "TEXT", 0, None, 1, 0),
    (1, "event_id", "TEXT", 1, None, 0, 0),
    (2, "revision", "INTEGER", 1, None, 0, 0),
]

_EXPECTED_ACTIVE_DEADLINE_COLS = [
    (0, "terminal_status", "TEXT", 0, None, 0, 0),
    (1, "next_deadline_epoch", "INTEGER", 0, None, 0, 0),
    (2, "event_id", "TEXT", 0, None, 0, 0),
]

# Private key set constants (re-exported from task_initiation_private)
_AGGREGATE_KEYS_V1 = p._AGGREGATE_KEYS_V1
_REVISION_KEYS_V1 = p._REVISION_KEYS_V1
_RESPONSE_PRIVATE_KEYS_V1 = p._RESPONSE_PRIVATE_KEYS_V1
_ACCEPTED_RESPONSE_KEYS_V1 = p._ACCEPTED_RESPONSE_KEYS_V1
_RESOLVED_TASK_VARIANTS = p._RESOLVED_TASK_VARIANTS
_VALID_RESOLUTION_REASONS = p._VALID_RESOLUTION_REASONS

_VALID_PHASES = frozenset({"awaiting_response", "observing", "queued", "preparing", "terminal"})
_VALID_TERMINAL_STATUSES = frozenset({
    "completed", "expired", "superseded", "refused", "failed",
})

_SCHEMA_DDL_STATEMENTS = [
    """CREATE TABLE interactions (
    event_id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL UNIQUE,
    aggregate_json TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    phase TEXT NOT NULL CHECK (phase IN ('awaiting_response','observing')),
    terminal_status TEXT CHECK (
        terminal_status IS NULL OR
        terminal_status IN ('completed','expired','superseded','refused','failed')
    ),
    next_deadline_epoch INTEGER CHECK (
        next_deadline_epoch IS NULL OR next_deadline_epoch > 0
    ),
    last_observed_at_epoch INTEGER NOT NULL CHECK (last_observed_at_epoch > 0),
    created_at_epoch INTEGER NOT NULL CHECK (created_at_epoch > 0),
    updated_at_epoch INTEGER NOT NULL CHECK (
        updated_at_epoch > 0 AND updated_at_epoch >= created_at_epoch
    ),
    interaction_policy_json TEXT NOT NULL
)""",
    """CREATE TABLE messages (
    kind TEXT NOT NULL CHECK (kind IN ('stuck','response')),
    message_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    payload_json TEXT NOT NULL,
    event_id TEXT NOT NULL
        REFERENCES interactions(event_id) ON DELETE CASCADE,
    result_json TEXT NOT NULL,
    recorded_at_epoch INTEGER NOT NULL CHECK (recorded_at_epoch > 0),
    PRIMARY KEY (kind, message_id)
)""",
    """CREATE TABLE card_index (
    card_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL
        REFERENCES interactions(event_id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK (revision > 0),
    UNIQUE (event_id, revision)
)""",
    """CREATE INDEX interactions_active_deadline_idx
    ON interactions(terminal_status, next_deadline_epoch, event_id)""",
]
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_uuid4(value: Any) -> bool:
    return isinstance(value, str) and bool(_UUID4_RE.match(value))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and bool(_SHA256_RE.match(value))


_sha256 = p._sha256


def _decode_aggregate_json(raw: str, *, source: str) -> dict[str, Any]:
    try:
        decoded = c._strict_json_loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise KernelCorruptionError(f"{source}: invalid aggregate_json: {exc}")
    if not isinstance(decoded, dict):
        raise KernelCorruptionError(f"{source}: aggregate is not a dict")
    # Reject non-finite numbers
    for val in _walk_values(decoded):
        if isinstance(val, float) and (val != val or val in (float("inf"), float("-inf"))):
            raise KernelCorruptionError(f"{source}: non-finite float in aggregate")
    return decoded


def _walk_values(obj: Any) -> Iterator[Any]:
    """Recursively yield every scalar value in a JSON-like structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_values(v)
    else:
        yield obj


def _decode_message_payload_json(raw: str, *, source: str) -> dict[str, Any]:
    try:
        decoded = c._strict_json_loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise KernelCorruptionError(f"{source}: invalid payload_json: {exc}")
    if not isinstance(decoded, dict):
        raise KernelCorruptionError(f"{source}: payload is not a dict")
    return decoded



def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise KernelCorruptionError(f"{field}: expected string, got {type(value).__name__}")
    return value


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise KernelCorruptionError(f"{field}: expected int, got {type(value).__name__}")
    return value


def _require_uuid4(value: Any, field: str) -> str:
    text = _require_str(value, field)
    if not _is_uuid4(text):
        raise KernelCorruptionError(f"{field}: invalid UUIDv4: {text!r}")
    return text


def _require_sha256(value: Any, field: str) -> str:
    text = _require_str(value, field)
    if not _is_sha256(text):
        raise KernelCorruptionError(f"{field}: invalid SHA-256: {text!r}")
    return text


def _require_phase(value: Any, field: str) -> str:
    text = _require_str(value, field)
    if text not in _VALID_PHASES:
        raise KernelCorruptionError(f"{field}: invalid phase: {text!r}")
    return text


def _require_terminal_status(value: Any, field: str) -> str | None:
    if value is None:
        return None
    text = _require_str(value, field)
    if text not in _VALID_TERMINAL_STATUSES:
        raise KernelCorruptionError(f"{field}: invalid terminal status: {text!r}")
    return text


def _require_optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, field)


def _require_positive_int(value: Any, field: str) -> int:
    v = _require_int(value, field)
    if v <= 0:
        raise KernelCorruptionError(f"{field}: must be positive, got {v}")
    return v


def _convert_evidence_issues(data: dict[str, Any]) -> dict[str, Any]:
    """Convert evidence_issues sets to sorted arrays for JSON encoding."""
    result = dict(data)
    if "evidence_issues" in result and isinstance(result["evidence_issues"], set):
        result["evidence_issues"] = sorted(result["evidence_issues"])
    if "revisions" in result:
        revisions = []
        for rev in result["revisions"]:
            r = dict(rev)
            if "evidence_issues" in r and isinstance(r["evidence_issues"], set):
                r["evidence_issues"] = sorted(r["evidence_issues"])
            revisions.append(r)
        result["revisions"] = revisions
    return result


def _restore_evidence_sets(data: dict[str, Any]) -> dict[str, Any]:
    """Restore evidence_issues from arrays back to sets for reducer compatibility.

    Validates every element is a string before calling set(), so malformed
    entries (objects, numbers, booleans, nested arrays) produce
    KernelCorruptionError rather than TypeError.
    """
    result = dict(data)
    if "evidence_issues" in result:
        if not isinstance(result["evidence_issues"], list):
            raise KernelCorruptionError("evidence_issues: expected list")
        for i, item in enumerate(result["evidence_issues"]):
            if not isinstance(item, str):
                raise KernelCorruptionError(
                    f"evidence_issues[{i}]: expected string, got {type(item).__name__}"
                )
        if len(set(result["evidence_issues"])) != len(result["evidence_issues"]):
            raise KernelCorruptionError("evidence_issues: duplicate entries")
        result["evidence_issues"] = set(result["evidence_issues"])
    if "revisions" in result:
        revisions = []
        for rev in result["revisions"]:
            r = dict(rev)
            if "evidence_issues" in r:
                if not isinstance(r["evidence_issues"], list):
                    raise KernelCorruptionError("revision evidence_issues: expected list")
                for i, item in enumerate(r["evidence_issues"]):
                    if not isinstance(item, str):
                        raise KernelCorruptionError(
                            f"revision evidence_issues[{i}]: expected string, got {type(item).__name__}"
                    )
                if len(set(r["evidence_issues"])) != len(r["evidence_issues"]):
                    raise KernelCorruptionError("revision evidence_issues: duplicate entries")
                r["evidence_issues"] = set(r["evidence_issues"])
            revisions.append(r)
        result["revisions"] = revisions
    return result


def _agg_from_db(raw: str, *, source: str) -> dict[str, Any]:
    decoded = _decode_aggregate_json(raw, source=source)
    return _restore_evidence_sets(decoded)


def _agg_to_db(aggregate: Mapping[str, Any]) -> str:
    converted = _convert_evidence_issues(dict(aggregate))
    canonical_bytes = c._canonical_json(converted)
    return canonical_bytes.decode("utf-8")


InteractionPolicy = p.InteractionPolicy

_interaction_policy_from_json = p._interaction_policy_from_json
_interaction_policy_to_json = p._interaction_policy_to_json
ValidatedBundle = p.ValidatedBundle

def _validate_aggregate_structure(
    aggregate: dict[str, Any], *, row_event_id: str | None = None
) -> None:
    """Exact version-1 aggregate validation: keys, types, coherence."""
    # Exact key set
    actual_keys = set(aggregate.keys())
    if actual_keys != _AGGREGATE_KEYS_V1:
        extra = actual_keys - _AGGREGATE_KEYS_V1
        missing = _AGGREGATE_KEYS_V1 - actual_keys
        msg_parts = []
        if extra:
            msg_parts.append(f"unexpected keys: {sorted(extra)}")
        if missing:
            msg_parts.append(f"missing keys: {sorted(missing)}")
        raise KernelCorruptionError("aggregate key mismatch: " + "; ".join(msg_parts))

    # Required UUIDs
    event_id = _require_uuid4(aggregate["event_id"], "aggregate.event_id")
    if row_event_id is not None and event_id != row_event_id:
        raise KernelCorruptionError(
            f"aggregate event_id {event_id} != row event_id {row_event_id}"
        )
    _require_uuid4(aggregate["interaction_id"], "aggregate.interaction_id")

    # State version
    sv = _require_positive_int(aggregate["state_version"], "aggregate.state_version")

    # Phase
    phase = _require_phase(aggregate["phase"], "aggregate.phase")

    # Terminal status
    ts = _require_terminal_status(aggregate.get("terminal_status"), "aggregate.terminal_status")

    # Epoch timestamps: all must be positive int or None
    epoch_fields = [
        "request_occurred_at_epoch", "request_received_at_epoch",
        "request_expires_at_epoch", "actionable_surface_proven_by_epoch",
        "first_response_at_epoch", "first_response_received_at_epoch",
        "start_at_epoch", "start_received_at_epoch",
        "observation_due_at_epoch", "terminal_at_epoch",
    ]
    for f in epoch_fields:
        v = aggregate.get(f)
        if v is None:
            continue
        _require_positive_int(v, f"aggregate.{f}")

    # Timestamp validity (no ordering requirement between occurred and received
    # because valid Stuck events may arrive with future-skewed occurred_at_epoch).
    # The ingress policy gate enforces the skew bound before persistence.
    ro = aggregate["request_occurred_at_epoch"]
    rr = aggregate["request_received_at_epoch"]
    re = aggregate["request_expires_at_epoch"]
    if not (ro < re and rr < re):
        raise KernelCorruptionError("aggregate: request timestamps invalid")

    # has_published_card
    if not isinstance(aggregate["has_published_card"], bool):
        raise KernelCorruptionError("aggregate.has_published_card: expected bool")

    # revisions must be a list
    revisions = aggregate.get("revisions")
    if not isinstance(revisions, list):
        raise KernelCorruptionError("aggregate.revisions: expected list")

    # current_revision
    cr = aggregate.get("current_revision")
    if revisions:
        if cr is None:
            raise KernelCorruptionError("aggregate: has revisions but current_revision is null")
        _require_positive_int(cr, "aggregate.current_revision")
        if cr != revisions[-1].get("revision"):
            raise KernelCorruptionError("aggregate: current_revision != last revision")
    else:
        if cr is not None:
            raise KernelCorruptionError("aggregate: current_revision set but no revisions")

    # Phase/terminal/reason coherence
    if ts is not None:
        if aggregate.get("resolution_reason") is None:
            raise KernelCorruptionError("aggregate: terminal without resolution_reason")
        if aggregate.get("terminal_at_epoch") is None:
            raise KernelCorruptionError("aggregate: terminal without terminal_at_epoch")
        if ts == "superseded" and aggregate.get("resolution_reason") != "task_changed":
            raise KernelCorruptionError("aggregate: superseded but not task_changed")

    # Nonterminal awaiting_response: must have a Card with expiry
    if ts is None and phase == "awaiting_response":
        if not revisions:
            raise KernelCorruptionError("aggregate: awaiting_response without revisions")
        last_rev = revisions[-1]
        if last_rev.get("response") is not None:
            raise KernelCorruptionError("aggregate: awaiting_response but last revision has response")
        card_expiry = last_rev.get("card_expires_at_epoch")
        if not isinstance(card_expiry, int) or card_expiry <= 0:
            raise KernelCorruptionError("aggregate: awaiting_response without valid card expiry")

    # Nonterminal observing: must have observation_due_at_epoch
    if ts is None and phase == "observing":
        obs = aggregate.get("observation_due_at_epoch")
        if not isinstance(obs, int) or obs <= 0:
            raise KernelCorruptionError("aggregate: observing without observation_due_at_epoch")

    # message_reservations must be dict
    if not isinstance(aggregate.get("message_reservations"), dict):
        raise KernelCorruptionError("aggregate.message_reservations: expected dict")

    # accepted_responses must be list
    if not isinstance(aggregate.get("accepted_responses"), list):
        raise KernelCorruptionError("aggregate.accepted_responses: expected list")

    # evidence_issues must be a set (restored from JSON arrays)
    ei = aggregate.get("evidence_issues")
    if not isinstance(ei, set):
        raise KernelCorruptionError("aggregate.evidence_issues: expected set")
    # resolved_task shape (varies by source: explicit, session, fallback)
    rt = aggregate.get("resolved_task")
    if rt is not None:
        if not isinstance(rt, dict):
            raise KernelCorruptionError("aggregate.resolved_task: expected dict")
        if "label" not in rt or "source" not in rt:
            raise KernelCorruptionError("aggregate.resolved_task: missing label or source")
        _require_str(rt.get("label"), "aggregate.resolved_task.label")
        _require_str(rt.get("source"), "aggregate.resolved_task.source")

    # task_fingerprint
    tf = aggregate.get("task_fingerprint")
    if tf is not None:
        _require_sha256(tf, "aggregate.task_fingerprint")

def _agg_for_output(aggregate: dict[str, Any]) -> dict[str, Any]:
    """Convert evidence_issues sets to sorted lists for JSON output."""
    return _convert_evidence_issues(aggregate)


def _validate_revision_contiguity(aggregate: dict[str, Any]) -> None:
    revisions = aggregate.get("revisions", [])
    if not revisions:
        return
    expected = 1
    for rev in revisions:
        if not isinstance(rev, dict):
            raise KernelCorruptionError("revision is not a dict")
        rev_num = _require_int(rev.get("revision"), "revision.revision")
        if rev_num != expected:
            raise KernelCorruptionError(
                f"noncontiguous revisions: expected {expected}, got {rev_num}"
            )
        expected += 1

    current = aggregate.get("current_revision")
    if revisions and current is not None:
        current = _require_int(current, "current_revision")
        last_rev = revisions[-1].get("revision")
        if current != last_rev:
            raise KernelCorruptionError(
                f"current_revision {current} != last revision {last_rev}"
            )


def _validate_card_index_correspondence(
    aggregate: dict[str, Any], card_rows: list[sqlite3.Row]
) -> None:
    """Verify every Card in aggregate has a card_index row and vice versa."""
    agg_card_ids = set()
    for rev in aggregate.get("revisions", []):
        card_id = rev.get("card_id")
        if card_id:
            agg_card_ids.add((card_id, rev["revision"]))

    db_card_ids = set()
    for row in card_rows:
        db_card_ids.add((row["card_id"], row["revision"]))

    if agg_card_ids != db_card_ids:
        only_agg = agg_card_ids - db_card_ids
        only_db = db_card_ids - agg_card_ids
        msg_parts = []
        if only_agg:
            msg_parts.append(f"in aggregate but not card_index: {only_agg}")
        if only_db:
            msg_parts.append(f"in card_index but not aggregate: {only_db}")
        raise KernelCorruptionError("card_index mismatch: " + "; ".join(msg_parts))


# ---------------------------------------------------------------------------
# Focused validators (Defect 4 consolidation)
# ---------------------------------------------------------------------------


def _validate_aggregate_v1(
    aggregate: dict[str, Any], int_row: sqlite3.Row
) -> None:
    """Validate aggregate shape after structural checks pass.

    Requires: _validate_aggregate_structure already passed.
    Checks: durable phases, non-null invariants, derived column agreement,
    timestamp coherence, task_fingerprint, canonical encoding.
    """
    event_id = aggregate["event_id"]

    # --- Derived column agreement ---
    if aggregate["interaction_id"] != int_row["interaction_id"]:
        raise KernelCorruptionError(
            f"interaction {event_id}: aggregate interaction_id "
            f"{aggregate['interaction_id']} != row interaction_id {int_row['interaction_id']}"
        )
    if aggregate["state_version"] != int_row["state_version"]:
        raise KernelCorruptionError(
            f"interaction {event_id}: aggregate state_version {aggregate['state_version']} "
            f"!= row state_version {int_row['state_version']}"
        )
    if aggregate["phase"] != int_row["phase"]:
        raise KernelCorruptionError(
            f"interaction {event_id}: phase mismatch"
        )
    if aggregate.get("terminal_status") != int_row["terminal_status"]:
        raise KernelCorruptionError(
            f"interaction {event_id}: terminal_status mismatch"
        )

    # --- Interaction policy snapshot ---
    policy_json = int_row["interaction_policy_json"]
    policy = _interaction_policy_from_json(policy_json)
    skew_bound = policy.max_future_skew_seconds
    ro = aggregate["request_occurred_at_epoch"]
    rr = aggregate["request_received_at_epoch"]
    if ro > rr + skew_bound:
        raise KernelCorruptionError(
            f"interaction {event_id}: request_occurred_at_epoch {ro} exceeds "
            f"received_at {rr} + skew bound {skew_bound}"
        )

    # --- SQL scalar types ---
    for col in ("created_at_epoch", "updated_at_epoch", "last_observed_at_epoch"):
        v = int_row[col]
        if isinstance(v, bool) or not isinstance(v, int):
            raise KernelCorruptionError(
                f"interaction {event_id}: {col} expected int, got {type(v).__name__}"
            )
    ndl = int_row["next_deadline_epoch"]
    if ndl is not None and (isinstance(ndl, bool) or not isinstance(ndl, int)):
        raise KernelCorruptionError(
            f"interaction {event_id}: next_deadline_epoch expected int or null, got {type(ndl).__name__}"
        )

    # --- SQL timestamp coherence ---
    created = int_row["created_at_epoch"]
    updated = int_row["updated_at_epoch"]
    last_obs = int_row["last_observed_at_epoch"]
    if created != rr:
        raise KernelCorruptionError(
            f"interaction {event_id}: created_at_epoch {created} != request_received_at_epoch {rr}"
        )
    if updated < created:
        raise KernelCorruptionError(
            f"interaction {event_id}: updated_at_epoch {updated} < created_at_epoch {created}"
        )
    if updated < last_obs:
        raise KernelCorruptionError(
            f"interaction {event_id}: updated_at_epoch {updated} < last_observed_at_epoch {last_obs}"
        )
    if last_obs < created:
        raise KernelCorruptionError(
            f"interaction {event_id}: last_observed_at_epoch {last_obs} < created_at_epoch {created}"
        )

    # --- Defect 5: durable phase check ---
    _DURABLE_PHASES = frozenset({"awaiting_response", "observing", "terminal"})
    phase = aggregate["phase"]
    if phase not in _DURABLE_PHASES:
        raise KernelCorruptionError(
            f"interaction {event_id}: non-durable phase persisted: {phase}"
        )

    # --- Defect 5: committed aggregate invariants ---
    if not aggregate.get("has_published_card"):
        raise KernelCorruptionError(
            f"interaction {event_id}: has_published_card is not True"
        )
    revisions = aggregate.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise KernelCorruptionError(
            f"interaction {event_id}: revisions is empty or missing"
        )
    cr = aggregate.get("current_revision")
    if cr is None or not isinstance(cr, int) or cr != revisions[-1].get("revision"):
        raise KernelCorruptionError(
            f"interaction {event_id}: current_revision does not equal last revision"
        )
    if aggregate.get("latest_error") is not None:
        raise KernelCorruptionError(
            f"interaction {event_id}: latest_error is not null"
        )

    # --- Defect 5: resolved_task is non-null ---
    rt = aggregate.get("resolved_task")
    if rt is None:
        raise KernelCorruptionError(
            f"interaction {event_id}: resolved_task is null"
        )
    if not isinstance(rt, dict):
        raise KernelCorruptionError(
            f"interaction {event_id}: resolved_task is not a dict"
        )
    source = rt.get("source")
    if source not in _RESOLVED_TASK_VARIANTS:
        raise KernelCorruptionError(
            f"interaction {event_id}: unknown resolved_task source {source!r}"
        )
    expected_keys = _RESOLVED_TASK_VARIANTS[source]
    actual_keys = set(rt.keys())
    if actual_keys != expected_keys:
        extra = actual_keys - expected_keys
        missing = expected_keys - actual_keys
        parts = []
        if extra:
            parts.append(f"extra: {sorted(extra)}")
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        raise KernelCorruptionError(
            f"interaction {event_id}: resolved_task ({source}) key mismatch: " + "; ".join(parts)
        )

    # --- Defect 5: task_fingerprint is non-null and verified ---
    tf = aggregate.get("task_fingerprint")
    if tf is None:
        raise KernelCorruptionError(
            f"interaction {event_id}: task_fingerprint is null"
        )
    computed = c.task_fingerprint(rt)
    if tf != computed:
        raise KernelCorruptionError(
            f"interaction {event_id}: task_fingerprint mismatch"
        )

    # --- Canonical encoding check ---
    stored_agg_json = int_row["aggregate_json"]
    recanonical_agg = _agg_to_db(aggregate)
    if stored_agg_json != recanonical_agg:
        raise KernelCorruptionError(
            f"interaction {event_id}: aggregate_json not canonical"
        )


def _validate_revision_v1(aggregate: dict[str, Any], *, policy: InteractionPolicy) -> None:
    """Validate revision key sets, lineage, Milestone 2 defaults, private Response records."""
    event_id = aggregate["event_id"]
    revisions = aggregate.get("revisions", [])
    ts = aggregate.get("terminal_status")

    for rev in revisions:
        rev_num = rev["revision"]

        # --- Exact key set ---
        actual_keys = set(rev.keys())
        if actual_keys != _REVISION_KEYS_V1:
            extra = actual_keys - _REVISION_KEYS_V1
            missing = _REVISION_KEYS_V1 - actual_keys
            parts = []
            if extra:
                parts.append(f"extra: {sorted(extra)}")
            if missing:
                parts.append(f"missing: {sorted(missing)}")
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: revision key mismatch: " + "; ".join(parts)
            )

        # --- Defect 7: Milestone 2 defaults ---
        if rev.get("receipt") is not None:
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: receipt must be null (no Receipt support)"
            )
        if rev.get("receipt_payload_sha256") is not None:
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: receipt_payload_sha256 must be null"
            )
        if rev.get("card_posted_at_epoch") is not None:
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: card_posted_at_epoch must be null"
            )
        if rev.get("delivery_evidence") != "none":
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: delivery_evidence must be 'none'"
            )
        if rev.get("delivery_occurred_at_epoch") is not None:
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: delivery_occurred_at_epoch must be null"
            )

        # --- Defect 7: Committed invariants (non-null for every revision) ---
        for field in ("context_id", "context", "proposal", "proposal_sha256",
                      "task_fingerprint", "card_id", "card",
                      "card_issued_at_epoch", "card_expires_at_epoch"):
            if rev.get(field) is None:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: {field} is null"
                )

        # --- Defect 7: Response/hash symmetry ---
        resp_val = rev.get("response")
        rps_val = rev.get("response_payload_sha256")
        if (resp_val is None) != (rps_val is None):
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: response and response_payload_sha256 "
                f"must be both null or both non-null"
            )

        # --- UUID validation ---
        _require_uuid4(rev["card_id"], f"revision {rev_num}.card_id")
        _require_uuid4(rev["context_id"], f"revision {rev_num}.context_id")

        # --- Hash validation ---
        _require_sha256(rev["proposal_sha256"], f"revision {rev_num}.proposal_sha256")
        if rps_val is not None:
            _require_sha256(rps_val, f"revision {rev_num}.response_payload_sha256")

        # --- Timestamp validation ---
        _require_positive_int(rev["card_issued_at_epoch"], f"revision {rev_num}.card_issued_at_epoch")
        _require_positive_int(rev["card_expires_at_epoch"], f"revision {rev_num}.card_expires_at_epoch")

        # --- task_fingerprint must match aggregate ---
        if rev.get("task_fingerprint") is not None:
            if rev["task_fingerprint"] != aggregate.get("task_fingerprint"):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: revision.task_fingerprint mismatch"
                )
        # --- Load embedded objects ---
        ctx = rev.get("context")
        prop = rev.get("proposal")
        card_obj = rev.get("card")
        resp = rev.get("response")

        # --- Embedded public contracts (Defect 17: wrap in KernelCorruptionError) ---
        if ctx is not None:
            try:
                c.validate_context(ctx)
            except c.TaskInitiationContractError as exc:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: invalid context: {exc}"
                )

        # --- Defect 8: Exact Context boundaries ---
        if ctx is not None:
            df = ctx.get("disclosed_facts")
            if not isinstance(df, dict):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.disclosed_facts not a dict"
                )
            # project_summary, session_capsule must be null
            if df.get("project_summary") is not None:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.disclosed_facts.project_summary must be null"
                )
            if df.get("session_capsule") is not None:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.disclosed_facts.session_capsule must be null"
                )
            # recent_interactions, helper_material must be empty lists
            if df.get("recent_interactions") != []:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.disclosed_facts.recent_interactions must be []"
                )
            if df.get("helper_material") != []:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.disclosed_facts.helper_material must be []"
                )
            # omissions must be empty list
            if ctx.get("omissions") != []:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.omissions must be []"
                )
            # source_ref_sha256 equals task_fingerprint
            srs = ctx.get("source_ref_sha256")
            if srs is not None:
                if aggregate.get("task_fingerprint") is not None and srs != aggregate["task_fingerprint"]:
                    raise KernelCorruptionError(
                    )
            # No absolute source paths in context
            try:
                c._reject_absolute_paths(ctx, f"interaction {event_id} r{rev_num}.context")
            except c.TaskInitiationContractError as exc:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context contains absolute path: {exc}"
                )
            # Context timing: generated_at_epoch + ttl == expires_at_epoch
            gen = ctx.get("generated_at_epoch")
            exp = ctx.get("expires_at_epoch")
            if isinstance(gen, int) and not isinstance(gen, bool) and isinstance(exp, int) and not isinstance(exp, bool):
                if exp <= gen:
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: context expires_at_epoch {exp} <= generated_at_epoch {gen}"
                    )

        if prop is not None:
            try:
                c.validate_proposal(prop)
            except c.TaskInitiationContractError as exc:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: invalid proposal: {exc}"
                )

        if card_obj is not None:
            try:
                c.validate_card(card_obj)
            except c.TaskInitiationContractError as exc:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: invalid card: {exc}"
                )
        if resp is not None:
            resp_keys = set(resp.keys())
            if resp_keys != _RESPONSE_PRIVATE_KEYS_V1:
                extra = resp_keys - _RESPONSE_PRIVATE_KEYS_V1
                missing = _RESPONSE_PRIVATE_KEYS_V1 - resp_keys
                parts = []
                if extra:
                    parts.append(f"extra: {sorted(extra)}")
                if missing:
                    parts.append(f"missing: {sorted(missing)}")
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: response key mismatch: " + "; ".join(parts)
                )
            # Public portion passes validate_response
            public_resp = {
                k: v for k, v in resp.items()
                if k in ("schema_version", "response_id", "card_id",
                         "action", "detail", "occurred_at_epoch")
            }
            try:
                c.validate_response(public_resp)
            except c.TaskInitiationContractError as exc:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: invalid response: {exc}"
                )
            # response_id is UUIDv4
            _require_uuid4(resp["response_id"], f"revision {rev_num}.response.response_id")
            # card_id equals revision card_id
            if resp["card_id"] != rev["card_id"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: response.card_id != revision.card_id"
                )
            # received_at_epoch is positive int
            _require_positive_int(resp["received_at_epoch"], f"revision {rev_num}.response.received_at_epoch")
            # occurred_at_epoch_usable is bool (not int or string)
            oeu = resp.get("occurred_at_epoch_usable")
            if not isinstance(oeu, bool):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: occurred_at_epoch_usable must be bool, "
                    f"got {type(oeu).__name__}"
                )
            # response_payload_sha256 equals c._payload_sha256(public_response)
            computed_rps = c._payload_sha256(public_resp)
            if rps_val is not None and rps_val != computed_rps:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: response_payload_sha256 mismatch"
                )
            # Defect 10: occurred_at_epoch_usable computed from card timestamps + skew
            card_issued = rev["card_issued_at_epoch"]
            card_expires = rev["card_expires_at_epoch"]
            occurred = resp["occurred_at_epoch"]
            received_at = resp["received_at_epoch"]
            usable = (
                card_issued <= occurred < card_expires
                and occurred <= received_at + policy.max_future_skew_seconds
            )
            if oeu != usable:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: occurred_at_epoch_usable={oeu} "
                    f"but card window [{card_issued}, {card_expires}] skew={policy.max_future_skew_seconds} => {usable}"
                )

        # --- Defect 10: Evidence issues per revision ---
        # response_timestamp_inconsistent present iff occurred_at_epoch_usable is false.
        # Treat None as an empty issue set for the purposes of the iff check.
        rev_ei = rev.get("evidence_issues")
        if rev_ei is not None and not isinstance(rev_ei, set):
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: evidence_issues expected set or null, "
                f"got {type(rev_ei).__name__}"
            )
        effective_issues: set[str] = set() if rev_ei is None else rev_ei
        for issue in effective_issues:
            if not isinstance(issue, str):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: evidence_issue not a string: {issue!r}"
                )
            if issue != "response_timestamp_inconsistent":
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: unknown evidence_issue: {issue!r}"
                )
        has_inconsistent = "response_timestamp_inconsistent" in effective_issues
        should_have = resp is not None and resp.get("occurred_at_epoch_usable") is False
        if has_inconsistent != should_have:
            raise KernelCorruptionError(
                f"interaction {event_id} r{rev_num}: evidence_issues "
                f"has_inconsistent={has_inconsistent} should_have={should_have}"
            )

        # --- Cross-object semantic bindings ---
        # Context bindings
        if ctx is not None:
            if ctx.get("interaction_id") != aggregate["interaction_id"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.interaction_id mismatch"
                )
            if ctx.get("revision") != rev_num:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.revision mismatch"
                )
            if aggregate.get("terminal_status") != "superseded":
                if ctx.get("task_fingerprint") != aggregate.get("task_fingerprint"):
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: context.task_fingerprint mismatch"
                    )
            if rev.get("task_fingerprint") is not None and ctx.get("task_fingerprint") != rev["task_fingerprint"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context.task_fingerprint != revision.task_fingerprint"
                )
            if ctx is not None and rev.get("context_id") is not None:
                if rev["context_id"] != ctx.get("context_id"):
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: context_id mismatch"
                    )

        # Card bindings
        if card_obj is not None:
            if card_obj.get("interaction_id") != aggregate["interaction_id"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.interaction_id mismatch"
                )
            if card_obj.get("revision") != rev_num:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.revision mismatch"
                )
            if rev.get("card_id") is not None and card_obj.get("card_id") is not None:
                if rev["card_id"] != card_obj.get("card_id"):
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: card_id mismatch"
                    )
            # Card timestamps match revision fields
            if card_obj.get("issued_at_epoch") != rev["card_issued_at_epoch"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.issued_at_epoch != card_issued_at_epoch"
                )
            if card_obj.get("expires_at_epoch") != rev["card_expires_at_epoch"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.expires_at_epoch != card_expires_at_epoch"
                )

        # Proposal-Card cross-validation
        if prop is not None and card_obj is not None:
            if card_obj.get("blocker") != prop.get("blocker"):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.blocker != proposal.blocker"
                )
            if card_obj.get("tiny_start") != prop.get("tiny_start"):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: card.tiny_start != proposal.tiny_start"
                )
            stored_ps = rev.get("proposal_sha256")
            expected_ps = c._payload_sha256(prop)
            if stored_ps != expected_ps:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: proposal_sha256 mismatch"
                )
            # Defect 9: start_countdown_seconds derived from proposal
            ts_obj = prop.get("tiny_start", {})
            if isinstance(ts_obj, dict):
                est_min = ts_obj.get("estimated_minutes")
                if isinstance(est_min, int) and not isinstance(est_min, bool) and est_min > 0:
                    cap = policy.start_countdown_seconds_cap
                    expected_sd = min(est_min * 60, cap)
                    actual_sd = card_obj.get("start_countdown_seconds")
                    if actual_sd != expected_sd:
                        raise KernelCorruptionError(
                            f"interaction {event_id} r{rev_num}: start_countdown_seconds "
                            f"{actual_sd} != expected {expected_sd}"
                        )
        # Response card_id binding
        if resp is not None and rev.get("card_id") is not None:
            if resp.get("card_id") != rev["card_id"]:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: response.card_id != revision.card_id"
                )

    # ================================================================
    # Defect 8: Revision/action lineage (performed after per-revision loop)
    # ================================================================
    if not revisions:
        return

    for i, rev in enumerate(revisions):
        rev_num = rev["revision"]
        resp = rev.get("response")
        is_last = (i == len(revisions) - 1)

        if is_last:
            # Last revision rules
            if ts is None and aggregate["phase"] == "awaiting_response":
                # Nonterminal awaiting_response: last revision must be unanswered
                if resp is not None:
                    raise KernelCorruptionError(
                        f"interaction {event_id}: awaiting_response but last revision r{rev_num} has response"
                    )
            if ts is None and aggregate["phase"] == "observing":
                # Nonterminal observing: must have accepted Start and no later Card
                if resp is not None and resp.get("action") != "start":
                    raise KernelCorruptionError(
                        f"interaction {event_id}: observing but last revision r{rev_num} "
                        f"has non-Start response"
                    )
        else:
            # Not the last revision: must have an accepted response
            if resp is None:
                raise KernelCorruptionError(
                    f"interaction {event_id}: non-last revision r{rev_num} has no response"
                )
            action = resp.get("action")

            # Defect 8: Start/Defer/Dismiss cannot have later revision
            if action in ("start", "defer", "dismiss"):
                raise KernelCorruptionError(
                    f"interaction {event_id}: r{rev_num} action={action} but has later revision"
                )

            # Defect 8: Revision-limit Shrink/Blocked cannot have later revision
            # (These terminate at the revision ceiling. If there IS a later revision,
            # it wasn't the ceiling.)
            # Actually: revision-ceiling Shrink/Blocked means no more revisions.
            # If there's a next revision, it wasn't ceiling; this is fine.
            # But per the reducer, shrink_limit_reached and blocked_unresolved
            # are terminal and have no later revision. Since we're in the non-last
            # case here, we just need to verify the action is shrink/blocked
            # (acceptable for intermediate revisions).
            if action not in ("shrink", "blocked"):
                raise KernelCorruptionError(
                    f"interaction {event_id}: r{rev_num} action={action} does not allow "
                    f"later revision"
                )

    # Defect 8: Revision n with next revision must have accepted shrink/blocked Response
    # Nonterminal awaiting_response must have unanswered last revision
    if ts is None and aggregate["phase"] == "awaiting_response":
        if revisions[-1].get("response") is not None:
            raise KernelCorruptionError(
                f"interaction {event_id}: nonterminal awaiting_response but last revision "
                f"r{revisions[-1]['revision']} has response"
            )

    # Defect 8: Nonterminal observing must have accepted Start and no later Card
    if ts is None and aggregate["phase"] == "observing":
        start_found = False
        for rev in revisions:
            resp = rev.get("response")
            if resp is not None and resp.get("action") == "start":
                start_found = True
                # Must be the last revision with a response
                if rev["revision"] != revisions[-1]["revision"]:
                    raise KernelCorruptionError(
                        f"interaction {event_id}: Start accepted at r{rev['revision']} "
                        f"but not the last revision r{revisions[-1]['revision']}"
                    )
                break
        if not start_found:
            raise KernelCorruptionError(
                f"interaction {event_id}: observing without accepted Start"
            )
    # Defect 8: Unique Context IDs across revisions
    ctx_ids: list[str] = []
    for rev in revisions:
        cid = rev.get("context_id")
        if cid is not None:
            if cid in ctx_ids:
                raise KernelCorruptionError(
                    f"interaction {event_id}: duplicate context_id {cid}"
                )
            ctx_ids.append(cid)

    # Defect 8: Followup lineage (validated in _validate_preparation_lineage_v1)

def _validate_preparation_lineage_v1(
    aggregate: dict[str, Any],
    *,
    policy: InteractionPolicy,
) -> None:
    """Validate deterministic-preparation lineage invariants."""
    event_id = aggregate["event_id"]
    revisions = aggregate.get("revisions", [])
    task_fp = aggregate.get("task_fingerprint")
    ctx_ttl = policy.context_ttl_seconds
    card_ttl = policy.card_ttl_seconds

    for i, rev in enumerate(revisions):
        rev_num = rev["revision"]
        ctx = rev.get("context")
        card_obj = rev.get("card")

        # --- Context/Card TTL binding ---
        if ctx is not None and isinstance(ctx, dict):
            gen = ctx.get("generated_at_epoch")
            exp_ep = ctx.get("expires_at_epoch")
            if isinstance(gen, int) and not isinstance(gen, bool) and isinstance(exp_ep, int) and not isinstance(exp_ep, bool):
                if exp_ep != gen + ctx_ttl:
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: context expiry mismatch"
                    )
            cv = ctx.get("policy_version")
            if cv != c.CONTEXT_POLICY_VERSION:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: context policy_version mismatch"
                )

        if card_obj is not None and isinstance(card_obj, dict):
            issued = card_obj.get("issued_at_epoch")
            expires = card_obj.get("expires_at_epoch")
            if isinstance(issued, int) and not isinstance(issued, bool) and isinstance(expires, int) and not isinstance(expires, bool):
                if expires != issued + card_ttl:
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: card expiry mismatch"
                    )

        # --- Provenance binding ---
        if ctx is not None and isinstance(ctx, dict):
            provenance = ctx.get("provenance")
            if not isinstance(provenance, list) or len(provenance) != 1:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: provenance must be list of 1"
                )
            entry = provenance[0]
            if not isinstance(entry, dict):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: provenance[0] not dict"
                )
            if entry.get("category") != "task":
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: provenance category not task"
                )
            entry_srs = entry.get("source_ref_sha256")
            ctx_tf = ctx.get("task_fingerprint")
            if entry_srs != ctx_tf:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: provenance source_ref mismatch"
                )
            if task_fp is not None and entry_srs != task_fp:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: provenance source_ref != aggregate fp"
                )
            gen_val = ctx.get("generated_at_epoch")
            exp_val = ctx.get("expires_at_epoch")
            if isinstance(gen_val, int) and not isinstance(gen_val, bool):
                if entry.get("observed_at_epoch") != gen_val:
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: provenance observed_at_epoch mismatch"
                    )
            if isinstance(exp_val, int) and not isinstance(exp_val, bool):
                if entry.get("fresh_until_epoch") != exp_val:
                    raise KernelCorruptionError(
                        f"interaction {event_id} r{rev_num}: provenance fresh_until_epoch mismatch"
                    )

        # --- Follow-up lineage ---
        df = ctx.get("disclosed_facts", {}) if (ctx is not None and isinstance(ctx, dict)) else {}
        followup = df.get("followup")
        if i == 0:
            if followup is not None:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: initial followup must be null"
                )
        else:
            prev_resp = revisions[i - 1].get("response")
            if prev_resp is None:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: no preceding response"
                )
            prev_action = prev_resp.get("action")
            if prev_action not in ("shrink", "blocked"):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: preceding action not shrink/blocked"
                )
            if not isinstance(followup, dict):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: followup must be dict"
                )
            if followup.get("action") != prev_action:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: followup.action mismatch"
                )
            if followup.get("detail") != prev_resp.get("detail"):
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: followup.detail mismatch"
                )
            prev_card = revisions[i - 1].get("card")
            expected_pts = prev_card.get("tiny_start", {}).get("instruction") if isinstance(prev_card, dict) else None
            if followup.get("prior_tiny_start") != expected_pts:
                raise KernelCorruptionError(
                    f"interaction {event_id} r{rev_num}: followup.prior_tiny_start mismatch"
                )


def _validate_resolved_task_origin_v1(
    *,
    stuck_payload: Mapping[str, Any],
    aggregate: Mapping[str, Any],
) -> None:
    """Validate that persisted resolved_task is bound to the immutable Stuck event."""
    event_id = aggregate["event_id"]
    validated_stuck = c.validate_stuck_event(stuck_payload)
    resolved_task = aggregate.get("resolved_task")
    if not isinstance(resolved_task, dict):
        raise KernelCorruptionError(
            f"interaction {event_id}: resolved_task is not a dict"
        )
    rt_source = resolved_task.get("source")
    stuck_task_ref = validated_stuck.get("task_ref")

    # A. Stuck contains an explicit TaskRef
    if stuck_task_ref is not None:
        if rt_source != "explicit_task_ref":
            raise KernelCorruptionError(
                f"interaction {event_id}: resolved_task.source is {rt_source!r} "
                f"but immutable Stuck has an explicit task_ref"
            )
        rt_task_ref = resolved_task.get("task_ref")
        stuck_ref = stuck_task_ref["ref"]
        if rt_task_ref != stuck_ref:
            raise KernelCorruptionError(
                f"interaction {event_id}: resolved_task.task_ref {rt_task_ref!r} "
                f"!= immutable Stuck task_ref {stuck_ref!r}"
            )
        return

    # B. Stuck does NOT contain an explicit TaskRef
    if rt_source == "explicit_task_ref":
        raise KernelCorruptionError(
            f"interaction {event_id}: resolved_task.source is explicit_task_ref "
            f"but immutable Stuck has no task_ref"
        )

    # C. Fallback-description source
    if rt_source == "fallback_description":
        rt_label = resolved_task.get("label")
        stuck_desc = validated_stuck.get("task_description")
        if rt_label != stuck_desc:
            raise KernelCorruptionError(
                f"interaction {event_id}: resolved_task.label {rt_label!r} "
                f"!= immutable Stuck task_description {stuck_desc!r}"
            )

    # D. Active-session source: Stuck must have no explicit TaskRef (already ensured above)

def _validate_response_evidence_v1(aggregate: dict[str, Any]) -> None:
    """Validate accepted_responses, evidence issues, and derived timestamps."""
    event_id = aggregate["event_id"]
    revisions = aggregate.get("revisions", [])

    # Build list from revision responses
    accepted_from_revisions: list[dict[str, Any]] = []
    for rev in revisions:
        resp = rev.get("response")
        if resp is not None:
            accepted_from_revisions.append({
                "response_id": resp["response_id"],
                "card_id": resp["card_id"],
                "action": resp["action"],
                "detail": resp.get("detail"),
                "revision": rev["revision"],
                "received_at_epoch": resp["received_at_epoch"],
                "occurred_at_epoch": resp.get("occurred_at_epoch"),
                "evidence_issues": rev.get("evidence_issues"),
            })

    ar = aggregate.get("accepted_responses", [])
    if not isinstance(ar, list):
        raise KernelCorruptionError(f"interaction {event_id}: accepted_responses is not a list")

    # Defect 11: 1:1 correspondence
    if len(ar) != len(accepted_from_revisions):
        raise KernelCorruptionError(
            f"interaction {event_id}: accepted_responses count {len(ar)} != "
            f"revision responses {len(accepted_from_revisions)}"
        )

    for i, entry in enumerate(ar):
        if not isinstance(entry, dict):
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_responses[{i}] is not a dict, "
                f"got {type(entry).__name__}"
            )
        # Exact key set
        entry_keys = set(entry.keys())
        if entry_keys != _ACCEPTED_RESPONSE_KEYS_V1:
            extra = entry_keys - _ACCEPTED_RESPONSE_KEYS_V1
            missing = _ACCEPTED_RESPONSE_KEYS_V1 - entry_keys
            parts = []
            if extra:
                parts.append(f"extra: {sorted(extra)}")
            if missing:
                parts.append(f"missing: {sorted(missing)}")
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}] key mismatch: " + "; ".join(parts)
            )
        # Validate scalar types
        for fld, require_str in [("response_id", True), ("card_id", True), ("user_action", True), ("detail", False)]:
            v = entry.get(fld)
            if require_str:
                if isinstance(v, bool) or not isinstance(v, str):
                    raise KernelCorruptionError(
                        f"interaction {event_id}: accepted_response[{i}].{fld} must be string, "
                        f"got {type(v).__name__}"
                    )
            else:
                if v is not None and (isinstance(v, bool) or not isinstance(v, str)):
                    raise KernelCorruptionError(
                        f"interaction {event_id}: accepted_response[{i}].{fld} must be string or null, "
                        f"got {type(v).__name__}"
                    )
        rev_val = entry.get("revision")
        if isinstance(rev_val, bool) or not isinstance(rev_val, int) or rev_val <= 0:
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}].revision must be positive int, "
                f"got {type(rev_val).__name__}"
            )
        expected = accepted_from_revisions[i]
        if entry["response_id"] != expected["response_id"]:
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}] response_id mismatch"
            )
        if entry["card_id"] != expected["card_id"]:
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}] card_id mismatch"
            )
        if entry["user_action"] != expected["action"]:
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}] user_action mismatch"
            )
        if entry["revision"] != expected["revision"]:
            raise KernelCorruptionError(
                f"interaction {event_id}: accepted_response[{i}] revision mismatch"
            )

    # Defect 12: Aggregate evidence timestamps
    # Derive from revision Responses
    if accepted_from_revisions:
        # first_response_at_epoch: first response's occurred_at_epoch
        # first_response_received_at_epoch: first response's received_at_epoch
        first_resp = accepted_from_revisions[0]
        fr_expected = first_resp.get("occurred_at_epoch")
        frr_expected = first_resp["received_at_epoch"]

        # actionable_surface_proven_by_epoch: first response's occurred_at or received_at
        asp_expected_a = first_resp.get("occurred_at_epoch")
        asp_expected_b = first_resp["received_at_epoch"]

        fr = aggregate.get("first_response_at_epoch")
        frr = aggregate.get("first_response_received_at_epoch")
        asp = aggregate.get("actionable_surface_proven_by_epoch")

        if fr_expected is not None and fr is not None and fr != fr_expected:
            raise KernelCorruptionError(
                f"interaction {event_id}: first_response_at_epoch {fr} != {fr_expected}"
            )
        if frr is not None and frr != frr_expected:
            raise KernelCorruptionError(
                f"interaction {event_id}: first_response_received_at_epoch {frr} != {frr_expected}"
            )
        if asp is not None and asp not in (asp_expected_a, asp_expected_b):
            raise KernelCorruptionError(
                f"interaction {event_id}: actionable_surface_proven_by_epoch {asp} "
                f"not in ({asp_expected_a}, {asp_expected_b})"
            )

    # start_at_epoch / start_received_at_epoch
    for entry in accepted_from_revisions:
        if entry["action"] == "start":
            sa = aggregate.get("start_at_epoch")
            sr = aggregate.get("start_received_at_epoch")
            if sa is not None:
                expected_sa = entry.get("occurred_at_epoch")
                if expected_sa is not None and sa != expected_sa:
                    raise KernelCorruptionError(
                        f"interaction {event_id}: start_at_epoch {sa} != {expected_sa}"
                    )
            if sr is not None and sr != entry["received_at_epoch"]:
                raise KernelCorruptionError(
                    f"interaction {event_id}: start_received_at_epoch {sr} != {entry['received_at_epoch']}"
                )
            break

    # Defect 10: Aggregate evidence_issues equals union of revision evidence_issues
    agg_ei = aggregate.get("evidence_issues")
    expected_ei: set[str] = set()
    for entry in accepted_from_revisions:
        rev_ei = entry.get("evidence_issues")
        if rev_ei is not None:
            expected_ei |= rev_ei
    if agg_ei != expected_ei:
        raise KernelCorruptionError(
            f"interaction {event_id}: aggregate evidence_issues {agg_ei} != "
            f"union of revision evidence_issues {expected_ei}"
        )


def _validate_message_set_v1(
    store: "TaskInitiationStore",
    conn: sqlite3.Connection,
    event_id: str,
    aggregate: dict[str, Any],
) -> None:
    """Validate message multiplicity, payload identity, bidirectional reservation."""
    messages = conn.execute(
        "SELECT * FROM messages WHERE event_id = ?", (event_id,)
    ).fetchall()

    # --- Defect 13: Message multiplicity ---
    stuck_count = 0
    response_counts: dict[str, int] = {}  # response_id -> count

    for msg_row in messages:
        kind = msg_row["kind"]
        message_id = msg_row["message_id"]
        if kind == "stuck":
            stuck_count += 1
        elif kind == "response":
            response_counts[message_id] = response_counts.get(message_id, 0) + 1
        else:
            raise KernelCorruptionError(
                f"interaction {event_id}: unknown message kind {kind!r}"
            )

    # Exactly one Stuck message
    if stuck_count != 1:
        raise KernelCorruptionError(
            f"interaction {event_id}: expected exactly 1 stuck message, got {stuck_count}"
        )

    # Each accepted revision Response has exactly one SQL Response message
    revisions = aggregate.get("revisions", [])
    accepted_response_ids: set[str] = set()
    for rev in revisions:
        resp = rev.get("response")
        if resp is not None:
            accepted_response_ids.add(resp["response_id"])

    ts = aggregate.get("terminal_status")
    rr_val = aggregate.get("resolution_reason")

    # Count accepted Response messages
    accepted_msg_count = sum(
        1 for rid, cnt in response_counts.items() if rid in accepted_response_ids
    )
    if accepted_msg_count != len(accepted_response_ids):
        raise KernelCorruptionError(
            f"interaction {event_id}: expected {len(accepted_response_ids)} accepted "
            f"response messages, got {accepted_msg_count}"
        )

    # At most one superseding Response, only when aggregate is superseded/task_changed
    superseded_ids = set(response_counts.keys()) - accepted_response_ids
    if superseded_ids:
        if ts != "superseded" or rr_val != "task_changed":
            raise KernelCorruptionError(
                f"interaction {event_id}: superseded response messages without "
                f"superseded/task_changed aggregate"
            )
        if len(superseded_ids) > 1:
            raise KernelCorruptionError(
                f"interaction {event_id}: multiple superseded response messages: "
                f"{sorted(superseded_ids)}"
            )

    # --- Bidirectional reservation correspondence (before per-message
    #     validation so key-level mismatches are caught with specific messages) ---
    reservations = aggregate.get("message_reservations", {})
    message_keys: set[str] = set()
    for msg_row in messages:
        key = f"{msg_row['kind']}:{msg_row['message_id']}"
        message_keys.add(key)
    reservation_keys = set(reservations.keys())
    if message_keys != reservation_keys:
        extra_msg = message_keys - reservation_keys
        extra_res = reservation_keys - message_keys
        parts = []
        if extra_msg:
            parts.append(f"messages without reservations: {sorted(extra_msg)}")
        if extra_res:
            parts.append(f"reservations without messages: {sorted(extra_res)}")
        raise KernelCorruptionError(f"interaction {event_id}: " + "; ".join(parts))

    # --- Validate each message row ---
    for msg_row in messages:
        store._validate_message_row(conn, msg_row, aggregate)


def _validate_terminal_state_v1(
    aggregate: dict[str, Any], int_row: sqlite3.Row
) -> None:
    """Validate terminal/phase/reason/deadline coherence (Defect 15)."""
    event_id = aggregate["event_id"]
    revisions = aggregate.get("revisions", [])
    phase = aggregate["phase"]
    ts = aggregate.get("terminal_status")
    rr_val = aggregate.get("resolution_reason")

    # --- Defect 15: Accept only these durable terminal states ---
    if ts is not None:
        # Terminal: must have resolution_reason and terminal_at_epoch
        if rr_val is None:
            raise KernelCorruptionError(
                f"interaction {event_id}: terminal without resolution_reason"
            )
        if aggregate.get("terminal_at_epoch") is None:
            raise KernelCorruptionError(
                f"interaction {event_id}: terminal without terminal_at_epoch"
            )

        # No deadline for terminal rows
        if int_row["next_deadline_epoch"] is not None:
            raise KernelCorruptionError(
                f"interaction {event_id}: terminal but has next_deadline_epoch"
            )

        # Defect 15: superseded must be task_changed only
        if ts == "superseded" and rr_val != "task_changed":
            raise KernelCorruptionError(
                f"interaction {event_id}: superseded but resolution_reason={rr_val}"
            )

        # Defect 15: completed reasons
        if ts == "completed":
            if rr_val not in (
                "deferred", "dismissed", "shrink_limit_reached",
                "blocked_unresolved", "observation_completed",
                "start_observation_elapsed",
            ):
                raise KernelCorruptionError(
                    f"interaction {event_id}: completed but resolution_reason={rr_val}"
                )

        # Defect 15: expired must be card_expired_without_response only
        if ts == "expired":
            if rr_val != "card_expired_without_response":
                raise KernelCorruptionError(
                    f"interaction {event_id}: expired with resolution_reason={rr_val}"
                )

        # Defect 15: reject request_expired, failed, refused
        if ts in ("refused", "failed"):
            raise KernelCorruptionError(
                f"interaction {event_id}: terminal status {ts} not produced by Milestone 2"
            )
        if ts == "expired" and rr_val in ("card_not_posted_before_expiry", "delivery_ambiguous"):
            raise KernelCorruptionError(
                f"interaction {event_id}: expired/{rr_val} not produced by Milestone 2"
            )
    else:
        # Non-terminal
        if rr_val is not None:
            raise KernelCorruptionError(
                f"interaction {event_id}: non-terminal with resolution_reason={rr_val}"
            )

        if phase == "awaiting_response":
            # Must have unanswered Card and exact Card deadline
            if not revisions:
                raise KernelCorruptionError(
                    f"interaction {event_id}: awaiting_response without revisions"
                )
            last_rev = revisions[-1]
            if last_rev.get("response") is not None:
                raise KernelCorruptionError(
                    f"interaction {event_id}: awaiting_response but last revision has response"
                )
            card_expiry = last_rev.get("card_expires_at_epoch")
            ndl = int_row["next_deadline_epoch"]
            if not isinstance(card_expiry, int) or card_expiry <= 0:
                raise KernelCorruptionError(
                    f"interaction {event_id}: awaiting_response without valid card expiry"
                )
            if ndl != card_expiry:
                raise KernelCorruptionError(
                    f"interaction {event_id}: next_deadline_epoch {ndl} != card expiry {card_expiry}"
                )

        elif phase == "observing":
            # Must have accepted Start and observation deadline
            start_found = any(
                r.get("response", {}).get("action") == "start"
                for r in revisions
            )
            if not start_found:
                raise KernelCorruptionError(
                    f"interaction {event_id}: observing without Start response"
                )
            obs = aggregate.get("observation_due_at_epoch")
            ndl = int_row["next_deadline_epoch"]
            if not isinstance(obs, int) or obs <= 0:
                raise KernelCorruptionError(
                    f"interaction {event_id}: observing without observation_due_at_epoch"
                )
            if ndl != obs:
                raise KernelCorruptionError(
                    f"interaction {event_id}: next_deadline_epoch {ndl} != "
                    f"observation_due_at_epoch {obs}"
                )
        elif phase == "terminal":
            raise KernelCorruptionError(
                f"interaction {event_id}: phase is terminal but terminal_status is None"
            )
        else:
            raise KernelCorruptionError(
                f"interaction {event_id}: unknown phase {phase!r}"
            )


# ---------------------------------------------------------------------------
# Database connection and path resolution
# ---------------------------------------------------------------------------


def _xdg_state_home() -> Path:
    raw = os.environ.get("XDG_STATE_HOME", "")
    if raw and not raw.startswith("/"):
        raw = ""
    if raw:
        return Path(raw)
    return Path.home() / ".local" / "state"


def default_state_dir() -> Path:
    """Return the default application state directory.

    Uses $XDG_STATE_HOME/perseverance-ai/task-initiation,
    falling back to ~/.local/state/perseverance-ai/task-initiation.
    """
    return _xdg_state_home() / "perseverance-ai" / "task-initiation"


def _sqlite_uri(path: Path, *, mode: str = "rw") -> str:
    """Return a SQLite URI for *path* with percent-encoded special characters.

    *mode* is ``rw`` (non-creating read-write) or ``ro`` (read-only).
    The URI does NOT create a missing file; ``mode=rwc`` would.
    """
    from urllib.parse import quote
    encoded = quote(str(path), safe="/")
    return f"file:{encoded}?mode={mode}"


def connect_database(path: Path, *, busy_timeout_seconds: float) -> sqlite3.Connection:
    """Open a SQLite connection with explicit manual transaction control.

    Uses ``mode=rw`` URI so a missing file raises an error rather than
    creating an empty database. Only ``initialize()`` may create the file.
    """
    kwargs: dict[str, Any] = {
        "uri": True,
        "timeout": busy_timeout_seconds,
        "isolation_level": None,
    }
    if hasattr(sqlite3, "LEGACY_TRANSACTION_CONTROL"):
        kwargs["autocommit"] = sqlite3.LEGACY_TRANSACTION_CONTROL
    connection = sqlite3.connect(_sqlite_uri(path, mode="rw"), **kwargs)
    connection.row_factory = sqlite3.Row
    return connection


def _validate_secure_state_directory(path: Path) -> None:
    """Reject unless *path* is a real non-symlink directory owned by us, mode 0700."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise KernelStorageError(f"cannot lstat state dir: {exc}")
    if stat.S_ISLNK(st.st_mode):
        raise KernelStorageError("state directory is a symlink")
    if not stat.S_ISDIR(st.st_mode):
        raise KernelStorageError("state directory is not a directory")
    if st.st_uid != os.geteuid():
        raise KernelStorageError("state directory not owned by current user")
    if stat.S_IMODE(st.st_mode) != 0o700:
        raise KernelStorageError(
            f"state directory permissions {oct(stat.S_IMODE(st.st_mode))}, expected 0700"
        )


def _validate_secure_database_file(path: Path) -> None:
    """Reject unless *path* is a real non-symlink regular file with safe attributes."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise KernelStorageError(f"cannot lstat DB: {exc}")
    if stat.S_ISLNK(st.st_mode):
        raise KernelStorageError("database is a symlink")
    if not stat.S_ISREG(st.st_mode):
        raise KernelStorageError("database is not a regular file")
    if st.st_uid != os.geteuid():
        raise KernelStorageError("database not owned by current user")
    if st.st_nlink != 1:
        raise KernelStorageError("database has hard links")
    if stat.S_IMODE(st.st_mode) != 0o600:
        raise KernelStorageError(
            f"database permissions {oct(stat.S_IMODE(st.st_mode))}, expected 0600"
        )


# ---------------------------------------------------------------------------
# TaskInitiationStore
# ---------------------------------------------------------------------------


class TaskInitiationStore:
    """Private XDG-local SQLite persistence for the task-initiation kernel.

    Owns: path resolution, permission enforcement, schema migration,
    explicit transactions, read-only connections, and health checks.
    """
    def _verify_permissions(self) -> None:
        """Re-verify permissions on state dir and DB before every entry point.

        Raises ``KernelStorageError`` if the DB has not been initialized yet.
        """
        if not os.path.lexists(str(self._state_dir)):
            raise KernelStorageError("state directory does not exist")
        _validate_secure_state_directory(self._state_dir)
        if not os.path.lexists(str(self._db_path)):
            raise KernelStorageError("database not initialized — run init first")
        _validate_secure_database_file(self._db_path)
    @property
    def database_path(self) -> Path:
        return self._db_path

    def __init__(self, state_dir: Path, *, busy_timeout_seconds: float) -> None:
        if not state_dir.is_absolute():
            raise KernelStorageError(f"state_dir must be absolute: {state_dir}")
        self._state_dir = state_dir
        self._db_path = state_dir / "kernel.sqlite3"
        self._busy_timeout = busy_timeout_seconds



    def initialize(self) -> dict[str, Any]:
        """Create app dir, open DB, set PRAGMAs, validate journal_mode, migrate.

        Idempotent: re-running on an existing valid database normalizes
        journal_mode back to DELETE.  New paths are created with strict
        permissions; existing insecure paths raise KernelStorageError.
        """
        # Use os.path.lexists (not Path.exists) to detect broken symlinks.
        # Path.exists() follows symlinks and returns False for broken ones,
        # which would cause us to attempt creation through the symlink.
        db_lexists = os.path.lexists(str(self._db_path))
        state_lexists = os.path.lexists(str(self._state_dir))

        if not state_lexists:
            self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        else:
            _validate_secure_state_directory(self._state_dir)

        if db_lexists:
            # Directory entry exists.  If it's a broken symlink, Path.exists()
            # returns False but we must still reject it.
            if not self._db_path.exists():
                # Broken symlink or other unresolvable path — reject without opening
                raise KernelStorageError("database path is a broken symlink")
            # Validate path attributes BEFORE any SQLite open.
            _validate_secure_database_file(self._db_path)
        else:
            # Secure pre-creation: O_EXCL ensures we create, not open existing.
            # O_NOFOLLOW prevents following a symlink created between lexists and open.
            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(str(self._db_path), flags, 0o600)
                os.close(fd)
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    raise KernelStorageError(
                        f"database path already exists (symlink or race): {self._db_path}"
                    )
                if hasattr(os, "O_NOFOLLOW") and exc.errno == errno.ELOOP:
                    raise KernelStorageError(
                        f"database path is a symlink: {self._db_path}"
                    )
                raise KernelStorageError(f"cannot create database: {self._db_path}: {exc}")
            # Re-validate the newly created file
            _validate_secure_database_file(self._db_path)
        try:
            conn = connect_database(self._db_path, busy_timeout_seconds=self._busy_timeout)
        except sqlite3.Error as exc:
            raise _translate_sqlite_error(exc)

        try:
            # Enable foreign keys and set pragmas before any DDL
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = %d" % int(self._busy_timeout * 1000))
            conn.execute("PRAGMA synchronous = EXTRA")

            # Set and verify journal_mode=DELETE (not in a transaction)
            conn.execute("PRAGMA journal_mode = DELETE")
            row = conn.execute("PRAGMA journal_mode").fetchone()
            if row is None or row[0].lower() != "delete":
                raise KernelStorageError(
                    f"journal_mode is {row[0] if row else 'unknown'}, expected delete"
                )

            # Verify foreign_keys
            fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
            if fk_row is None or fk_row[0] != 1:
                raise KernelStorageError("foreign_keys not enabled")

            # Verify synchronous
            sync_row = conn.execute("PRAGMA synchronous").fetchone()
            if sync_row is None or sync_row[0] != 3:
                raise KernelStorageError(f"synchronous is {sync_row[0] if sync_row else 'unknown'}, expected 3")

            # Check current version FIRST (before permissions) so incompatible
            # databases raise KernelCorruptionError, not KernelStorageError

            # Check current version
            version_row = conn.execute("PRAGMA user_version").fetchone()
            version = version_row[0] if version_row else 0

            if version == 0:
                # Check if there are any user tables (nonempty version-0 → refuse)
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                if tables:
                    raise KernelCorruptionError(
                        "nonempty version-0 database; reset required"
                    )
                # Migrate to version 1
                self._migrate_v1(conn)
            elif version == 1:
                self._validate_schema_structure(conn)
            elif version > 1:
                raise KernelCorruptionError(
                    f"unsupported database version {version}; "
                    f"this kernel supports only version 1"
                )
            else:
                raise KernelCorruptionError(f"unexpected user_version: {version}")

            # Final integrity check
            integrity = conn.execute("PRAGMA integrity_check").fetchall()
            if [row[0] for row in integrity] != ["ok"]:
                raise KernelCorruptionError(f"integrity_check failed: {integrity}")

            fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_check:
                raise KernelCorruptionError(f"foreign_key_check failed: {fk_check}")

            return {"status": "initialized", "version": 1, "path": str(self._db_path)}
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3.Error as exc:
            raise _translate_sqlite_error(exc)
        finally:
            _safe_close(conn)

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        """Create version-1 schema in a single transaction."""
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA_DDL_STATEMENTS:
                conn.execute(statement)
            conn.execute("PRAGMA user_version = 1")
            conn.execute("COMMIT")
        except (KernelBusyError, KernelCorruptionError, KernelStorageError) as exc:
            try: conn.execute("ROLLBACK")
            except sqlite3.Error as _re:
                raise KernelStorageError(
                    f"migration rollback failed after {type(exc).__name__}({exc}): "
                    f"rollback error {type(_re).__name__}: {_re}"
                ) from exc
            raise
        except sqlite3.Error as exc:
            try: conn.execute("ROLLBACK")
            except sqlite3.Error as _re:
                raise KernelStorageError(
                    f"migration rollback failed after sqlite3.Error({exc}): "
                    f"rollback error {type(_re).__name__}: {_re}"
                ) from exc
            raise _translate_sqlite_error(exc)
        except Exception as exc:
            try: conn.execute("ROLLBACK")
            except sqlite3.Error as _re:
                raise KernelStorageError(
                    f"migration rollback failed after {type(exc).__name__}({exc}): "
                    f"rollback error {type(_re).__name__}: {_re}"
                ) from exc
            raise


    def _validate_schema_structure(self, conn: sqlite3.Connection) -> None:
        """Full structural schema validation: tables, triggers, views, columns,
        PKs, UNIQUE constraints, indexes, FKs, journal_mode=DELETE."""
        # Reject triggers and views
        extra_objects = conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('trigger', 'view')"
        ).fetchall()
        if extra_objects:
            names = [f"{r['type']} {r['name']}" for r in extra_objects]
            raise KernelCorruptionError("unexpected schema objects: " + "; ".join(names))
        version_row = conn.execute("PRAGMA user_version").fetchone()
        if version_row is None or version_row[0] != 1:
            raise KernelCorruptionError(
                f"expected user_version=1, got {version_row}"
            )

        # Check table names
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = {row[0] for row in tables}
        if table_names != _EXPECTED_TABLE_NAMES:
            extra = table_names - _EXPECTED_TABLE_NAMES
            missing = _EXPECTED_TABLE_NAMES - table_names
            msg_parts = []
            if extra:
                msg_parts.append(f"unexpected tables: {sorted(extra)}")
            if missing:
                msg_parts.append(f"missing tables: {sorted(missing)}")
            raise KernelCorruptionError("schema mismatch: " + "; ".join(msg_parts))

        # Check columns for each table
        expected_cols_map = {
            "interactions": _EXPECTED_INTERACTIONS_COLS,
            "messages": _EXPECTED_MESSAGES_COLS,
            "card_index": _EXPECTED_CARD_INDEX_COLS,
        }
        for table_name, expected_cols in expected_cols_map.items():
            cols = conn.execute(f"PRAGMA table_xinfo({table_name})").fetchall()
            if len(cols) != len(expected_cols):
                raise KernelCorruptionError(
                    f"{table_name}: expected {len(expected_cols)} columns, got {len(cols)}"
                )
            for (exp_cid, exp_name, exp_type, exp_notnull, exp_dflt, exp_pk, exp_hidden), col in zip(expected_cols, cols):
                if col["cid"] != exp_cid:
                    raise KernelCorruptionError(
                        f"{table_name}.{col['name']}: cid {col['cid']} != expected {exp_cid}"
                    )
                if col["name"].lower() != exp_name.lower():
                    raise KernelCorruptionError(
                        f"{table_name}: column {col['cid']} name {col['name']} != expected {exp_name}"
                    )
                if col["type"].upper() != exp_type.upper():
                    raise KernelCorruptionError(
                        f"{table_name}.{col['name']}: type {col['type']} != expected {exp_type}"
                    )
                if bool(col["notnull"]) != bool(exp_notnull):
                    raise KernelCorruptionError(
                        f"{table_name}.{col['name']}: notnull {col['notnull']} != expected {exp_notnull}"
                    )
                if col["pk"] != exp_pk:
                    raise KernelCorruptionError(
                        f"{table_name}.{col['name']}: pk {col['pk']} != expected {exp_pk}"
                    )
                if col["hidden"] != exp_hidden:
                    raise KernelCorruptionError(
                        f"{table_name}.{col['name']}: hidden {col['hidden']} != expected {exp_hidden}"
                    )
                # For dflt_value, ignore differences in quoting (SQLite may
                # store NULL as None or the string "NULL")
                if exp_dflt is not None and col["dflt_value"] is not None:
                    if col["dflt_value"].upper() != exp_dflt.upper():
                        raise KernelCorruptionError(
                            f"{table_name}.{col['name']}: dflt {col['dflt_value']} != expected {exp_dflt}"
                        )

        # Check index names
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        index_names = {row[0] for row in indexes}
        if index_names != _EXPECTED_INDEX_NAMES:
            extra = index_names - _EXPECTED_INDEX_NAMES
            missing = _EXPECTED_INDEX_NAMES - index_names
            msg_parts = []
            if extra:
                msg_parts.append(f"unexpected indexes: {sorted(extra)}")
            if missing:
                msg_parts.append(f"missing indexes: {sorted(missing)}")
            raise KernelCorruptionError("index mismatch: " + "; ".join(msg_parts))

        # Validate each table's index_list: PK + UNIQUE + named index
        # interactions: PK(event_id), UNIQUE(interaction_id), named nonunique(terminal_status,next_deadline_epoch,event_id)
        for table_name in _EXPECTED_TABLE_NAMES:
            idx_list = conn.execute(f"PRAGMA index_list('{table_name}')").fetchall()
            idx_entries: list[dict[str, Any]] = []
            for idx_row in idx_list:
                idx_name = idx_row["name"]
                idx_cols_raw = conn.execute(f"PRAGMA index_xinfo('{idx_name}')").fetchall()
                key_cols = [(c["name"].lower(), c["cid"]) for c in idx_cols_raw if c["key"]]
                idx_entries.append({
                    "name": idx_name,
                    "unique": bool(idx_row["unique"]),
                    "origin": idx_row["origin"],
                    "partial": bool(idx_row["partial"]),
                    "key_cols": key_cols,
                })

            if table_name == "interactions":
                # PK on event_id (auto-created by SQLite)
                pk_found = any(
                    e["unique"] and e["origin"] in ("pk", "u") and [c[0] for c in e["key_cols"]] == ["event_id"]
                    for e in idx_entries
                )
                if not pk_found:
                    raise KernelCorruptionError("interactions: missing PK on event_id")
                # UNIQUE on interaction_id
                uniq_found = any(
                    e["unique"] and [c[0] for c in e["key_cols"]] == ["interaction_id"]
                    for e in idx_entries
                )
                if not uniq_found:
                    raise KernelCorruptionError("interactions: missing UNIQUE on interaction_id")
                # Named non-unique index
                named = [e for e in idx_entries if not e["name"].startswith("sqlite_")]
                if len(named) != 1 or named[0]["name"] != "interactions_active_deadline_idx":
                    raise KernelCorruptionError("interactions: missing interactions_active_deadline_idx")
                if named[0]["unique"] or named[0]["partial"]:
                    raise KernelCorruptionError("interactions: interactions_active_deadline_idx must be non-unique non-partial")
                actual_cols = [c[0] for c in named[0]["key_cols"]]
                if actual_cols != ["terminal_status", "next_deadline_epoch", "event_id"]:
                    raise KernelCorruptionError(
                        f"interactions_active_deadline_idx: cols {actual_cols} != expected"
                    )

            elif table_name == "messages":
                pk_found = any(
                    e["unique"] and e["origin"] in ("pk", "u") and set(c[0] for c in e["key_cols"]) == {"kind", "message_id"}
                    for e in idx_entries
                )
                if not pk_found:
                    raise KernelCorruptionError("messages: missing PK on (kind, message_id)")

            elif table_name == "card_index":
                pk_found = any(
                    e["unique"] and e["origin"] in ("pk", "u") and [c[0] for c in e["key_cols"]] == ["card_id"]
                    for e in idx_entries
                )
                if not pk_found:
                    raise KernelCorruptionError("card_index: missing PK on card_id")
                # Inline UNIQUE creates sqlite_autoindex_card_index_N
                uniq_found = any(
                    e["unique"] and [c[0] for c in e["key_cols"]] == ["event_id", "revision"]
                    for e in idx_entries
                )
                if not uniq_found:
                    raise KernelCorruptionError("card_index: missing UNIQUE on (event_id, revision)")
        # FK validation: exactly two FKs, both ON DELETE CASCADE, ON UPDATE NO ACTION
        fk_tables = []
        for table_name in _EXPECTED_TABLE_NAMES:
            fk_list = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
            for fk in fk_list:
                fk_tables.append((table_name, fk["from"], fk["table"], fk["to"], fk["on_delete"], fk["on_update"]))

        expected_fks = {
            ("messages", "event_id", "interactions", "event_id", "CASCADE", "NO ACTION"),
            ("card_index", "event_id", "interactions", "event_id", "CASCADE", "NO ACTION"),
        }
        actual_fks = {(fk[0], fk[1], fk[2], fk[3], fk[4], fk[5].upper()) for fk in fk_tables}
        if actual_fks != expected_fks:
            extra = actual_fks - expected_fks
            missing = expected_fks - actual_fks
            msg_parts = []
            if extra:
                msg_parts.append(f"unexpected FKs: {sorted(extra)}")
            if missing:
                msg_parts.append(f"missing FKs: {sorted(missing)}")
            raise KernelCorruptionError("FK mismatch: " + "; ".join(msg_parts))

    @contextmanager
    def immediate_transaction(self) -> Iterator[sqlite3.Connection]:
        """Open writer, BEGIN IMMEDIATE, yield, commit/rollback, always close."""
        self._verify_permissions()
        try:
            conn = connect_database(self._db_path, busy_timeout_seconds=self._busy_timeout)
        except sqlite3.Error as exc:
            raise _translate_sqlite_error(exc)
        try:
            # Verify PRAGMAs
            conn.execute("PRAGMA foreign_keys = ON")
            fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
            if fk_row is None or fk_row[0] != 1:
                raise KernelStorageError("foreign_keys not enabled on writer")

            # Verify DB version on every entry point
            vrow = conn.execute("PRAGMA user_version").fetchone()
            version = vrow[0] if vrow else 0
            if version != 1:
                raise KernelCorruptionError(
                    f"unsupported database version {version}; this kernel requires version 1"
                )

            self._validate_schema_structure(conn)
            conn.execute("PRAGMA busy_timeout = %d" % int(self._busy_timeout * 1000))
            conn.execute("PRAGMA synchronous = 3")
            # Verify synchronous took effect
            sync_row = conn.execute("PRAGMA synchronous").fetchone()
            if sync_row is None or sync_row[0] != 3:
                raise KernelStorageError(
                    f"synchronous is {sync_row[0] if sync_row else 'unknown'}, expected 3"
                )

            jm_row = conn.execute("PRAGMA journal_mode").fetchone()
            if jm_row is None or jm_row[0].lower() != "delete":
                raise KernelStorageError(
                    f"journal_mode is {jm_row[0] if jm_row else 'unknown'}, expected delete"
                )

            assert not conn.in_transaction, "connection already in transaction"
            conn.execute("BEGIN IMMEDIATE")
            assert conn.in_transaction, "BEGIN IMMEDIATE did not start transaction"
            yield conn
            if conn.in_transaction:
                conn.execute("COMMIT")
                assert not conn.in_transaction, "COMMIT did not end transaction"
        except (KernelBusyError, KernelCorruptionError, KernelStorageError) as _exc:
            if conn.in_transaction:
                try: conn.execute("ROLLBACK")
                except sqlite3.Error as _re:
                    raise KernelStorageError(
                        f"rollback failed after {type(_exc).__name__}({_exc}): rollback error {_re}"
                    ) from _exc
            raise
        except sqlite3.Error as exc:
            if conn.in_transaction:
                try: conn.execute("ROLLBACK")
                except sqlite3.Error as _re:
                    raise KernelStorageError(
                        f"rollback failed after sqlite3.Error({exc}): rollback error {_re}"
                    ) from exc
            raise _translate_sqlite_error(exc)
        except Exception:
            if conn.in_transaction:
                try: conn.execute("ROLLBACK")
                except sqlite3.Error as _re:
                    raise KernelStorageError(
                        f"rollback failed after Exception: {_re}"
                    )
            raise
        finally:
            _safe_close(conn)

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        """Open read-only connection with query_only=ON."""
        self._verify_permissions()
        uri = _sqlite_uri(self._db_path, mode="ro")
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=self._busy_timeout)
        except sqlite3.Error as exc:
            raise _translate_sqlite_error(exc)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = %d" % int(self._busy_timeout * 1000))

            # Verify DB version on every entry point
            vrow = conn.execute("PRAGMA user_version").fetchone()
            version = vrow[0] if vrow else 0
            if version != 1:
                raise KernelCorruptionError(
                    f"unsupported database version {version}; this kernel requires version 1"
                )

            self._validate_schema_structure(conn)
            jm_row = conn.execute("PRAGMA journal_mode").fetchone()
            if jm_row is None or jm_row[0].lower() != "delete":
                raise KernelStorageError(
                    f"journal_mode is {jm_row[0] if jm_row else 'unknown'}, expected delete"
                )

            yield conn
        except (KernelBusyError, KernelCorruptionError, KernelStorageError):
            raise
        except sqlite3.Error as exc:
            raise _translate_sqlite_error(exc)
        finally:
            _safe_close(conn)

    def check_database(self) -> dict[str, Any]:
        """Read-only structural, integrity, and proportional row validation."""
        with self.read_connection() as conn:
            # Schema checks
            self._validate_schema_structure(conn)

            # Integrity
            integrity = conn.execute("PRAGMA integrity_check").fetchall()
            if [row[0] for row in integrity] != ["ok"]:
                raise KernelCorruptionError(f"integrity_check: {integrity}")

            fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_check:
                raise KernelCorruptionError(f"foreign_key_check: {fk_check}")

            # Validate each interaction row
            interactions = conn.execute(
                "SELECT event_id FROM interactions ORDER BY event_id"
            ).fetchall()
            for row in interactions:
                self.load_and_validate_bundle(conn, row["event_id"])

            # Message count from SQL (all messages already validated inside bundles)
            message_count_row = conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()
            message_count = message_count_row[0] if message_count_row else 0

            return {
                "status": "ok",
                "version": 1,
                "interaction_count": len(interactions),
                "message_count": message_count,
            }

    # ------------------------------------------------------------------
    # Row validation
    # ------------------------------------------------------------------

    def _validate_message_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        aggregate: dict[str, Any] | None = None,
    ) -> None:
        """Validate a single messages row against its owning aggregate."""
        kind = row["kind"]
        message_id = row["message_id"]
        source = f"messages {kind}:{message_id}"

        # Verify payload_sha256 matches canonical payload_json
        payload = _decode_message_payload_json(row["payload_json"], source=source)

        computed_hash = c._payload_sha256(payload)
        if computed_hash != row["payload_sha256"]:
            raise KernelCorruptionError(
                f"{source}: payload_sha256 mismatch"
            )

        # Validate payload through public validators (structural mode only)
        try:
            if kind == "stuck":
                c.validate_stuck_event(payload)
            elif kind == "response":
                c.validate_response(payload)
        except c.TaskInitiationContractError as exc:
            raise KernelCorruptionError(f"{source}: invalid payload: {exc}")

        # Verify canonical re-encoding matches stored payload_json
        recanonical = c._canonical_json(payload).decode("utf-8")
        if recanonical != row["payload_json"]:
            raise KernelCorruptionError(f"{source}: payload not canonical")
        # If we have the aggregate, verify reservation matches
        if aggregate is not None:
            reservations = aggregate.get("message_reservations", {})
            key = f"{kind}:{message_id}"
            reserved_hash = reservations.get(key)
            if reserved_hash is None:
                raise KernelCorruptionError(
                    f"{source}: not found in message_reservations"
                )
            if reserved_hash != row["payload_sha256"]:
                raise KernelCorruptionError(
                    f"{source}: reservation hash mismatch"
                )

        # Verify result_json is valid JSON
        try:
            result = c._strict_json_loads(row["result_json"])
        except (json.JSONDecodeError, ValueError) as exc:
            raise KernelCorruptionError(f"{source}: invalid result_json: {exc}")
        if not isinstance(result, dict):
            raise KernelCorruptionError(f"{source}: result is not a dict")

        # SQL row-to-payload identity checks (Defect 7)
        if aggregate is not None:
            if kind == "stuck":
                # Stuck: message_id == payload.event_id
                if message_id != payload.get("event_id"):
                    raise KernelCorruptionError(
                        f"{source}: message_id {message_id} != payload.event_id {payload.get('event_id')}"
                    )
                # Stuck: recorded_at_epoch == request_received_at_epoch
                if row["recorded_at_epoch"] != aggregate.get("request_received_at_epoch"):
                    raise KernelCorruptionError(
                        f"{source}: recorded_at {row['recorded_at_epoch']} != "
                        f"request_received_at {aggregate.get('request_received_at_epoch')}"
                    )
            elif kind == "response":
                # Response: message_id == payload.response_id
                if message_id != payload.get("response_id"):
                    raise KernelCorruptionError(
                        f"{source}: message_id {message_id} != payload.response_id {payload.get('response_id')}"
                    )
                # Determine if accepted or superseded
                resp_found = False
                targeted_rr: int | None = None
                for rev in aggregate.get("revisions", []):
                    if (
                        rev.get("response") is not None
                        and rev["response"].get("response_id") == message_id
                    ):
                        resp_found = True
                        targeted_rr = rev["response"].get("received_at_epoch")
                        break
                if resp_found:
                    # Accepted: recorded_at_epoch == revision.response.received_at_epoch
                    if targeted_rr is not None and row["recorded_at_epoch"] != targeted_rr:
                        raise KernelCorruptionError(
                            f"{source}: recorded_at {row['recorded_at_epoch']} != "
                            f"response.received_at {targeted_rr}"
                        )
                elif aggregate.get("terminal_status") == "superseded":
                    # Superseded: recorded_at_epoch == aggregate.terminal_at_epoch
                    ta = aggregate.get("terminal_at_epoch")
                    if ta is not None and row["recorded_at_epoch"] != ta:
                        raise KernelCorruptionError(
                            f"{source}: recorded_at {row['recorded_at_epoch']} != "
                            f"terminal_at_epoch {ta}"
                        )
    # ------------------------------------------------------------------
    # Internal: validate a replay message against an already-validated bundle
    # ------------------------------------------------------------------

    def _validate_replay_against_bundle(
        self, conn: sqlite3.Connection, message_row: sqlite3.Row,
        aggregate: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate replay payload/reservation/result against *aggregate*.

        Does NOT reload or reconstruct the owner.  Returns (payload, result).
        """
        kind = message_row["kind"]
        message_id = message_row["message_id"]
        event_id = message_row["event_id"]
        source = f"replay {kind}:{message_id}"

        # Verify payload
        payload = _decode_message_payload_json(message_row["payload_json"], source=source)
        computed_payload_hash = c._payload_sha256(payload)
        if computed_payload_hash != message_row["payload_sha256"]:
            raise KernelCorruptionError(f"{source}: payload_sha256 mismatch")

        # Verify reservation
        reservations = aggregate.get("message_reservations", {})
        rkey = f"{kind}:{message_id}"
        if reservations.get(rkey) != message_row["payload_sha256"]:
            raise KernelCorruptionError(f"{source}: reservation mismatch")

        # Decode result
        try:
            result = c._strict_json_loads(message_row["result_json"])
        except (json.JSONDecodeError, ValueError) as exc:
            raise KernelCorruptionError(f"{source}: invalid result_json: {exc}")
        if not isinstance(result, dict):
            raise KernelCorruptionError(f"{source}: result is not a dict")

        # Build expected result
        if kind == "stuck":
            expected = _expected_stuck_result(
                event_id, aggregate["interaction_id"], aggregate, conn,
            )
        elif kind == "response":
            expected = _expected_response_result(message_id, aggregate, conn, payload=payload)
        else:
            raise KernelCorruptionError(f"{source}: unknown message kind: {kind}")

        expected_bytes = c._canonical_json(expected)
        if expected_bytes.decode("utf-8") != message_row["result_json"]:
            raise KernelCorruptionError(
                f"{source}: result_json not canonical"
            )

        return payload, result

    # ------------------------------------------------------------------
    # Public bundle loader (single semantic authority)
    # ------------------------------------------------------------------

    def load_and_validate_bundle(
        self, conn: sqlite3.Connection, event_id: str, *, message_row: sqlite3.Row | None = None
    ) -> ValidatedBundle:
        """Load and fully validate an interaction bundle.

        Performs structural decoding, deterministic-preparation validation,
        frozen-reducer reconstruction, exact canonical aggregate comparison,
        SQL-derived owner-column checks, Card-route checks, and optionally
        replay-result validation.

        This is the single lifecycle authority for every public surface.
        """
        # --- 1. Load interaction row ---
        int_row = conn.execute(
            "SELECT * FROM interactions WHERE event_id = ?", (event_id,)
        ).fetchone()
        if int_row is None:
            raise KernelNotFoundError(f"interaction {event_id} not found")

        # --- 1b. Validate SQL scalar types ---
        for _col, _require_pos in [
            ("state_version", True), ("created_at_epoch", True),
            ("updated_at_epoch", True), ("last_observed_at_epoch", True),
        ]:
            _v = int_row[_col]
            if isinstance(_v, bool) or not isinstance(_v, int) or (_require_pos and _v <= 0):
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: interactions.{_col} must be "
                    f"{'positive ' if _require_pos else ''}int, got {type(_v).__name__} {_v!r}"
                )
        for _col in ("next_deadline_epoch",):
            _v = int_row[_col]
            if _v is not None:
                if isinstance(_v, bool) or not isinstance(_v, int) or _v <= 0:
                    raise KernelCorruptionError(
                        f"load_and_validate_bundle: interactions.{_col} must be "
                        f"positive int or null, got {type(_v).__name__} {_v!r}"
                    )
        for _col in ("event_id", "interaction_id", "phase"):
            _v = int_row[_col]
            if isinstance(_v, bool) or not isinstance(_v, str):
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: interactions.{_col} must be string, "
                    f"got {type(_v).__name__}"
                )
        _ts_val = int_row["terminal_status"]
        if _ts_val is not None and (isinstance(_ts_val, bool) or not isinstance(_ts_val, str)):
            raise KernelCorruptionError(
                f"load_and_validate_bundle: interactions.terminal_status must be string or null, "
                f"got {type(_ts_val).__name__}"
            )
        _pol_raw = int_row["interaction_policy_json"]
        if isinstance(_pol_raw, bool) or not isinstance(_pol_raw, str):
            raise KernelCorruptionError(
                f"load_and_validate_bundle: interaction_policy_json must be string, "
                f"got {type(_pol_raw).__name__}"
            )

        # --- 2. Decode policy and aggregate (inside safety net) ---
        try:
            policy = _interaction_policy_from_json(int_row["interaction_policy_json"])
            aggregate = _agg_from_db(int_row["aggregate_json"], source=f"interaction {event_id}")
         
            # --- 3. Structural and preparatory validators ---
            _validate_aggregate_structure(aggregate, row_event_id=event_id)
            _validate_revision_contiguity(aggregate)
    
            card_rows = conn.execute(
                "SELECT * FROM card_index WHERE event_id = ? ORDER BY revision",
                (event_id,),
            ).fetchall()
            _validate_card_index_correspondence(aggregate, card_rows)
            _validate_aggregate_v1(aggregate, int_row)
            _validate_terminal_state_v1(aggregate, int_row)
            _validate_revision_v1(aggregate, policy=policy)
            _validate_preparation_lineage_v1(aggregate, policy=policy)
            _validate_response_evidence_v1(aggregate)
            _validate_message_set_v1(self, conn, event_id, aggregate)
    
            # --- 4. Load reconstruction inputs ---
            stuck_row = conn.execute(
                "SELECT * FROM messages WHERE kind='stuck' AND event_id=?",
                (event_id,),
            ).fetchone()
            if stuck_row is None:
                raise KernelCorruptionError(f"load_and_validate_bundle: missing Stuck message for {event_id}")
    
            resp_rows = conn.execute(
                "SELECT * FROM messages WHERE kind='response' AND event_id=? ORDER BY message_id",
                (event_id,),
            ).fetchall()
            resp_msg_map: dict[str, sqlite3.Row] = {}
            superseding: sqlite3.Row | None = None
            accepted_ids: set[str] = set()
            for rev in aggregate.get("revisions", []):
                rev_resp = rev.get("response")
                if rev_resp is not None and isinstance(rev_resp, dict):
                    accepted_ids.add(rev_resp.get("response_id", ""))
            for rr in resp_rows:
                rid = rr["message_id"]
                try:
                    rpay = c._strict_json_loads(rr["payload_json"])
                except (json.JSONDecodeError, ValueError):
                    raise KernelCorruptionError(f"load_and_validate_bundle: invalid response payload for {rid}")
                if isinstance(rpay, dict):
                    actual_rid = rpay.get("response_id", rid)
                    if actual_rid in accepted_ids:
                        resp_msg_map[actual_rid] = rr
                    else:
                        superseding = rr
    
            # --- 4b. Validate resolved-task origin against Stuck ---
            stuck_payload = _decode_message_payload_json(
                stuck_row["payload_json"], source=f"bundle stuck origin {event_id}"
            )
            _validate_resolved_task_origin_v1(
                stuck_payload=stuck_payload,
                aggregate=aggregate,
            )

            # --- 5. Reducer reconstruction + canonical comparison ---
            resolved_task = aggregate.get("resolved_task", {})
            if not isinstance(resolved_task, dict):
                raise KernelCorruptionError(f"load_and_validate_bundle: resolved_task not a dict for {event_id}")
    
            reconstructed = reconstruct_expected_aggregate_v1(
                stuck_row=stuck_row,
                resolved_task=resolved_task,
                revisions=aggregate.get("revisions", []),
                response_messages=resp_msg_map,
                superseding_msg=superseding,
                terminal_at_epoch=aggregate.get("terminal_at_epoch"),
                interaction_policy=policy,
            )
            if _agg_to_db(reconstructed) != _agg_to_db(aggregate):
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: reducer reconstruction mismatch for {event_id}"
                )
    
            # --- 6. Validate SQL-derived owner columns ---
            if int_row["event_id"] != aggregate.get("event_id"):
                raise KernelCorruptionError(f"load_and_validate_bundle: event_id mismatch for {event_id}")
            if int_row["phase"] != aggregate.get("phase"):
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: phase mismatch for {event_id}: "
                    f"{int_row['phase']} != {aggregate.get('phase')}"
                )
            stored_status = _require_terminal_status(int_row["terminal_status"], f"int_row.terminal_status {event_id}")
            if stored_status != aggregate.get("terminal_status"):
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: terminal_status mismatch for {event_id}"
                )
    
            # --- 7. Validate all owner message results ---
            validated_payload = None
            validated_result = None
            all_messages: list[sqlite3.Row] = [stuck_row] + list(resp_rows)
            for msg_row in all_messages:
                pl, res = self._validate_replay_against_bundle(conn, msg_row, reconstructed)
                if (message_row is not None
                        and msg_row["kind"] == message_row["kind"]
                        and msg_row["message_id"] == message_row["message_id"]
                        and msg_row["event_id"] == message_row["event_id"]):
                    validated_payload = pl
                    validated_result = res
    
            if message_row is not None and validated_result is None:
                raise KernelCorruptionError(
                    f"load_and_validate_bundle: selected message {message_row['message_id']} "
                    f"does not belong to owner {event_id}"
                )
    
    
        except (TypeError, ValueError, KeyError, AttributeError, c.TaskInitiationContractError) as _exc:
            raise KernelCorruptionError(
                f"load_and_validate_bundle: {event_id}: malformed persistence: "
                f"{type(_exc).__name__}: {_exc}"
            ) from _exc
        return ValidatedBundle(
            int_row=int_row,
            aggregate=aggregate,
            validated_payload=validated_payload,
            validated_result=validated_result,
        )


    def validate_replay_bundle(
        self, conn: sqlite3.Connection, message_row: sqlite3.Row
    ) -> dict[str, Any]:
        """Validate a replay message through the authoritative bundle loader."""
        bundle = self.load_and_validate_bundle(
            conn, message_row["event_id"], message_row=message_row,
        )
        if bundle.validated_result is None:
            raise KernelCorruptionError(
                f"validate_replay_bundle: no result for {message_row['message_id']}"
            )
        return bundle.validated_result

    @staticmethod
    def _compute_next_deadline(aggregate: dict[str, Any]) -> int | None:
        """Derive next_deadline_epoch from aggregate state."""
        if aggregate.get("terminal_status") is not None:
            return None
        phase = aggregate.get("phase")
        if phase == "awaiting_response":
            revisions = aggregate.get("revisions", [])
            if revisions:
                current = revisions[-1]
                return current.get("card_expires_at_epoch")
        elif phase == "observing":
            return aggregate.get("observation_due_at_epoch")
        return None



def _expected_stuck_result(
    event_id: str,
    interaction_id: str,
    aggregate: dict[str, Any],
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Derive the expected Stuck result from persisted evidence."""
    revisions = aggregate.get("revisions", [])
    if not revisions:
        raise KernelCorruptionError(f"expected_stuck_result {event_id}: no revisions")
    card = revisions[0].get("card")
    if card is None:
        raise KernelCorruptionError(f"expected_stuck_result {event_id}: revision 1 has no card")
    card_id = card.get("card_id")
    if not isinstance(card_id, str):
        raise KernelCorruptionError(f"expected_stuck_result {event_id}: invalid card_id")
    rows = conn.execute(
        "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = 1",
        (card_id, event_id),
    ).fetchall()
    if len(rows) != 1:
        raise KernelCorruptionError(f"expected_stuck_result {event_id}: card_index missing for {card_id}")
    return {
        "kind": "stuck",
        "status": "card_published",
        "event_id": event_id,
        "interaction_id": interaction_id,
        "card": card,
    }

def _expected_response_result(

    response_id: str,
    aggregate: dict[str, Any],
    conn: sqlite3.Connection,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive the expected Response result from revision-local evidence.

    Accepted responses derive phase/status/reason from what the action
    produces, NOT from the current aggregate state.  This keeps historical
    replay immutable even after later revisions change the aggregate.
    """
    event_id = aggregate["event_id"]
    interaction_id = aggregate["interaction_id"]
    revisions = aggregate.get("revisions", [])

    # Try to find the revision containing this response
    targeted_rev_num: int | None = None
    card_id: str | None = None
    action: str | None = None
    is_accepted = False
    for rev in revisions:
        resp = rev.get("response")
        if resp is not None and resp.get("response_id") == response_id:
            targeted_rev_num = rev["revision"]
            card_id = rev["card"]["card_id"]
            action = resp["action"]
            is_accepted = True
            break

    if not is_accepted:
        # Superseded: response not stored in any revision
        if (
            aggregate.get("terminal_status") != "superseded"
            or aggregate.get("resolution_reason") != "task_changed"
        ):
            raise KernelCorruptionError(
                f"expected_response_result {response_id}: response not found in any revision "
                f"and aggregate is not superseded/task_changed"
            )
        if payload is None:
            raise KernelCorruptionError(
                f"expected_response_result {response_id}: superseded but no payload provided"
            )
        card_id = payload.get("card_id")
        action = payload.get("action")
        if not isinstance(card_id, str) or not isinstance(action, str):
            raise KernelCorruptionError(
                f"expected_response_result {response_id}: invalid payload for superseded"
            )
        # Find revision by card_id
        for rev in revisions:
            if rev.get("card", {}).get("card_id") == card_id:
                targeted_rev_num = rev["revision"]
                break
        if targeted_rev_num is None:
            raise KernelCorruptionError(
                f"expected_response_result {response_id}: card_id {card_id} not in any revision"
            )

    revision = targeted_rev_num

    # Verify card_index for the targeted revision
    cv_rows = conn.execute(
        "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = ?",
        (card_id, event_id, revision),
    ).fetchall()
    if len(cv_rows) != 1:
        raise KernelCorruptionError(
            f"expected_response_result {response_id}: card_index missing for {card_id} r{revision}"
        )

    # -----------------------------------------------
    # Superseded result — only for truly superseded (not found in revisions)
    # -----------------------------------------------
    if not is_accepted:
        return {
            "kind": "response",
            "status": "superseded",
            "response_id": response_id,
            "card_id": card_id,
            "interaction_id": interaction_id,
            "revision": revision,
            "requested_action": action,
            "next_card": None,
            "phase": "awaiting_response",
            "terminal_status": "superseded",
            "resolution_reason": "task_changed",
            "observation_due_at_epoch": None,
        }
    # -----------------------------------------------
    # Accepted result — derive from action, NOT aggregate
    # -----------------------------------------------

    # Determine next_card: look at revision+1
    next_card: dict[str, Any] | None = None
    next_rev_num = revision + 1
    for rev in revisions:
        if rev.get("revision") == next_rev_num:
            next_card = rev.get("card")
            break

    at_ceiling = next_card is None and action in ("shrink", "blocked")

    if action == "start":
        phase = "observing"
        terminal_status = None
        resolution_reason = None
        observation_due = aggregate.get("observation_due_at_epoch")
    elif action in ("shrink", "blocked"):
        if at_ceiling:
            phase = "observing"
            terminal_status = "completed"
            resolution_reason = (
                "shrink_limit_reached" if action == "shrink" else "blocked_unresolved"
            )
            observation_due = None
        else:
            phase = "awaiting_response"
            terminal_status = None
            resolution_reason = None
            observation_due = None
    elif action in ("defer", "dismiss"):
        phase = "observing"
        terminal_status = "completed"
        resolution_reason = "deferred" if action == "defer" else "dismissed"
        observation_due = None
    else:
        raise KernelCorruptionError(
            f"expected_response_result {response_id}: unknown action {action}"
        )

    # Verify next_card in card_index if present
    if next_card is not None:
        next_card_id = next_card.get("card_id")
        nc_rows = conn.execute(
            "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = ?",
            (next_card_id, event_id, next_rev_num),
        ).fetchall()
        if len(nc_rows) != 1:
            raise KernelCorruptionError(
                f"expected_response_result {response_id}: next_card {next_card_id} not in card_index r{next_rev_num}"
            )

    return {
        "kind": "response",
        "status": "accepted",
        "response_id": response_id,
        "card_id": card_id,
        "interaction_id": interaction_id,
        "revision": revision,
        "action": action,
        "next_card": next_card,
        "phase": phase,
        "terminal_status": terminal_status,
        "resolution_reason": resolution_reason,
        "observation_due_at_epoch": observation_due,
    }


def reconstruct_expected_aggregate_v1(
    stuck_row: sqlite3.Row,
    resolved_task: dict[str, Any],
    revisions: list[dict[str, Any]],
    response_messages: dict[str, sqlite3.Row],
    superseding_msg: sqlite3.Row | None,
    terminal_at_epoch: int | None,
    interaction_policy: Any,
) -> dict[str, Any]:
    """Rebuild the aggregate from scratch using contract reducers.

    Takes the Stuck SQL row (for message_id/recorded_at_epoch/event_id binding)
    and uses its recorded_at_epoch as the received_at_epoch for _new_interaction.

    Returns the reconstructed aggregate.  Callers MUST compare it against
    the persisted aggregate with canonical JSON.

    Wraps all ContractError / ValueError / TypeError as KernelCorruptionError.
    """
    try:
        policy_dict = interaction_policy.reducer_policy()
    except Exception as exc:
        raise KernelCorruptionError(
            f"reconstruct_aggregate: cannot derive policy dict: {exc}"
        )
    try:
        # 1. Decode Stuck payload from SQL row and validate bindings
        stuck_row_msg_id = _require_str(stuck_row["message_id"], "stuck_row.message_id")
        stuck_payload = _decode_message_payload_json(
            stuck_row["payload_json"], source="reconstruct stuck"
        )
        received_at = _require_int(stuck_row["recorded_at_epoch"], "stuck_row.recorded_at_epoch")
        if received_at <= 0:
            raise KernelCorruptionError(
                "reconstruct_aggregate: stuck_row.recorded_at_epoch must be positive"
            )

        # Validate Stuck message_id == payload.event_id
        stuck_event_id = stuck_payload.get("event_id")
        if stuck_row_msg_id != stuck_event_id:
            raise KernelCorruptionError(
                f"reconstruct_aggregate: stuck message_id {stuck_row_msg_id} "
                f"!= payload.event_id {stuck_event_id}"
            )

        c.validate_stuck_event(stuck_payload)

        # 2. _new_interaction
        state: dict[str, Any] = c._new_interaction(
            stuck_payload, received_at_epoch=received_at, policy=policy_dict,
        )

        # Validate Stuck recorded_at_epoch == aggregate request_received_at_epoch
        if received_at != state.get("request_received_at_epoch"):
            raise KernelCorruptionError(
                f"reconstruct_aggregate: stuck recorded_at {received_at} "
                f"!= aggregate request_received_at {state.get('request_received_at_epoch')}"
            )

        # 3. Validate resolved_task shape and fingerprint
        if not isinstance(resolved_task, dict):
            raise KernelCorruptionError("reconstruct_aggregate: resolved_task not a dict")
        expected_fp = c.task_fingerprint(resolved_task)

        # 4. _attach_resolved_task  (now_epoch = first context generated_at_epoch)
        if not revisions:
            raise KernelCorruptionError("reconstruct_aggregate: no revisions")
        first_ctx = revisions[0].get("context")
        if not isinstance(first_ctx, dict):
            raise KernelCorruptionError("reconstruct_aggregate: revision 1 has no context")
        first_ct = first_ctx.get("generated_at_epoch")
        if not isinstance(first_ct, int) or first_ct <= 0:
            raise KernelCorruptionError(
                "reconstruct_aggregate: revision 1 context missing generated_at_epoch"
            )
        state = c._attach_resolved_task(state, resolved_task, now_epoch=first_ct)

        # Verify fingerprint matches after attach
        if state.get("task_fingerprint") != expected_fp:
            raise KernelCorruptionError(
                f"reconstruct_aggregate: task_fingerprint mismatch: "
                f"{state.get('task_fingerprint')} != {expected_fp}"
            )

        # 5. Process each revision
        for rev in revisions:
            rev_ctx = rev.get("context")
            rev_prop = rev.get("proposal")
            rev_card = rev.get("card")
            if not isinstance(rev_ctx, dict):
                raise KernelCorruptionError(
                    f"reconstruct_aggregate: revision {rev.get('revision')} missing context"
                )
            if not isinstance(rev_prop, dict):
                raise KernelCorruptionError(
                    f"reconstruct_aggregate: revision {rev.get('revision')} missing proposal"
                )
            if not isinstance(rev_card, dict):
                raise KernelCorruptionError(
                    f"reconstruct_aggregate: revision {rev.get('revision')} missing card"
                )

            ctx_gen = rev_ctx.get("generated_at_epoch")
            card_issued = rev_card.get("issued_at_epoch")
            if not isinstance(ctx_gen, int) or ctx_gen <= 0:
                raise KernelCorruptionError(
                    f"reconstruct_aggregate: revision {rev.get('revision')} context missing generated_at_epoch"
                )
            if not isinstance(card_issued, int) or card_issued <= 0:
                raise KernelCorruptionError(
                    f"reconstruct_aggregate: revision {rev.get('revision')} card missing issued_at_epoch"
                )

            # 5a. _record_context_prepared
            state = c._record_context_prepared(
                state, rev_ctx, resolved_task, now_epoch=ctx_gen, policy=policy_dict,
            )
            if state.get("terminal_status") is not None:
                break
            # 5b. _record_proposal_validated
            state = c._record_proposal_validated(
                state, rev_prop, now_epoch=card_issued, policy=policy_dict,
            )
            if state.get("terminal_status") is not None:
                break
            # 5c. _record_card_published
            state = c._record_card_published(
                state, rev_card, now_epoch=card_issued,
                resolved_task=resolved_task, policy=policy_dict,
            )
            if state.get("terminal_status") is not None:
                break

            # 5d. Accepted Response
            rev_response = rev.get("response")
            if rev_response is not None:
                if not isinstance(rev_response, dict):
                    raise KernelCorruptionError(
                        f"reconstruct_aggregate: revision {rev.get('revision')} response not a dict"
                    )
                resp_id = rev_response.get("response_id")
                if not isinstance(resp_id, str):
                    raise KernelCorruptionError(
                        f"reconstruct_aggregate: revision {rev.get('revision')} response missing response_id"
                    )
                msg_row = response_messages.get(resp_id)
                if msg_row is None:
                    raise KernelCorruptionError(
                        f"reconstruct_aggregate: response {resp_id} not in response_messages"
                    )
                # Decode the public Response from the SQL payload
                public_response = _decode_message_payload_json(
                    msg_row["payload_json"], source=f"reconstruct response {resp_id}"
                )
                # Verify canonical full public payload matches stored payload_sha256
                if c._payload_sha256(public_response) != msg_row["payload_sha256"]:
                    raise KernelCorruptionError(
                        f"reconstruct_aggregate: response {resp_id} payload_sha256 mismatch"
                    )
                rr_epoch = rev_response.get("received_at_epoch")
                if not isinstance(rr_epoch, int) or rr_epoch <= 0:
                    raise KernelCorruptionError(
                        f"reconstruct_aggregate: revision {rev.get('revision')} response missing received_at_epoch"
                    )
                state = c._apply_response(
                    state, public_response, received_at_epoch=rr_epoch,
                    resolved_task=resolved_task, policy=policy_dict,
                )
            if state.get("terminal_status") is not None:
                break

        # 6. Superseding message (response not attached to any revision)
        if superseding_msg is not None and state.get("terminal_status") is None:
            superseding_payload = _decode_message_payload_json(
                superseding_msg["payload_json"], source="reconstruct superseding"
            )
            # Verify canonical full public payload matches stored payload_sha256
            if c._payload_sha256(superseding_payload) != superseding_msg["payload_sha256"]:
                raise KernelCorruptionError(
                    "reconstruct_aggregate: superseding payload_sha256 mismatch"
                )
            if terminal_at_epoch is None:
                raise KernelCorruptionError(
                    "reconstruct_aggregate: superseding_msg but terminal_at_epoch is None"
                )
            # Construct a different task (different fingerprint) to trigger supersession.
            different_task = p._make_distinct_resolved_task_for_supersession(resolved_task)
            state = c._apply_response(
                state, superseding_payload, received_at_epoch=terminal_at_epoch,
                resolved_task=different_task, policy=policy_dict,
            )

        # 7. Advance time if needed
        if state.get("terminal_status") is None and terminal_at_epoch is not None:
            state = c._advance_time(state, now_epoch=terminal_at_epoch, policy=policy_dict)

        return state

    except c.TaskInitiationContractError as exc:
        raise KernelCorruptionError(f"reconstruct_aggregate: {exc}") from exc
    except (ValueError, TypeError) as exc:
        raise KernelCorruptionError(f"reconstruct_aggregate: {exc}") from exc


# ---------------------------------------------------------------------------
# FK validation helper
# ---------------------------------------------------------------------------


def _check_fk(
    conn: sqlite3.Connection,
    table: str,
    ref_table: str,
    from_col: str,
    to_col: str,
) -> None:
    """Verify a FK constraint exists with correct target and cascading delete."""
    fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    for fk in fks:
        if (
            fk["from"].lower() == from_col.lower()
            and fk["table"].lower() == ref_table.lower()
            and fk["to"].lower() == to_col.lower()
        ):
            if fk["on_delete"] != "CASCADE":
                raise KernelCorruptionError(
                    f"FK {table}.{from_col}->{ref_table}.{to_col}: "
                    f"expected ON DELETE CASCADE, got {fk['on_delete']}"
                )
            return
    raise KernelCorruptionError(
        f"missing FK: {table}.{from_col} -> {ref_table}.{to_col}"
    )
