"""Shared pytest fixtures for Milestone 2 public acceptance tests.

Provides fixtures for temporary state directories, kernel instances,
and factory helpers for Stuck events and Resolution data. Uses only
pytest conventions — no script-style check/raises/PASSED/FAILED globals
and no test execution at import time.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from ai_system import task_initiation_contracts as c
from ai_system.task_initiation_kernel import (
    KernelPolicy,
    OperationResult,
    ResolutionInput,
    TaskInitiationKernel,
    load_resolution_input,
)
from ai_system.task_initiation_store import (
    KernelBusyError,
    KernelCorruptionError,
    KernelNotFoundError,
    KernelRefusalError,
    KernelStorageError,
    TaskInitiationStore,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_NOW_BASE: int = 1_700_000_000
REV_FIXTURE: str = hashlib.sha256(b"test-rev").hexdigest()
REV_FIXTURE2: str = hashlib.sha256(b"test-rev2").hexdigest()

# ---------------------------------------------------------------------------
# Private helpers (not fixtures, usable inside fixtures)
# ---------------------------------------------------------------------------

_uuid_ctr: int = 0


def _fixed_clock() -> int:
    return FIXED_NOW_BASE


def _fixed_id_factory() -> uuid.UUID:
    global _uuid_ctr
    _uuid_ctr += 1
    return uuid.UUID(f"00000000-0000-4000-8000-{_uuid_ctr:012d}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_state_dir() -> Path:
    """Create a disposable temporary directory for kernel state.

    The directory is cleaned up after the test completes.
    """
    d = Path(tempfile.mkdtemp(prefix="m2pub_"))
    yield d
    import shutil

    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def default_policy() -> KernelPolicy:
    """Return the default KernelPolicy."""
    return KernelPolicy()


@pytest.fixture
def short_policy() -> KernelPolicy:
    """Return a policy with short observation and card TTL for faster tests."""
    return KernelPolicy(
        card_ttl_seconds=10,
        observation_seconds=10,
        stuck_ttl_seconds=60,
    )


@pytest.fixture
def kernel(temp_state_dir: Path, default_policy: KernelPolicy) -> TaskInitiationKernel:
    """Create an initialized kernel with fixed clock and default policy.

    Each test gets a fresh isolated kernel.
    """
    k = TaskInitiationKernel(
        temp_state_dir,
        policy=default_policy,
        clock=_fixed_clock,
        busy_timeout_seconds=0.2,
    )
    k.initialize()
    return k


@pytest.fixture
def kernel_short(
    temp_state_dir: Path, short_policy: KernelPolicy
) -> TaskInitiationKernel:
    """Create an initialized kernel with short policy for expiry tests."""
    k = TaskInitiationKernel(
        temp_state_dir,
        policy=short_policy,
        clock=_fixed_clock,
        busy_timeout_seconds=0.2,
    )
    k.initialize()
    return k


@pytest.fixture
def stuck_event() -> dict[str, Any]:
    """Return a minimal valid Stuck event dict.

    Tests can override fields via keyword arguments when calling
    kernel.ingest_stuck().
    """
    return {
        "schema_version": "task_initiation_stuck.v1",
        "event_id": str(uuid.uuid4()),
        "source": "tasker",
        "occurred_at_epoch": FIXED_NOW_BASE - 10,
        "task_description": "Test task from fixture",
        "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
    }


@pytest.fixture
def stuck_event_no_ref() -> dict[str, Any]:
    """Return a valid Stuck event with no task_ref (session fallback)."""
    return {
        "schema_version": "task_initiation_stuck.v1",
        "event_id": str(uuid.uuid4()),
        "source": "tasker",
        "occurred_at_epoch": FIXED_NOW_BASE - 10,
        "task_description": "Session fallback task",
        "task_ref": None,
    }


@pytest.fixture
def resolution_tasks(temp_state_dir: Path) -> ResolutionInput:
    """Create a ResolutionInput with a single task."""
    p = temp_state_dir / f"res_{uuid.uuid4().hex[:8]}.json"
    p.write_text(
        json.dumps(
            {
                "tasks": {
                    "Tasks/test.md": {"label": "Fixture Task", "revision": REV_FIXTURE}
                }
            },
            sort_keys=True,
        )
    )
    return load_resolution_input(p, policy=KernelPolicy())


@pytest.fixture
def stuck_with_resolution(
    kernel: TaskInitiationKernel,
    stuck_event: dict[str, Any],
    resolution_tasks: ResolutionInput,
) -> dict[str, Any]:
    """Ingest a Stuck event and return dict with event_id, card, kernel.

    Returns a dict with keys: kernel, event_id, card, result.
    """
    result = kernel.ingest_stuck(stuck_event, resolution=resolution_tasks)
    assert result.result["status"] == "card_published"
    return {
        "kernel": kernel,
        "event_id": result.result["event_id"],
        "card": result.result["card"],
        "result": result,
    }


def make_stuck(**overrides: Any) -> dict[str, Any]:
    """Create a Stuck event dict with default values, overridable."""
    base: dict[str, Any] = {
        "schema_version": "task_initiation_stuck.v1",
        "event_id": str(uuid.uuid4()),
        "source": "tasker",
        "occurred_at_epoch": FIXED_NOW_BASE - 10,
        "task_description": "Test task",
        "task_ref": {"source": "tasknotes", "ref": "Tasks/test.md"},
    }
    base.update(overrides)
    return base


def make_response(
    card: Mapping[str, Any], action: str = "start", **overrides: Any
) -> dict[str, Any]:
    """Create a Response event dict bound to a card."""
    detail = overrides.pop("detail", None)
    if detail is None and action in ("shrink", "blocked"):
        detail = "test detail"
    base: dict[str, Any] = {
        "schema_version": "task_initiation_response.v1",
        "response_id": str(uuid.uuid4()),
        "card_id": card["card_id"],
        "action": action,
        "detail": detail,
        "occurred_at_epoch": FIXED_NOW_BASE - 5,
    }
    base.update(overrides)
    return base


def make_resolution_input(
    state_dir: Path,
    tasks_dict: dict[str, dict[str, str]],
    *,
    policy: KernelPolicy | None = None,
) -> ResolutionInput:
    """Create a ResolutionInput from a task dict."""
    if policy is None:
        policy = KernelPolicy()
    p = state_dir / f"res_{uuid.uuid4().hex[:8]}.json"
    p.write_text(json.dumps({"tasks": tasks_dict}, sort_keys=True))
    return load_resolution_input(p, policy=policy)


def reopen_kernel(state_dir: Path, **kw: Any) -> TaskInitiationKernel:
    """Reopen a kernel on an existing state directory."""
    k = TaskInitiationKernel(
        state_dir,
        policy=kw.pop("policy", KernelPolicy()),
        clock=kw.pop("clock", _fixed_clock),
        busy_timeout_seconds=kw.pop("busy_timeout_seconds", 0.2),
        **kw,
    )
    return k
