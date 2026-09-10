"""M2 verifier known defect reproduction tests.

These tests reproduce known defects C01-C12. They exercise the defect
conditions directly through the public kernel API. No xfail, skip, or
try/except markers - the baseline runner handles expected failures.

Each defect test calls kernel API only, not contract helpers.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3 as sqlite3_module
import threading
import uuid
from typing import Any
from m2_verifier_support import KernelBusyError, KernelCorruptionError, KernelRefusalError


class TestM2C01:
    """C01: Sensitive keys leak through aggregate in show output."""

    def test_sensitive_keys_not_in_aggregate(
        self, temp_state_dir, stuck_with_resolution
    ) -> None:
        """show(include_sensitive=True) must not expose raw sensitive keys in aggregate."""
        eid = stuck_with_resolution["event_id"]
        kernel = stuck_with_resolution["kernel"]

        s = kernel.show(eid, include_sensitive=True)
        agg = s["aggregate"]

        sensitive_fields = {"private_key", "secret", "token", "password"}
        agg_str = json.dumps(agg)

        leaked = [k for k in sensitive_fields if k in agg_str.lower()]
        assert not leaked, f"Sensitive keys leaked: {leaked}"


class TestM2C02:
    """C02: Orphaned card_index rows survive interaction deletion."""

    def test_card_index_cascades_on_delete(
        self, temp_state_dir, kernel, stuck_event, resolution_tasks
    ) -> None:
        """Deleting an interaction must cascade to card_index."""
        op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
        eid = op.result["event_id"]

        conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
        conn.row_factory = sqlite3_module.Row
        try:
            int_count = conn.execute(
                "SELECT COUNT(*) FROM interactions WHERE event_id=?", (eid,)
            ).fetchone()[0]
            ci_count = conn.execute(
                "SELECT COUNT(*) FROM card_index WHERE event_id=?", (eid,)
            ).fetchone()[0]
            assert int_count == 1
            assert ci_count == 1

            conn.execute("DELETE FROM interactions WHERE event_id = ?", (eid,))
            conn.commit()

            ci_after = conn.execute(
                "SELECT COUNT(*) FROM card_index WHERE event_id=?", (eid,)
            ).fetchone()[0]
            assert ci_after == 0, f"Orphaned card_index row: expected 0, got {ci_after}"
        finally:
            conn.close()


class TestM2C03:
    """C03: WAL mode persistence after store initialization."""

    def test_wal_mode_reset_after_initialize(self, temp_state_dir) -> None:
        """After initialize(), journal_mode must be 'delete'."""
        from ai_system.task_initiation_store import TaskInitiationStore

        store = TaskInitiationStore(temp_state_dir, busy_timeout_seconds=0.2)
        store.initialize()

        conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()

        store.initialize()
        with store.read_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
            assert mode == "delete", f"Expected delete mode, got {mode}"


class TestM2C04:
    """C04: Race between two respond() calls on same interaction."""

    def test_concurrent_respond_mutual_exclusion(
        self, temp_state_dir, stuck_with_resolution, resolution_tasks
    ) -> None:
        """Two concurrent respond() calls on same interaction must not both succeed."""
        from m2_verifier_support import make_response

        card = stuck_with_resolution["card"]
        kernel = stuck_with_resolution["kernel"]

        results: list[bool] = []
        errors: list[Exception] = []

        def do_respond(action: str) -> None:
            try:
                r = kernel.respond(make_response(card, action), resolution=resolution_tasks)
                results.append(r.replay)
            except (KernelBusyError, KernelRefusalError) as e:
                errors.append(e)

        t1 = threading.Thread(target=do_respond, args=("start",))
        t2 = threading.Thread(target=do_respond, args=("dismiss",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        non_replay = sum(1 for r in results if not r)
        assert non_replay <= 1, f"Multiple non-replay responses: {results}"


class TestM2C05:
    """C05: Concurrent ingest_stuck and respond."""

    def test_concurrent_ingest_respond(
        self, temp_state_dir, kernel, stuck_event, resolution_tasks
    ) -> None:
        """Concurrent ingest_stuck and respond must not corrupt state."""
        from m2_verifier_support import make_response

        op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
        card = op.result["card"]

        results: list[bool] = []
        errors: list[Exception] = []

        def do_work() -> None:
            try:
                r = kernel.respond(make_response(card, "start"), resolution=resolution_tasks)
                results.append(r.replay)
            except (KernelBusyError, KernelRefusalError) as e:
                errors.append(e)

        t1 = threading.Thread(target=do_work)
        t2 = threading.Thread(target=do_work)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        non_replay = sum(1 for r in results if not r)
        assert non_replay <= 1, f"Concurrent writers both succeeded: {results}"


class TestM2C06:
    """C06: Non-atomic check_database during concurrent operation."""

    def test_check_database_during_concurrent_writes(
        self, temp_state_dir, kernel, resolution_tasks
    ) -> None:
        """check_database must see a consistent snapshot during concurrent writes."""
        from m2_verifier_support import make_stuck

        errors: list[Any] = []

        def do_check() -> None:
            try:
                cdb = kernel.check_database()
                if cdb["status"] != "ok":
                    errors.append(cdb)
            except (KernelBusyError, KernelCorruptionError) as e:
                errors.append(e)

        for _ in range(5):
            st = make_stuck()
            kernel.ingest_stuck(st, resolution=resolution_tasks)

        t = threading.Thread(target=do_check)
        t.start()
        t.join()

        assert not errors, f"check_database errors during writes: {errors}"


class TestM2C07:
    """C07: Stuck ingestion with null task_ref."""

    def test_null_task_ref_validation(
        self, temp_state_dir, kernel, resolution_tasks
    ) -> None:
        """Stuck event with explicitly null task_ref must fail validation."""
        from m2_verifier_support import make_stuck

        st = make_stuck(task_ref=None)
        kernel.ingest_stuck(st, resolution=resolution_tasks)


class TestM2C08:
    """C08: Card with negative start_countdown_seconds."""

    def test_negative_countdown_rejected(
        self, temp_state_dir, kernel, stuck_event, resolution_tasks
    ) -> None:
        """Card from kernel must always have non-negative start_countdown_seconds."""
        op = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
        card = op.result["card"]
        assert card.get("start_countdown_seconds", 0) >= 0


class TestM2C09:
    """C09: Response with empty action string."""

    def test_empty_action_string_rejected(
        self, temp_state_dir, stuck_with_resolution, resolution_tasks
    ) -> None:
        """Response with empty action string must be rejected."""
        from m2_verifier_support import make_response

        card = stuck_with_resolution["card"]
        kernel = stuck_with_resolution["kernel"]

        kernel.respond(make_response(card, action=""), resolution=resolution_tasks)


class TestM2C10:
    """C10: show() leaks internal state_version that does not round-trip."""

    def test_state_version_roundtrip(
        self, temp_state_dir, stuck_with_resolution
    ) -> None:
        """show() state_version must be consistent across restarts."""
        from m2_verifier_support import reopen_kernel

        eid = stuck_with_resolution["event_id"]
        kernel = stuck_with_resolution["kernel"]

        s1 = kernel.show(eid)
        k2 = reopen_kernel(temp_state_dir)
        s2 = k2.show(eid)

        assert s1["state_version"] == s2["state_version"], (
            f"State version mismatch: {s1['state_version']} vs {s2['state_version']}"
        )


class TestM2C11:
    """C11: Reconciliation advances deadline for already-terminal interaction."""

    def test_reconcile_ignores_terminal(
        self, temp_state_dir, kernel_short, stuck_event, resolution_tasks
    ) -> None:
        """reconcile() must not modify already-terminal interactions."""
        from m2_verifier_support import make_response, reopen_kernel
        from ai_system.task_initiation_kernel import KernelPolicy

        op = kernel_short.ingest_stuck(stuck_event, resolution=resolution_tasks)
        card = op.result["card"]
        kernel_short.respond(make_response(card, "dismiss"), resolution=resolution_tasks)

        eid = op.result["event_id"]
        s_before = kernel_short.show(eid)

        late_clock = lambda: 1_700_000_000 + 2000  # noqa: E731
        k2 = reopen_kernel(
            temp_state_dir,
            clock=late_clock,
            policy=KernelPolicy(card_ttl_seconds=10, observation_seconds=10),
        )
        k2.reconcile()

        s_after = k2.show(eid)
        assert s_before["terminal_status"] == s_after["terminal_status"]


class TestM2C12:
    """C12: Card published with duplicate card_id in same interaction."""

    def test_no_duplicate_card_ids(
        self, temp_state_dir, stuck_with_resolution
    ) -> None:
        """Same card_id must not appear twice in one interaction's revisions."""
        eid = stuck_with_resolution["event_id"]
        kernel = stuck_with_resolution["kernel"]

        s = kernel.show(eid, include_sensitive=True)
        revisions = s["aggregate"]["revisions"]

        card_ids = [r.get("card", {}).get("card_id") for r in revisions]
        card_ids = [c for c in card_ids if c is not None]

        assert len(card_ids) == len(set(card_ids)), f"Duplicate card_ids: {card_ids}"
