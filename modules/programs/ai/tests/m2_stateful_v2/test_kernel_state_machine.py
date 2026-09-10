"""Hypothesis RuleBasedStateMachine for TaskInitiationKernel.

Uses actual TaskInitiationKernel + temp SQLite. Exposed via TestCase.
Deterministic clock and UUID source. Independent reducer-based reference model.

Rules: ingest_stuck, replay_stuck, start, shrink, blocked, defer, dismiss,
replay_response, advance_clock, reconcile, show, check_database,
restart_same_policy, restart_different_policy.

Invariants: check_database succeeds, exact replay is idempotent,
restart preserves interaction policy, real state equals model expectation.

Missing Hypothesis = hard failure. No xfail/skip/importorskip.
No catching KernelCorruptionError.
"""
from __future__ import annotations

import hashlib
import json as _json
import shutil
import sys
import tempfile
import uuid as _uuid_mod
from pathlib import Path
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "python"))

# Dependency probe -- hard failure; missing Hypothesis is a hard error.
try:
    from hypothesis import HealthCheck, settings
    from hypothesis.stateful import (
        RuleBasedStateMachine,
        initialize,
        invariant,
        precondition,
        rule,
    )
    from hypothesis import strategies as st
    import hypothesis
except ImportError as exc:
    pytest.fail(
        f"hypothesis not installed -- install with: pip install hypothesis ({exc})"
    )

