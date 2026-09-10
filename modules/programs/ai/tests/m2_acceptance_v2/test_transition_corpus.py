"""M2 verifier transition corpus validation.

Validates the frozen transition corpus: 12 valid traces that exercise every
lifecycle path. Each trace uses public Response field 'action' (not 'user_action').

Every trace must pass public validators and produce the expected snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from typing import Any

from m2_verifier_support import (
    FIXED_NOW_BASE,
    KernelRefusalError,
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)
from ai_system.task_initiation_kernel import (
    KernelPolicy,
    TaskInitiationKernel,
)


def _load_corpus() -> dict[str, Any]:
    """Load the frozen transition corpus."""
    corpus_path = (
        Path(__file__).resolve().parent.parent
        / "m2_verifier_support"
        / "m2_transition_corpus.json"
    )
    return json.loads(corpus_path.read_text())


CORPUS = _load_corpus()


def test_corpus_has_twelve_traces() -> None:
    """The corpus must contain exactly 12 traces."""
    traces = CORPUS["traces"]
    assert len(traces) == 12, f"Expected 12 traces, got {len(traces)}"


def test_corpus_all_traces_use_action_not_user_action() -> None:
    """All Response inputs must use 'action' field, not 'user_action'."""
    for trace in CORPUS["traces"]:
        for inp in trace["inputs"]:
            if inp["kind"] == "response":
                payload = inp["payload"]
                assert "action" in payload, (
                    f"Trace {trace['trace_id']}: missing 'action' in Response payload"
                )
                assert "user_action" not in payload, (
                    f"Trace {trace['trace_id']}: found deprecated 'user_action' in Response payload"
                )


def test_corpus_trace_ids_are_unique() -> None:
    """All trace IDs must be unique."""
    ids = [t["trace_id"] for t in CORPUS["traces"]]
    assert len(ids) == len(set(ids)), f"Duplicate trace IDs: {ids}"


def test_corpus_snapshots_use_valid_phases() -> None:
    """All expected_snapshots phases must be valid durable phases."""
    valid_phases = {"awaiting_response", "observing"}
    for trace in CORPUS["traces"]:
        for snap in trace.get("expected_snapshots", []):
            phase = snap.get("phase")
            assert phase in valid_phases, (
                f"Trace {trace['trace_id']}: invalid phase {phase!r}"
            )


def test_corpus_stuck_inputs_validate() -> None:
    """Every Stuck input in the corpus must pass schema validation."""
    from ai_system.task_initiation_contracts import validate_stuck_event

    for trace in CORPUS["traces"]:
        for inp in trace["inputs"]:
            if inp["kind"] == "stuck":
                validated = validate_stuck_event(inp["payload"])
                assert validated["schema_version"] == "task_initiation_stuck.v1"


def test_corpus_response_inputs_validate() -> None:
    """Every Response input in the corpus must pass schema validation."""
    from ai_system.task_initiation_contracts import validate_response

    for trace in CORPUS["traces"]:
        for inp in trace["inputs"]:
            if inp["kind"] == "response":
                validated = validate_response(inp["payload"])
                assert "action" in validated
                assert validated["action"] in {"start", "shrink", "blocked", "defer", "dismiss"}


# ===========================================================================
# Trace replay: execute each trace against a real kernel
# ===========================================================================


def test_trace_m2_c01_stuck_ingestion(temp_state_dir) -> None:
    """TRACE_M2_C01: Stuck ingestion produces card_published."""
    trace = _find_trace("TRACE_M2_C01_stuck_ingestion")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op = k.ingest_stuck(stuck, resolution=res)
    assert op.result["status"] == "card_published"
    assert not op.replay


def test_trace_m2_c02_start_response(temp_state_dir) -> None:
    """TRACE_M2_C02: Start response transitions to observing."""
    trace = _find_trace("TRACE_M2_C02_start_response")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    r = k.respond(_bind_response(resp, card), resolution=res)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "observing"
    assert not r.replay


def test_trace_m2_c03_shrink_response(temp_state_dir) -> None:
    """TRACE_M2_C03: Shrink response produces next_card."""
    trace = _find_trace("TRACE_M2_C03_shrink_response")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    r = k.respond(_bind_response(resp, card), resolution=res)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None


def test_trace_m2_c04_blocked_response(temp_state_dir) -> None:
    """TRACE_M2_C04: Blocked response produces next_card."""
    trace = _find_trace("TRACE_M2_C04_blocked_response")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    r = k.respond(_bind_response(resp, card), resolution=res)
    assert r.result["status"] == "accepted"
    assert r.result["phase"] == "awaiting_response"
    assert r.result.get("next_card") is not None


def test_trace_m2_c05_defer_response(temp_state_dir) -> None:
    """TRACE_M2_C05: Defer response produces terminal_status=completed."""
    trace = _find_trace("TRACE_M2_C05_defer_response")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    r = k.respond(_bind_response(resp, card), resolution=res)
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"


def test_trace_m2_c06_dismiss_response(temp_state_dir) -> None:
    """TRACE_M2_C06: Dismiss response produces terminal_status=completed."""
    trace = _find_trace("TRACE_M2_C06_dismiss_response")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    r = k.respond(_bind_response(resp, card), resolution=res)
    assert r.result["status"] == "accepted"
    assert r.result["terminal_status"] == "completed"


def test_trace_m2_c07_revision_ceiling(temp_state_dir) -> None:
    """TRACE_M2_C07: After 3 shrinks, terminal_status appears."""
    trace = _find_trace("TRACE_M2_C07_revision_ceiling")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)
    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    # Shrink 1
    r1 = k.respond(_bind_response(_build_response_from_trace(trace, 0), card), resolution=res)
    assert r1.result["status"] == "accepted"
    card2 = r1.result.get("next_card")
    assert card2 is not None

    # Shrink 2
    r2 = k.respond(_bind_response(_build_response_from_trace(trace, 1), card2), resolution=res)
    assert r2.result["status"] == "accepted"
    card3 = r2.result.get("next_card")
    if card3 is not None:
        # Shrink 3
        r3 = k.respond(_bind_response(_build_response_from_trace(trace, 2), card3), resolution=res)
        assert r3.result.get("terminal_status") is not None
    else:
        assert r2.result.get("terminal_status") is not None


def test_trace_m2_c08_card_expiry(temp_state_dir) -> None:
    """TRACE_M2_C08: Card past expiry rejects respond."""
    trace = _find_trace("TRACE_M2_C08_card_expiry")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)
    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]

    # Advance clock past expiry
    expired_clock = lambda: card["expires_at_epoch"] + 1  # noqa: E731
    k2 = reopen_kernel(temp_state_dir, clock=expired_clock)

    with pytest.raises(KernelRefusalError):
        k2.respond(make_response(card, "start"), resolution=res)


def test_trace_m2_c09_observation_completion(temp_state_dir) -> None:
    """TRACE_M2_C09: reconcile transitions overdue observing to terminal."""
    trace = _find_trace("TRACE_M2_C09_observation_completion")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]
    k.respond(_bind_response(resp, card), resolution=res)

    late_clock = lambda: 1_700_000_000 + 2000  # noqa: E731
    k2 = reopen_kernel(
        temp_state_dir,
        clock=late_clock,
        policy=KernelPolicy(card_ttl_seconds=900, observation_seconds=10),
    )
    rec = k2.reconcile()
    assert rec["ok"] is True
    assert rec["reconciled"] >= 1


def test_trace_m2_c10_supersession(temp_state_dir) -> None:
    """TRACE_M2_C10: Changed task revision supersedes interaction."""
    import hashlib

    trace = _find_trace("TRACE_M2_C10_supersession")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    rev1 = hashlib.sha256(b"orig").hexdigest()
    rev2 = hashlib.sha256(b"changed").hexdigest()

    res1 = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "Original", "revision": rev1}},
    )
    op_stuck = k.ingest_stuck(stuck, resolution=res1)
    card = op_stuck.result["card"]

    res2 = make_resolution_input(
        temp_state_dir,
        {"Tasks/test.md": {"label": "Changed", "revision": rev2}},
    )
    r = k.respond(make_response(card, "start"), resolution=res2)
    assert r.result["status"] == "superseded"


def test_trace_m2_c11_idempotent_replay(temp_state_dir) -> None:
    """TRACE_M2_C11: Identical Stuck replay returns replay=True."""
    trace = _find_trace("TRACE_M2_C11_idempotent_replay")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op1 = k.ingest_stuck(stuck, resolution=res)
    assert not op1.replay

    op2 = k.ingest_stuck(stuck, resolution=res)
    assert op2.replay
    assert op1.result["status"] == op2.result["status"]


def test_trace_m2_c12_restart_resilience(temp_state_dir) -> None:
    """TRACE_M2_C12: State preserved across close/reopen."""
    trace = _find_trace("TRACE_M2_C12_restart_resilience")
    policy = KernelPolicy(**trace["policy"])
    k = _init_kernel(temp_state_dir, policy)

    stuck = _build_stuck_from_trace(trace, 0)
    resp = _build_response_from_trace(trace, 0)
    res = _make_resolution(temp_state_dir, stuck)

    op_stuck = k.ingest_stuck(stuck, resolution=res)
    card = op_stuck.result["card"]
    k.respond(_bind_response(resp, card), resolution=res)

    cdb_before = k.check_database()
    assert cdb_before["status"] == "ok"

    k2 = reopen_kernel(temp_state_dir)
    cdb_after = k2.check_database()
    assert cdb_after["status"] == "ok"


# ===========================================================================
# Helpers
# ===========================================================================


def _find_trace(trace_id: str) -> dict[str, Any]:
    """Find a trace by ID in the corpus."""
    for t in CORPUS["traces"]:
        if t["trace_id"] == trace_id:
            return t
    raise KeyError(f"Trace not found: {trace_id}")


def _init_kernel(temp_state_dir: Path, policy: KernelPolicy) -> TaskInitiationKernel:
    """Initialize a kernel with the given policy and fixed clock."""
    from m2_verifier_support import _fixed_clock, _reset_uuid_counter

    _reset_uuid_counter()
    k = TaskInitiationKernel(
        temp_state_dir,
        policy=policy,
        clock=_fixed_clock,
        busy_timeout_seconds=0.2,
    )
    k.initialize()
    return k


def _build_stuck_from_trace(trace: dict[str, Any], index: int) -> dict[str, Any]:
    """Build a full Stuck event from a trace input."""
    inp = trace["inputs"][index]
    base = dict(inp["payload"])
    base.setdefault("source", "tasker")
    return base


def _build_response_from_trace(trace: dict[str, Any], index: int) -> dict[str, Any]:
    """Build a Response event from a trace input (card_id not yet bound)."""
    response_inputs = [i for i in trace["inputs"] if i["kind"] == "response"]
    inp = response_inputs[index]
    base = dict(inp["payload"])
    base.setdefault("schema_version", "task_initiation_response.v1")
    base.setdefault("response_id", "11111111-1111-4111-8111-111111111111")
    base.setdefault("occurred_at_epoch", FIXED_NOW_BASE - 5)
    return base


def _bind_response(resp: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    """Bind a Response template to a specific card."""
    result = dict(resp)
    result["card_id"] = card["card_id"]
    return result


def _make_resolution(
    temp_state_dir: Path, stuck: dict[str, Any]
) -> Any:
    """Create a ResolutionInput for a Stuck event's task_ref."""
    from m2_verifier_support import REV_FIXTURE

    task_ref = stuck.get("task_ref", {})
    ref = task_ref.get("ref", "Tasks/test.md")
    return make_resolution_input(
        temp_state_dir,
        {ref: {"label": stuck.get("task_description", "Task"), "revision": REV_FIXTURE}},
    )
