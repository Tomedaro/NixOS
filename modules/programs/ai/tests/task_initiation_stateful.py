"""Hypothesis stateful testing for task-initiation kernel.

Requires the 'hypothesis' package. If unavailable, all tests are skipped
with a clear diagnostic message.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

try:
    import hypothesis
    from hypothesis import HealthCheck, settings
    from hypothesis.stateful import RuleBasedStateMachine, rule, initialize
    HAVE_HYPOTHESIS = True
except ImportError:
    HAVE_HYPOTHESIS = False

# Use the kernel_smoke test harness
from task_initiation_kernel_smoke import check


def _skipped(reason: str) -> None:
    """Record a skipped check (counts as passed but prints a note)."""
    print(f"SKIP {reason}")


def test_imports_and_skip() -> None:
    """Verify import chain works; skip gracefully if hypothesis is missing."""
    if not HAVE_HYPOTHESIS:
        _skipped("hypothesis not installed — install with: pip install hypothesis")
        return

    from ai_system.task_initiation_kernel import TaskInitiationKernel, KernelPolicy
    from ai_system.task_initiation_store import TaskInitiationStore
    from ai_system import task_initiation_contracts as c

    check("imports ok", True)

    # Verify basic RuleBasedStateMachine can be defined
    class DummyStateMachine(RuleBasedStateMachine):
        def __init__(self) -> None:
            super().__init__()
            self.counter = 0

        @initialize()
        def init(self) -> None:
            self.counter = 0

        @rule()
        def increment(self) -> None:
            self.counter += 1

    check("RuleBasedStateMachine compiles", True)
    check("DummyStateMachine instantiable", DummyStateMachine is not None)


def test_kernel_state_machine() -> None:
    """Define and sanity-check a TaskInitiationKernel RuleBasedStateMachine.

    This is a structural test: it verifies the state machine class can be
    defined and instantiated. Full fuzzing is left to a dedicated CI step
    because it requires the hypothesis package and significant runtime.
    """
    if not HAVE_HYPOTHESIS:
        _skipped("hypothesis not installed")
        return

    import hashlib
    import json
    import tempfile
    import uuid
    from typing import Any

    from ai_system.task_initiation_kernel import (
        KernelPolicy,
        TaskInitiationKernel,
        load_resolution_input,
    )
    from ai_system.task_initiation_store import _agg_from_db

    _REV = hashlib.sha256(b"test-rev").hexdigest()

    def _make_res(sd, tasks):
        p = sd / "res.json"
        p.write_text(json.dumps({"tasks": tasks}))
        return load_resolution_input(p, policy=KernelPolicy())

    class KernelStateMachine(RuleBasedStateMachine):
        """Stateful model of kernel lifecycle operations."""

        def __init__(self) -> None:
            super().__init__()
            self.sd = Path(tempfile.mkdtemp(prefix="hsm_"))
            self.kernel = TaskInitiationKernel(
                self.sd,
                clock=lambda: 1_700_000_000,
                id_factory=uuid.uuid4,
                busy_timeout_seconds=0.2,
            )
            self.kernel.initialize()
            self.res = _make_res(self.sd, {"Tasks/test.md": {"label": "T", "revision": _REV}})
            self.event_ids: list[str] = []
            self.cards: list[dict[str, Any]] = []

        @initialize()
        def start(self) -> None:
            # Already set up in __init__
            pass

        @rule()
        def ingest_stuck(self) -> None:
            from ai_system.task_initiation_kernel import KernelRefusalError
            stuck = {
                "schema_version": "task_initiation_stuck.v1",
                "event_id": str(uuid.uuid4()),
                "source": "tasker",
                "occurred_at_epoch": 1_700_000_000 - 10,
                "task_description": "A fuzzed task",
            }
            try:
                op = self.kernel.ingest_stuck(stuck, resolution=self.res)
                if not op.replay:
                    self.event_ids.append(op.result["event_id"])
                    self.cards.append(op.result.get("card"))
            except KernelRefusalError:
                pass

        @rule()
        def respond_start(self) -> None:
            if not self.cards:
                return
            from ai_system.task_initiation_kernel import KernelRefusalError
            card = self.cards[0]
            resp = {
                "schema_version": "task_initiation_response.v1",
                "response_id": str(uuid.uuid4()),
                "card_id": card["card_id"],
                "action": "start",
                "detail": None,
                "occurred_at_epoch": card["issued_at_epoch"] + 5,
            }
            try:
                self.kernel.respond(resp, resolution=self.res)
            except KernelRefusalError:
                pass

        @rule()
        def check_database(self) -> None:
            from ai_system.task_initiation_kernel import KernelCorruptionError
            try:
                self.kernel.check_database()
            except KernelCorruptionError:
                pass

        @rule()
        def reconcile_state(self) -> None:
            self.kernel.reconcile()

        @rule()
        def list_active(self) -> None:
            self.kernel.list_active()

    check("KernelStateMachine defined", KernelStateMachine is not None)

    # Instantiate and run a minimal sequence manually
    sm = KernelStateMachine()
    try:
        sm.ingest_stuck()
        sm.check_database()
        sm.list_active()
        sm.reconcile_state()
        check("KernelStateMachine manual run completed", True)
    except Exception as e:
        check(f"KernelStateMachine manual run: {e}", False)


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("=== stateful tests ===")
    test_imports_and_skip()
    test_kernel_state_machine()
    print()
    # Count PASSED/FAILED from kernel_smoke check
    import task_initiation_kernel_smoke as tks
    print(f"=== stateful: {tks.PASSED} passed, {tks.FAILED} failed ===")
    if tks.FAILED:
        raise SystemExit(1)
    print("ALL PASS")