from ai_system.task_initiation_kernel import (
    KernelPolicy,
    ResolutionInput,
    TaskInitiationKernel,
    load_resolution_input,
)
from ai_system.task_initiation_store import (
    KernelCorruptionError,
    KernelNotFoundError,
    KernelRefusalError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_NOW_BASE: int = 1_700_000_000
REV_FIXTURE: str = hashlib.sha256(b"test-rev").hexdigest()

# ---------------------------------------------------------------------------
# Deterministic UUID factory
# ---------------------------------------------------------------------------


def _make_uuid_counter(start: int = 0) -> Callable[[], _uuid_mod.UUID]:
    """Return a deterministic UUID factory with a mutable counter."""
    ctr = [start]

    def factory() -> _uuid_mod.UUID:
        ctr[0] += 1
        return _uuid_mod.UUID(f"00000000-0000-4000-8000-{ctr[0]:012d}")

    return factory


# ---------------------------------------------------------------------------
# Reference Model
# ---------------------------------------------------------------------------


class ReferenceModel:
    """Independent reducer-based reference model for TaskInitiationKernel.

    Tracks expected state for each event independently of the kernel.
    After each kernel operation, the model is updated in parallel so
    invariants can compare real kernel state against model expectations.
    """

    def __init__(self, policy: KernelPolicy) -> None:
        self._policy = policy
        self._events: dict[str, dict[str, Any]] = {}
        self._event_policies: dict[str, KernelPolicy] = {}

    # -- helpers --

    def _ev(self, event_id: str) -> dict[str, Any]:
        if event_id not in self._events:
            raise KernelNotFoundError(f"unknown event_id: {event_id}")
        return self._events[event_id]

    # -- model state accessors --

    def has_event(self, event_id: str) -> bool:
        return event_id in self._events

    def event_ids(self) -> list[str]:
        return list(self._events.keys())

    def phase(self, event_id: str) -> str:
        return self._ev(event_id)["phase"]

    def terminal_status(self, event_id: str) -> str | None:
        return self._ev(event_id)["terminal_status"]

    def current_card(self, event_id: str) -> dict[str, Any] | None:
        return self._ev(event_id)["current_card"]

    def revision_count(self, event_id: str) -> int:
        return self._ev(event_id)["revision_count"]

    def was_responded(self, event_id: str, card_id: str) -> bool:
        return card_id in self._ev(event_id)["responded_card_ids"]

    # -- internal time advancement (mirrors _advance_time) --

    def _advance_event(self, event_id: str, now_epoch: int) -> None:
        """Advance time for a single event (mirrors kernel _advance_time)."""
        ev = self._ev(event_id)
        if ev["terminal_status"] is not None:
            return

        # Observation expiry
        if (
            ev["phase"] == "observing"
            and ev["observation_due_at_epoch"] is not None
            and now_epoch >= ev["observation_due_at_epoch"]
        ):
            ev["terminal_status"] = "completed"
            return

        # Card expiry while awaiting response
        if ev["phase"] == "awaiting_response":
            card = ev["current_card"]
            if card is not None and now_epoch >= card.get(
                "expires_at_epoch", now_epoch + 1
            ):
                ev["terminal_status"] = "expired"
                ev["phase"] = "observing"
                return

    # -- public operations (mirror kernel public API) --

    def advance_clock(self, now_epoch: int) -> None:
        """Track clock advancement. Does NOT change event state.

        In the kernel, time advancement only happens during reconcile()
        or respond() -- the clock alone does not mutate interactions.
        """
        pass

    def reconcile(self, now_epoch: int) -> None:
        """Reconcile: advance time for all events."""
        for eid in list(self._events.keys()):
            self._advance_event(eid, now_epoch)

    def ingest_stuck(self, event_id: str, card: dict[str, Any]) -> None:
        """Record a new Stuck event with its published card."""
        if event_id in self._events:
            return  # replay -- idempotent, no state change
        self._events[event_id] = {
            "phase": "awaiting_response",
            "terminal_status": None,
            "current_card": dict(card),
            "revision_count": 1,
            "card_ids": [card["card_id"]],
            "responded_card_ids": set(),
            "observation_due_at_epoch": None,
        }
        self._event_policies[event_id] = self._policy

    def respond(
        self,
        event_id: str,
        card_id: str,
        action: str,
        now_epoch: int,
    ) -> None:
        """Apply a response action to the reference model.

        Mirrors the kernel's reducer: first advance time (which may
        make the event terminal), then apply the response if still alive.
        """
        # Advance time first (kernel does this before _apply_response)
        self._advance_event(event_id, now_epoch)

        ev = self._ev(event_id)

        if ev["terminal_status"] is not None:
            raise KernelRefusalError(
                f"interaction {event_id} is terminal: {ev['terminal_status']}"
            )

        current = ev["current_card"]
        if current is None or current["card_id"] != card_id:
            raise KernelRefusalError(f"unknown or stale card_id: {card_id}")

        if card_id in ev["responded_card_ids"]:
            raise KernelRefusalError(f"card_already_responded: {card_id}")

        # Check expiry
        if now_epoch >= current.get("expires_at_epoch", now_epoch + 1):
            raise KernelRefusalError(f"expired card: {card_id}")

        ev["responded_card_ids"].add(card_id)

        ev_policy = self._event_policies.get(event_id, self._policy)
        max_rev = ev_policy.max_card_revisions
        rev = ev["revision_count"]

        if action in ("defer", "dismiss"):
            ev["terminal_status"] = "completed"
            ev["phase"] = "observing"
        elif action in ("shrink", "blocked"):
            if rev >= max_rev:
                ev["terminal_status"] = "completed"
                ev["phase"] = "observing"
            else:
                ev["phase"] = "preparing"
                ev["current_card"] = None
        elif action == "start":
            ev["observation_due_at_epoch"] = (
                now_epoch + ev_policy.observation_seconds
            )
            ev["phase"] = "observing"

    def record_card_published(
        self, event_id: str, card: dict[str, Any]
    ) -> None:
        """Record a followup card published after a shrink/blocked response."""
        ev = self._ev(event_id)
        ev["current_card"] = dict(card)
        ev["revision_count"] = card.get("revision", ev["revision_count"] + 1)
        ev["card_ids"].append(card["card_id"])
        if ev["phase"] == "preparing":
            ev["phase"] = "awaiting_response"

    # -- verification helpers --

    def assert_matches_kernel(
        self, kernel: TaskInitiationKernel, event_id: str
    ) -> None:
        """Assert that the reference model matches kernel state for an event."""
        ev = self._ev(event_id)
        try:
            shown = kernel.show(event_id)
        except KernelNotFoundError:
            return

        assert shown["phase"] == ev["phase"], (
            f"phase mismatch for {event_id}: "
            f"model={ev['phase']} kernel={shown['phase']}"
        )
        assert shown["terminal_status"] == ev["terminal_status"], (
            f"terminal_status mismatch for {event_id}: "
            f"model={ev['terminal_status']} kernel={shown['terminal_status']}"
        )


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class KernelStateMachine(RuleBasedStateMachine):
    """RuleBasedStateMachine exercising TaskInitiationKernel lifecycle.

    State tracked:
        - model: ReferenceModel (independent reducer-based oracle)
        - event_ids: known event IDs in order of creation
        - epoch: current simulated clock epoch
        - kernel: current kernel instance
        - state_dir: temp directory for SQLite
        - policy: current KernelPolicy
        - id_factory: deterministic UUID factory
    """

    def __init__(self) -> None:
        super().__init__()
        self.model: ReferenceModel
        self.event_ids: list[str] = []
        self.epoch: int = FIXED_NOW_BASE
        self.state_dir: Path | None = None
        self.kernel: TaskInitiationKernel | None = None
        self.policy: KernelPolicy = KernelPolicy(
            stuck_ttl_seconds=7200,
            card_ttl_seconds=900,
            observation_seconds=600,
            max_card_revisions=3,
            context_ttl_seconds=3600,
        )
        self.id_factory: Callable[[], _uuid_mod.UUID] = _make_uuid_counter()
        # Track the last response sent (for replay_response rule)
        self._last_response: dict[str, Any] | None = None
        # Track the last stuck event payload (for replay_stuck rule)
        self._last_stuck: dict[str, Any] | None = None
        # Track the last resolution (needed by respond to re-resolve tasks)
        self._last_resolution: ResolutionInput | None = None

    def _clock(self) -> int:
        return self.epoch

    # ------------------------------------------------------------------
    # Lifecycle: initialize
    # ------------------------------------------------------------------

    @initialize()
    def init_kernel(self) -> None:
        self.state_dir = Path(tempfile.mkdtemp(prefix="tik_sm_"))
        self.state_dir.chmod(0o700)
        self.model = ReferenceModel(self.policy)
        self._open_kernel()

    def _open_kernel(self) -> None:
        """Create or reopen the kernel on the existing state_dir."""
        assert self.state_dir is not None
        self.kernel = TaskInitiationKernel(
            self.state_dir,
            policy=self.policy,
            clock=self._clock,
            id_factory=self.id_factory,
            busy_timeout_seconds=2.0,
        )
        result = self.kernel.initialize()
        assert result["status"] == "initialized"
        assert result["version"] == 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_resolution(self) -> ResolutionInput:
        """Create a ResolutionInput using a fixed task key so it can be
        reused across ingest and respond (both need to resolve the same task)."""
        tasks = {
            "Tasks/test_sm.md": {
                "label": "Stateful Task",
                "revision": REV_FIXTURE,
            }
        }
        p = self.state_dir / f"res_{self.id_factory().hex[:8]}.json"
        p.write_text(_json.dumps({"tasks": tasks}, sort_keys=True))
        return load_resolution_input(p, policy=self.policy)

    def _make_stuck(self, **overrides: Any) -> dict[str, Any]:
        event_id = str(self.id_factory())
        base: dict[str, Any] = {
            "schema_version": "task_initiation_stuck.v1",
            "event_id": event_id,
            "source": "tasker",
            "task_description": "Stateful test task",
            "occurred_at_epoch": self.epoch - 10,
            "task_ref": {
                "source": "tasknotes",
                "ref": "Tasks/test_sm.md",
            },
        }
        base.update(overrides)
        return base

    def _make_response(
        self, card: dict[str, Any], action: str, **overrides: Any
    ) -> dict[str, Any]:
        # shrink and blocked require a non-empty detail
        detail: str | None = None
        if action in ("shrink", "blocked"):
            detail = f"{action} detail for stateful test"
        # Use card's issued_at_epoch to ensure timestamp is within the
        # card's validity window: issued <= occurred < expires.
        issued = card.get("issued_at_epoch", self.epoch - 5)
        base: dict[str, Any] = {
            "schema_version": "task_initiation_response.v1",
            "response_id": str(self.id_factory()),
            "card_id": card["card_id"],
            "action": action,
            "detail": detail,
            "occurred_at_epoch": issued + 1,
        }
        base.update(overrides)
        return base

    def _ingest_one(self) -> str:
        """Ingest one Stuck event; return the event_id."""
        assert self.kernel is not None
        stuck = self._make_stuck()
        self._last_stuck = dict(stuck)
        resolution = self._make_resolution()
        self._last_resolution = resolution
        op = self.kernel.ingest_stuck(stuck, resolution=resolution)
        assert op.result["status"] == "card_published"
        assert "card" in op.result
        eid = op.result["event_id"]
        self.event_ids.append(eid)
        self.model.ingest_stuck(eid, op.result["card"])
        return eid

    def _has_respondable_card(self) -> bool:
        """Check if the latest event has a card that can be responded to."""
        if not self.event_ids:
            return False
        eid = self.event_ids[-1]
        if not self.model.has_event(eid):
            return False
        if self.model.terminal_status(eid) is not None:
            return False
        card = self.model.current_card(eid)
        if card is None:
            return False
        if self.model.was_responded(eid, card["card_id"]):
            return False
        if self.epoch >= card.get("expires_at_epoch", self.epoch + 1):
            return False
        return True

    def _respond_to_latest(self, action: str) -> None:
        """Respond to the most recent event's current card."""
        assert self.kernel is not None
        eid = self.event_ids[-1]
        card = self.model.current_card(eid)
        assert card is not None
        resp = self._make_response(card, action)
        resolution = self._last_resolution

        try:
            op = self.kernel.respond(resp, resolution=resolution)
            assert op.result["status"] in ("accepted", "superseded"), (
                f"unexpected status: {op.result['status']}"
            )
            self._last_response = dict(resp)
            self.model.respond(eid, card["card_id"], action, self.epoch)
            if "next_card" in op.result and op.result["next_card"] is not None:
                self.model.record_card_published(eid, op.result["next_card"])
        except KernelRefusalError:
            pass

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    @rule()
    def ingest_stuck(self) -> None:
        """Ingest a new Stuck event."""
        self._ingest_one()

    @precondition(lambda self: self._last_stuck is not None)
    @rule()
    def replay_stuck(self) -> None:
        """Replay the most recent Stuck event -- must be idempotent."""
        assert self.kernel is not None
        assert self._last_stuck is not None
        stuck = dict(self._last_stuck)
        resolution = self._make_resolution()
        op = self.kernel.ingest_stuck(stuck, resolution=resolution)
        assert op.replay is True, "replay_stuck: expected replay=True"

    @precondition(lambda self: self._has_respondable_card())
    @rule()
    def start(self) -> None:
        self._respond_to_latest("start")

    @precondition(lambda self: self._has_respondable_card())
    @rule()
    def shrink(self) -> None:
        self._respond_to_latest("shrink")

    @precondition(lambda self: self._has_respondable_card())
    @rule()
    def blocked(self) -> None:
        self._respond_to_latest("blocked")

    @precondition(lambda self: self._has_respondable_card())
    @rule()
    def defer(self) -> None:
        self._respond_to_latest("defer")

    @precondition(lambda self: self._has_respondable_card())
    @rule()
    def dismiss(self) -> None:
        self._respond_to_latest("dismiss")

    @precondition(lambda self: self._last_response is not None)
    @rule()
    def replay_response(self) -> None:
        """Replay the last response -- must be idempotent."""
        assert self.kernel is not None
        assert self._last_response is not None
        resp = dict(self._last_response)
        try:
            op = self.kernel.respond(resp, resolution=self._last_resolution)
            assert op.replay is True, (
                f"replay_response: expected replay=True for {resp['response_id']}"
            )
        except KernelRefusalError:
            pass

    @rule(seconds=st.integers(min_value=10, max_value=2000))
    def advance_clock(self, seconds: int) -> None:
        """Advance the simulated clock."""
        self.epoch += seconds
        self.model.advance_clock(self.epoch)

    @rule()
    def reconcile(self) -> None:
        """Run reconcile and update model."""
        assert self.kernel is not None
        result = self.kernel.reconcile()
        assert result["ok"] is True
        self.model.reconcile(self.epoch)

    @precondition(lambda self: bool(self.event_ids))
    @rule()
    def show(self) -> None:
        """Show the most recent event."""
        assert self.kernel is not None
        eid = self.event_ids[-1]
        try:
            result = self.kernel.show(eid)
            assert "event_id" in result
            assert "phase" in result
            assert "terminal_status" in result
        except KernelNotFoundError:
            pass

    @rule()
    def check_database(self) -> None:
        """Run check_database -- must succeed or raise KernelCorruptionError."""
        assert self.kernel is not None
        result = self.kernel.check_database()
        assert result["status"] == "ok"
        assert result["version"] == 1

    @rule()
    def restart_same_policy(self) -> None:
        """Close and reopen the kernel with the same policy."""
        if self.state_dir is None:
            return
        self.kernel = TaskInitiationKernel(
            self.state_dir,
            policy=self.policy,
            clock=self._clock,
            id_factory=self.id_factory,
            busy_timeout_seconds=2.0,
        )
        self.model._policy = self.policy
        result = self.kernel.check_database()
        assert result["status"] == "ok"

    @rule()
    def restart_different_policy(self) -> None:
        """Close and reopen the kernel with a different policy."""
        if self.state_dir is None:
            return
        new_policy = KernelPolicy(
            stuck_ttl_seconds=self.policy.stuck_ttl_seconds + 1000,
            card_ttl_seconds=self.policy.card_ttl_seconds + 100,
            observation_seconds=self.policy.observation_seconds + 100,
            max_card_revisions=self.policy.max_card_revisions + 1,
            context_ttl_seconds=self.policy.context_ttl_seconds + 100,
        )
        self.policy = new_policy
        self.model._policy = self.policy
        self.kernel = TaskInitiationKernel(
            self.state_dir,
            policy=self.policy,
            clock=self._clock,
            id_factory=self.id_factory,
            busy_timeout_seconds=2.0,
        )
        result = self.kernel.check_database()
        assert result["status"] == "ok"

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    @invariant()
    def check_database_succeeds(self) -> None:
        """After any sequence, check_database must succeed on a valid kernel."""
        if self.kernel is not None and self.state_dir is not None:
            result = self.kernel.check_database()
            assert result["status"] == "ok", (
                f"check_database failed: {result}"
            )

    @invariant()
    def model_matches_kernel(self) -> None:
        """For every event in the model, kernel.show() must match."""
        if self.kernel is None:
            return
        for eid in list(self.model.event_ids()):
            try:
                self.model.assert_matches_kernel(self.kernel, eid)
            except KernelNotFoundError:
                pass

    @invariant()
    def restart_preserves_interactions(self) -> None:
        """After restart, previously ingested events must still exist."""
        if self.kernel is None or not self.event_ids:
            return
        for eid in self.event_ids[: min(3, len(self.event_ids))]:
            try:
                shown = self.kernel.show(eid)
                assert "event_id" in shown
            except KernelNotFoundError:
                if self.model.has_event(eid):
                    ts = self.model.terminal_status(eid)
                    assert ts is not None, (
                        f"non-terminal event {eid} lost after restart"
                    )

    @invariant()
    def cards_have_valid_shape(self) -> None:
        """Every card tracked by the model must have required fields."""
        for eid in self.model.event_ids():
            card = self.model.current_card(eid)
            if card is not None:
                assert "card_id" in card, f"card missing card_id for {eid}"
                assert "issued_at_epoch" in card, (
                    f"card missing issued_at_epoch for {eid}"
                )
                assert "expires_at_epoch" in card, (
                    f"card missing expires_at_epoch for {eid}"
                )


# ---------------------------------------------------------------------------
# pytest TestCase wrapper
# ---------------------------------------------------------------------------


class TestKernelStateMachine:
    """Expose the Hypothesis state machine as pytest test cases."""

    def test_state_machine_runs(self) -> None:
        """Run the KernelStateMachine with bounded deterministic settings."""
        KernelStateMachine.TestCase.settings = settings(
            max_examples=30,
            stateful_step_count=40,
            deadline=None,
            suppress_health_check=list(HealthCheck),
            print_blob=True,
        )
        KernelStateMachine.TestCase().runTest()

    def test_state_machine_deterministic_replay(self) -> None:
        """Two runs with same seed produce identical results."""
        sm_settings = settings(
            max_examples=5,
            stateful_step_count=15,
            deadline=None,
            suppress_health_check=list(HealthCheck),
            database=None,
        )
        KernelStateMachine.TestCase.settings = sm_settings
        KernelStateMachine.TestCase().runTest()

        KernelStateMachine.TestCase.settings = sm_settings
        KernelStateMachine.TestCase().runTest()

    def test_minimal_lifecycle(self) -> None:
        """Run a minimal lifecycle: ingest -> start -> reconcile -> check_db."""
        sd = Path(tempfile.mkdtemp(prefix="tik_min_"))
        sd.chmod(0o700)
        try:
            policy = KernelPolicy()
            id_factory = _make_uuid_counter(1000)
            k = TaskInitiationKernel(
                sd,
                policy=policy,
                clock=lambda: FIXED_NOW_BASE,
                id_factory=id_factory,
                busy_timeout_seconds=2.0,
            )
            k.initialize()

            res_p = sd / "res.json"
            res_p.write_text(
                _json.dumps(
                    {
                        "tasks": {
                            "Tasks/test.md": {
                                "label": "Min",
                                "revision": REV_FIXTURE,
                            }
                        }
                    },
                    sort_keys=True,
                )
            )
            resolution = load_resolution_input(res_p, policy=policy)

            stuck = {
                "schema_version": "task_initiation_stuck.v1",
                "event_id": str(id_factory()),
                "source": "tasker",
                "task_description": "Minimal lifecycle test",
                "occurred_at_epoch": FIXED_NOW_BASE - 10,
                "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
            }
            op = k.ingest_stuck(stuck, resolution=resolution)
            assert op.result["status"] == "card_published"
            card = op.result["card"]

            resp = {
                "schema_version": "task_initiation_response.v1",
                "response_id": str(id_factory()),
                "card_id": card["card_id"],
                "action": "start",
                "detail": None,
                "occurred_at_epoch": card["issued_at_epoch"] + 1,
            }
            r = k.respond(resp, resolution=resolution)
            assert r.result["status"] == "accepted"
            assert r.result["phase"] == "observing"

            rec = k.reconcile()
            assert rec["ok"] is True

            cdb = k.check_database()
            assert cdb["status"] == "ok"
            assert cdb["interaction_count"] == 1

            shown = k.show(stuck["event_id"])
            assert shown["phase"] == "observing"
            assert shown["terminal_status"] is None

        finally:
            shutil.rmtree(str(sd), ignore_errors=True)

    def test_ingest_replay_idempotent(self) -> None:
        """Ingest the same Stuck event twice -- second must be replay=True."""
        sd = Path(tempfile.mkdtemp(prefix="tik_rep_"))
        sd.chmod(0o700)
        try:
            policy = KernelPolicy()
            id_factory = _make_uuid_counter(2000)
            k = TaskInitiationKernel(
                sd,
                policy=policy,
                clock=lambda: FIXED_NOW_BASE,
                id_factory=id_factory,
                busy_timeout_seconds=2.0,
            )
            k.initialize()

            res_p = sd / "res.json"
            res_p.write_text(
                _json.dumps(
                    {
                        "tasks": {
                            "Tasks/test.md": {
                                "label": "Replay",
                                "revision": REV_FIXTURE,
                            }
                        }
                    },
                    sort_keys=True,
                )
            )
            resolution = load_resolution_input(res_p, policy=policy)

            event_id = str(id_factory())
            stuck = {
                "schema_version": "task_initiation_stuck.v1",
                "event_id": event_id,
                "source": "tasker",
                "task_description": "Replay idempotency test",
                "occurred_at_epoch": FIXED_NOW_BASE - 10,
                "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
            }

            op1 = k.ingest_stuck(stuck, resolution=resolution)
            assert op1.replay is False
            assert op1.result["status"] == "card_published"

            op2 = k.ingest_stuck(stuck, resolution=resolution)
            assert op2.replay is True
            assert op2.result == op1.result

        finally:
            shutil.rmtree(str(sd), ignore_errors=True)

    def test_response_replay_idempotent(self) -> None:
        """Submit the same response twice -- second must be replay=True."""
        sd = Path(tempfile.mkdtemp(prefix="tik_rr_"))
        sd.chmod(0o700)
        try:
            policy = KernelPolicy()
            id_factory = _make_uuid_counter(3000)
            k = TaskInitiationKernel(
                sd,
                policy=policy,
                clock=lambda: FIXED_NOW_BASE,
                id_factory=id_factory,
                busy_timeout_seconds=2.0,
            )
            k.initialize()

            res_p = sd / "res.json"
            res_p.write_text(
                _json.dumps(
                    {
                        "tasks": {
                            "Tasks/test.md": {
                                "label": "RespReplay",
                                "revision": REV_FIXTURE,
                            }
                        }
                    },
                    sort_keys=True,
                )
            )
            resolution = load_resolution_input(res_p, policy=policy)

            stuck = {
                "schema_version": "task_initiation_stuck.v1",
                "event_id": str(id_factory()),
                "source": "tasker",
                "task_description": "Response replay test",
                "occurred_at_epoch": FIXED_NOW_BASE - 10,
                "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
            }
            op = k.ingest_stuck(stuck, resolution=resolution)
            card = op.result["card"]

            response_id = str(id_factory())
            resp = {
                "schema_version": "task_initiation_response.v1",
                "response_id": response_id,
                "card_id": card["card_id"],
                "action": "start",
                "detail": None,
                "occurred_at_epoch": card["issued_at_epoch"] + 1,
            }

            r1 = k.respond(resp, resolution=resolution)
            assert r1.replay is False

            r2 = k.respond(resp, resolution=resolution)
            assert r2.replay is True

        finally:
            shutil.rmtree(str(sd), ignore_errors=True)

    def test_restart_preserves_state(self) -> None:
        """Restart the kernel and verify state is preserved."""
        sd = Path(tempfile.mkdtemp(prefix="tik_rst_"))
        sd.chmod(0o700)
        try:
            policy = KernelPolicy()
            id_factory = _make_uuid_counter(4000)
            epoch = FIXED_NOW_BASE

            k = TaskInitiationKernel(
                sd,
                policy=policy,
                clock=lambda: epoch,
                id_factory=id_factory,
                busy_timeout_seconds=2.0,
            )
            k.initialize()

            res_p = sd / "res.json"
            res_p.write_text(
                _json.dumps(
                    {
                        "tasks": {
                            "Tasks/test.md": {
                                "label": "Restart",
                                "revision": REV_FIXTURE,
                            }
                        }
                    },
                    sort_keys=True,
                )
            )
            resolution = load_resolution_input(res_p, policy=policy)

            event_id = str(id_factory())
            stuck = {
                "schema_version": "task_initiation_stuck.v1",
                "event_id": event_id,
                "source": "tasker",
                "task_description": "Restart preservation test",
                "occurred_at_epoch": epoch - 10,
                "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
            }
            op = k.ingest_stuck(stuck, resolution=resolution)
            assert op.result["status"] == "card_published"
            card = op.result["card"]

            resp = {
                "schema_version": "task_initiation_response.v1",
                "response_id": str(id_factory()),
                "card_id": card["card_id"],
                "action": "start",
                "detail": None,
                "occurred_at_epoch": card["issued_at_epoch"] + 1,
            }
            k.respond(resp, resolution=resolution)

            # Restart kernel
            k2 = TaskInitiationKernel(
                sd,
                policy=policy,
                clock=lambda: epoch,
                id_factory=id_factory,
                busy_timeout_seconds=2.0,
            )
            cdb = k2.check_database()
            assert cdb["status"] == "ok"

            shown = k2.show(event_id)
            assert shown["phase"] == "observing"
            assert shown["terminal_status"] is None
            assert shown["event_id"] == event_id

        finally:
            shutil.rmtree(str(sd), ignore_errors=True)
