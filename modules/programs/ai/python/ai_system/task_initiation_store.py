"""Private SQLite store for the task-initiation kernel.

Owns: XDG path resolution, permission enforcement, journal-mode control,
explicit transaction boundaries, exact three-table migration, canonical
codec, owner-bundle replay validation, proportional corruption checking,
and read-only health inspection.

No public schema.  No ORM, framework, daemon, queue, or service.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class KernelNotFoundError(Exception):
    """Requested resource (interaction, Card, etc.) is absent."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class KernelRefusalError(Exception):
    """Deterministic non-persisted refusal (expired, conflict, invalid)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class KernelCorruptionError(Exception):
    """Persistence is malformed, incompatible, or cross-row inconsistent."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class KernelBusyError(Exception):
    """Database locked after the configured timeout."""

    pass


class KernelStorageError(Exception):
    """Permission, I/O, or commit failure."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


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

# Version-1 aggregate required keys
_REQUIRED_AGGREGATE_KEYS = frozenset({
    "event_id", "interaction_id", "phase", "terminal_status",
    "resolution_reason", "state_version",
})

_VALID_PHASES = frozenset({"awaiting_response", "observing"})
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
    )
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(data: Mapping[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_sha256(data: Mapping[str, Any]) -> str:
    return _sha256(_canonical_json(data))


def _decode_aggregate_json(raw: str, *, source: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KernelCorruptionError(f"{source}: invalid JSON: {exc}")
    if not isinstance(decoded, dict):
        raise KernelCorruptionError(f"{source}: aggregate is not a JSON object")
    return decoded


def _decode_message_result(raw: str, *, source: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KernelCorruptionError(f"{source}: invalid result JSON: {exc}")
    if not isinstance(decoded, dict):
        raise KernelCorruptionError(f"{source}: result is not a JSON object")
    if "ok" in decoded and "result" in decoded:
        decoded = decoded["result"]
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
    """Restore evidence_issues from arrays back to sets for reducer compatibility."""
    result = dict(data)
    if "evidence_issues" in result and isinstance(result["evidence_issues"], list):
        result["evidence_issues"] = set(result["evidence_issues"])
    if "revisions" in result:
        revisions = []
        for rev in result["revisions"]:
            r = dict(rev)
            if "evidence_issues" in r and isinstance(r["evidence_issues"], list):
                r["evidence_issues"] = set(r["evidence_issues"])
            revisions.append(r)
        result["revisions"] = revisions
    return result


def _agg_from_db(raw: str, *, source: str) -> dict[str, Any]:
    decoded = _decode_aggregate_json(raw, source=source)
    return _restore_evidence_sets(decoded)


def _agg_to_db(aggregate: Mapping[str, Any]) -> str:
    converted = _convert_evidence_issues(dict(aggregate))
    canonical_bytes = _canonical_json(converted)
    return canonical_bytes.decode("utf-8")


def _validate_aggregate_structure(
    aggregate: dict[str, Any], *, row_event_id: str | None = None
) -> None:
    """Validate the aggregate dict has required keys and coherent types."""
    for key in _REQUIRED_AGGREGATE_KEYS:
        if key not in aggregate:
            raise KernelCorruptionError(f"aggregate missing required key: {key}")

    event_id = _require_uuid4(aggregate["event_id"], "aggregate.event_id")
    if row_event_id is not None and event_id != row_event_id:
        raise KernelCorruptionError(
            f"aggregate event_id {event_id} != row event_id {row_event_id}"
        )

    _require_uuid4(aggregate["interaction_id"], "aggregate.interaction_id")


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


def connect_database(path: Path, *, busy_timeout_seconds: float) -> sqlite3.Connection:
    """Open a SQLite connection with explicit manual transaction control.

    ``isolation_level=None`` disables implicit legacy transactions.
    On Python with ``autocommit``, selects LEGACY_TRANSACTION_CONTROL.
    """
    kwargs: dict[str, Any] = {
        "timeout": busy_timeout_seconds,
        "isolation_level": None,
    }
    if hasattr(sqlite3, "LEGACY_TRANSACTION_CONTROL"):
        kwargs["autocommit"] = sqlite3.LEGACY_TRANSACTION_CONTROL
    connection = sqlite3.connect(str(path), **kwargs)
    connection.row_factory = sqlite3.Row
    return connection


def _check_permissions(path: Path, *, is_dir: bool = False) -> None:
    """Verify restrictive permissions and ownership.

    Directories must be mode 0700; files must be mode 0600.
    Symlinks are rejected.
    """
    if path.is_symlink():
        raise KernelStorageError(f"symlink not allowed: {path}")
    try:
        st = path.stat()
    except OSError as exc:
        raise KernelStorageError(f"cannot stat {path}: {exc}")
    mode = stat.S_IMODE(st.st_mode)
    expected = 0o700 if is_dir else 0o600
    # In test environments, umask may produce looser permissions.
    # Set the expected mode explicitly after creation; verify it here.
    if mode != expected:
        # Try to fix it
        try:
            os.chmod(path, expected)
            st = path.stat()
            mode = stat.S_IMODE(st.st_mode)
        except OSError:
            pass
    if mode != expected:
        raise KernelStorageError(
            f"file {path} has unexpected permissions: {oct(mode)}, expected {oct(expected)}"
        )


# ---------------------------------------------------------------------------
# TaskInitiationStore
# ---------------------------------------------------------------------------


class TaskInitiationStore:
    """Private XDG-local SQLite persistence for the task-initiation kernel.

    Owns: path resolution, permission enforcement, schema migration,
    explicit transactions, read-only connections, and health checks.
    """

    def __init__(self, state_dir: Path, *, busy_timeout_seconds: float) -> None:
        if not state_dir.is_absolute():
            raise KernelStorageError(f"state_dir must be absolute: {state_dir}")
        self._state_dir = state_dir
        self._db_path = state_dir / "kernel.sqlite3"
        self._busy_timeout = busy_timeout_seconds

    @property
    def database_path(self) -> Path:
        return self._db_path

    def initialize(self) -> dict[str, Any]:
        """Create app dir, open DB, set PRAGMAs, validate journal_mode, migrate.

        Idempotent: re-running on an existing valid database normalizes
        journal_mode back to DELETE.
        """
        self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        _check_permissions(self._state_dir, is_dir=True)

        conn = connect_database(self._db_path, busy_timeout_seconds=self._busy_timeout)

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
                # Existing database — validate semantically
                self._validate_v1_schema(conn)
                # Normalize journal_mode if it drifted
                pass  # Already set above
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

            if self._db_path.exists():
                _check_permissions(self._db_path, is_dir=False)

            return {"status": "initialized", "version": 1, "path": str(self._db_path)}

        finally:
            conn.close()

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        """Create version-1 schema in a single transaction."""
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA_DDL_STATEMENTS:
                conn.execute(statement)
            conn.execute("PRAGMA user_version = 1")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _validate_v1_schema(self, conn: sqlite3.Connection) -> None:
        """Semantically validate version-1 schema structure."""
        # Check user_version
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

        # Detailed index validation: check each expected index exists on its table
        for table_name in _EXPECTED_TABLE_NAMES:
            idx_list = conn.execute(
                f"PRAGMA index_list('{table_name}')"
            ).fetchall()
            for idx_row in idx_list:
                idx_name = idx_row["name"]
                if idx_name.startswith("sqlite_"):
                    continue
                if idx_name not in _EXPECTED_INDEX_NAMES:
                    raise KernelCorruptionError(
                        f"unexpected index: {idx_name} on {table_name}"
                    )
                if idx_name == "interactions_active_deadline_idx":
                    if idx_row["unique"] != 0:
                        raise KernelCorruptionError(
                            f"{idx_name}: expected non-unique index"
                        )
                    if idx_row["partial"] != 0:
                        raise KernelCorruptionError(
                            f"{idx_name}: expected non-partial index"
                        )

        # Validate index columns via index_xinfo (filter to key columns only)
        for idx_name in _EXPECTED_INDEX_NAMES:
            idx_cols = conn.execute(
                f"PRAGMA index_xinfo('{idx_name}')"
            ).fetchall()
            key_cols = [c for c in idx_cols if c["key"]]
            expected_idx_cols = _EXPECTED_ACTIVE_DEADLINE_COLS
            if len(key_cols) != len(expected_idx_cols):
                raise KernelCorruptionError(
                    f"{idx_name}: expected {len(expected_idx_cols)} key columns, got {len(key_cols)}"
                )
            for ec, ic in zip(expected_idx_cols, key_cols):
                if ic["name"].lower() != ec[1].lower():
                    raise KernelCorruptionError(
                        f"{idx_name}: column name {ic['name']} != expected {ec[1]}"
                    )

    @contextmanager
    def immediate_transaction(self) -> Iterator[sqlite3.Connection]:
        """Open writer, BEGIN IMMEDIATE, yield, commit/rollback, always close."""
        conn = connect_database(self._db_path, busy_timeout_seconds=self._busy_timeout)
        try:
            # Verify PRAGMAs
            conn.execute("PRAGMA foreign_keys = ON")
            fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
            if fk_row is None or fk_row[0] != 1:
                raise KernelStorageError("foreign_keys not enabled on writer")

            conn.execute("PRAGMA busy_timeout = %d" % int(self._busy_timeout * 1000))
            conn.execute("PRAGMA synchronous = 3")

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
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        """Open read-only connection with query_only=ON."""
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA foreign_keys = ON")

            jm_row = conn.execute("PRAGMA journal_mode").fetchone()
            if jm_row is None or jm_row[0].lower() != "delete":
                raise KernelStorageError(
                    f"journal_mode is {jm_row[0] if jm_row else 'unknown'}, expected delete"
                )

            yield conn
        finally:
            conn.close()

    def check_database(self) -> dict[str, Any]:
        """Read-only structural, integrity, and proportional row validation."""
        with self.read_connection() as conn:
            # Schema checks
            self._validate_v1_schema(conn)

            # Integrity
            integrity = conn.execute("PRAGMA integrity_check").fetchall()
            if [row[0] for row in integrity] != ["ok"]:
                raise KernelCorruptionError(f"integrity_check: {integrity}")

            fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_check:
                raise KernelCorruptionError(f"foreign_key_check: {fk_check}")

            # Validate each row
            interactions = conn.execute(
                "SELECT event_id FROM interactions ORDER BY event_id"
            ).fetchall()
            for row in interactions:
                self._validate_interaction_row(conn, row["event_id"])

            return {
                "status": "ok",
                "version": 1,
                "interaction_count": len(interactions),
            }

    # ------------------------------------------------------------------
    # Row validation
    # ------------------------------------------------------------------

    def _validate_interaction_row(
        self, conn: sqlite3.Connection, event_id: str
    ) -> None:
        """Proportional validation of one interaction row and its related rows."""
        int_row = conn.execute(
            "SELECT * FROM interactions WHERE event_id = ?", (event_id,)
        ).fetchone()
        if int_row is None:
            raise KernelCorruptionError(f"interaction {event_id} not found")

        # Decode and validate aggregate
        aggregate = _agg_from_db(int_row["aggregate_json"], source=f"interaction {event_id}")
        _validate_aggregate_structure(aggregate, row_event_id=event_id)
        _validate_revision_contiguity(aggregate)

        # Derived column agreement
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

        # Compute next_deadline_epoch from aggregate and verify
        expected_deadline = self._compute_next_deadline(aggregate)
        if expected_deadline != int_row["next_deadline_epoch"]:
            raise KernelCorruptionError(
                f"interaction {event_id}: next_deadline_epoch "
                f"{int_row['next_deadline_epoch']} != expected {expected_deadline}"
            )

        # Verify phase/terminal/deadline coherence
        if aggregate["phase"] == "observing" and aggregate.get("terminal_status") is None:
            if aggregate.get("observation_due_at_epoch") is None:
                raise KernelCorruptionError(
                    f"interaction {event_id}: observing without observation_due_at_epoch"
                )
        if aggregate.get("terminal_status") is not None:
            if int_row["next_deadline_epoch"] is not None:
                raise KernelCorruptionError(
                    f"interaction {event_id}: terminal but has next_deadline_epoch"
                )

        # Validate card_index correspondence
        card_rows = conn.execute(
            "SELECT * FROM card_index WHERE event_id = ? ORDER BY revision",
            (event_id,),
        ).fetchall()
        _validate_card_index_correspondence(aggregate, card_rows)

        # Validate message rows
        messages = conn.execute(
            "SELECT * FROM messages WHERE event_id = ?", (event_id,)
        ).fetchall()
        for msg_row in messages:
            self._validate_message_row(conn, msg_row, aggregate)

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
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            raise KernelCorruptionError(f"{source}: invalid payload_json")

        computed_hash = _payload_sha256(payload)
        if computed_hash != row["payload_sha256"]:
            raise KernelCorruptionError(
                f"{source}: payload_sha256 mismatch"
            )

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
            result = json.loads(row["result_json"])
        except json.JSONDecodeError:
            raise KernelCorruptionError(f"{source}: invalid result_json")
        if not isinstance(result, dict):
            raise KernelCorruptionError(f"{source}: result is not a dict")

    def validate_replay_bundle(
        self, conn: sqlite3.Connection, message_row: sqlite3.Row
    ) -> dict[str, Any]:
        """Owner-scoped replay validation.

        Loads the owning interaction, validates aggregate completeness,
        verifies payload/reservation/result consistency, checks Card routes,
        and returns the decoded immutable result. Raises KernelCorruptionError
        on any invalidity.
        """
        kind = message_row["kind"]
        message_id = message_row["message_id"]
        event_id = message_row["event_id"]

        # Load and validate the owner aggregate
        int_row = conn.execute(
            "SELECT * FROM interactions WHERE event_id = ?", (event_id,)
        ).fetchone()
        if int_row is None:
            raise KernelCorruptionError(
                f"replay {kind}:{message_id}: interaction {event_id} not found"
            )

        aggregate = _agg_from_db(int_row["aggregate_json"], source=f"replay {event_id}")
        _validate_aggregate_structure(aggregate, row_event_id=event_id)
        _validate_revision_contiguity(aggregate)

        # Full interaction row validation
        self._validate_interaction_row(conn, event_id)

        # Verify payload_sha256
        try:
            payload = json.loads(message_row["payload_json"])
        except json.JSONDecodeError:
            raise KernelCorruptionError(f"replay {kind}:{message_id}: invalid payload_json")

        computed_payload_hash = _payload_sha256(payload)
        if computed_payload_hash != message_row["payload_sha256"]:
            raise KernelCorruptionError(f"replay {kind}:{message_id}: payload_sha256 mismatch")

        # Verify reservation
        reservations = aggregate.get("message_reservations", {})
        key = f"{kind}:{message_id}"
        if reservations.get(key) != message_row["payload_sha256"]:
            raise KernelCorruptionError(f"replay {kind}:{message_id}: reservation mismatch")

        # Decode and validate result
        try:
            result = json.loads(message_row["result_json"])
        except json.JSONDecodeError:
            raise KernelCorruptionError(f"replay {kind}:{message_id}: invalid result_json")
        if not isinstance(result, dict):
            raise KernelCorruptionError(f"replay {kind}:{message_id}: result is not a dict")

        raw_result = result.get("result", result)
        if not isinstance(raw_result, dict):
            raise KernelCorruptionError(f"replay {kind}:{message_id}: result content is not a dict")

        # Kind-specific result checks
        if kind == "stuck":
            card = raw_result.get("card")
            if not isinstance(card, dict):
                raise KernelCorruptionError(f"replay stuck:{message_id}: result missing card")
            card_id = card.get("card_id")
            rev_rows = conn.execute(
                "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = 1",
                (card_id, event_id),
            ).fetchall()
            if len(rev_rows) != 1:
                raise KernelCorruptionError(
                    f"replay stuck:{message_id}: card_index missing for {card_id}"
                )

        elif kind == "response":
            status = raw_result.get("status")
            card_id = raw_result.get("card_id")
            revision = raw_result.get("revision")
            if card_id and revision:
                rev_rows = conn.execute(
                    "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = ?",
                    (card_id, event_id, revision),
                ).fetchall()

            if status == "accepted":
                # Must have the response in revisions
                found = False
                for rev in aggregate.get("revisions", []):
                    if rev.get("revision") == revision and rev.get("response"):
                        found = True
                        break
                if not found:
                    raise KernelCorruptionError(
                        f"replay response:{message_id}: accepted but no response in revisions"
                    )

                next_card = raw_result.get("next_card")
                if next_card is not None:
                    if not isinstance(next_card, dict):
                        raise KernelCorruptionError(f"replay response:{message_id}: next_card is not a dict")
                    next_card_id = next_card.get("card_id")
                    next_rev = revision + 1
                    nc_rows = conn.execute(
                        "SELECT * FROM card_index WHERE card_id = ? AND event_id = ? AND revision = ?",
                        (next_card_id, event_id, next_rev),
                    ).fetchall()
                    if len(nc_rows) != 1:
                        raise KernelCorruptionError(
                            f"replay response:{message_id}: next_card {next_card_id} not in card_index"
                        )

            elif status == "superseded":
                # Verify supersession in aggregate
                if aggregate.get("terminal_status") != "superseded":
                    raise KernelCorruptionError(
                        f"replay response:{message_id}: superseded result but aggregate not superseded"
                    )

        return raw_result

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
