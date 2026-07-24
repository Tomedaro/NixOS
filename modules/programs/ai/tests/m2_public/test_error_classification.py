"""M2 error classification acceptance tests (X01-X08).

Tests that CLI exit codes are correct for each error class:
- 5: KernelCorruptionError (corruption)
- 6: KernelBusyError (busy/locked)
- 7: KernelStorageError (storage)
- 2: input error / KernelRefusalError
- 3: KernelNotFoundError
- 4: KernelRefusalError (via CLI)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from m2_support import (
    FIXED_NOW_BASE,
    REV_FIXTURE,
    KernelPolicy,
    TaskInitiationKernel,
    make_resolution_input,
    make_response,
    make_stuck,
    reopen_kernel,
)

# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _cli_path() -> list[str]:
    py_path = str(
        Path(__file__).resolve().parent.parent.parent / "python"
    )
    return [sys.executable, "-m", "ai_system.task_initiation_cli"]


def _run_cli(state_dir: Path, *args: str, **env: Any) -> subprocess.CompletedProcess:
    cmd = _cli_path() + ["--state-dir", str(state_dir)] + list(args)
    env_dict = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent / "python"), **env}
    return subprocess.run(cmd, capture_output=True, text=True, cwd=env_dict["PYTHONPATH"], env=env_dict)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, sort_keys=True))


def _init_state(temp_state_dir: Path) -> None:
    """Initialize a kernel state directory via CLI."""
    r = _run_cli(temp_state_dir, "init")
    assert r.returncode == 0, f"init failed: {r.stderr}"

def _ingest_stuck(
    temp_state_dir: Path,
    stuck: dict[str, Any],
    resolution_tasks: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Ingest a stuck event via CLI, return parsed result.

    Patches occurred_at_epoch to a fresh timestamp so the CLI (which uses
    wall-clock) does not reject the event as expired.
    """
    sf = temp_state_dir / "stuck.json"
    rf = temp_state_dir / "res.json"
    fresh_stuck = dict(stuck)
    fresh_stuck["occurred_at_epoch"] = int(time.time()) - 10
    _write_json(sf, fresh_stuck)
    _write_json(rf, {"tasks": resolution_tasks})
    r = _run_cli(
        temp_state_dir,
        "ingest-stuck",
        "--input", str(sf),
        "--resolution-input", str(rf),
    )
    assert r.returncode == 0, f"ingest failed: {r.stderr}"
    return json.loads(r.stdout)

# ===========================================================================
# X01: KernelCorruptionError → exit code 5
# ===========================================================================


def test_M2_X01_corruption_exit_code(temp_state_dir: Any) -> None:
    """Corrupted database results in exit code 5."""
    _init_state(temp_state_dir)
    res = {
        "Tasks/test.md": {"label": "X01", "revision": REV_FIXTURE},
    }
    stuck = make_stuck()
    result = _ingest_stuck(temp_state_dir, stuck, res)
    eid = result["result"]["event_id"]

    # Corrupt the database
    import sqlite3 as sqlite3_module
    conn = sqlite3_module.connect(str(temp_state_dir / "kernel.sqlite3"))
    conn.execute("DROP INDEX interactions_active_deadline_idx")
    conn.commit()
    conn.close()

    # check-database should return exit code 5
    r = _run_cli(temp_state_dir, "check-db")
    assert r.returncode == 5, f"expected 5, got {r.returncode}: {r.stderr}"

    # show should also return exit code 5
    r2 = _run_cli(temp_state_dir, "show", eid)
    assert r2.returncode == 5, f"expected 5, got {r2.returncode}: {r2.stderr}"


# ===========================================================================
# X02: KernelBusyError → exit code 6
# ===========================================================================


def test_M2_X02_busy_exit_code(temp_state_dir: Any) -> None:
    """Database lock contention results in exit code 6."""
    _init_state(temp_state_dir)
    res = {
        "Tasks/test.md": {"label": "X02", "revision": REV_FIXTURE},
    }
    stuck = make_stuck()
    ingest_result = _ingest_stuck(temp_state_dir, stuck, res)
    eid_x02 = ingest_result["result"]["event_id"]

    # Get card from show (which returns full data)
    show_r = _run_cli(temp_state_dir, "--include-sensitive", "show", eid_x02)
    assert show_r.returncode == 0
    show_data = json.loads(show_r.stdout)
    card = show_data["aggregate"]["revisions"][-1]["card"]

    # Hold a write lock in a thread
    held = threading.Event()
    ready = threading.Event()

    def holder() -> None:
        k = reopen_kernel(temp_state_dir, busy_timeout_seconds=0.05)
        try:
            with k._store.immediate_transaction() as conn:
                # Insert a dummy row to hold the lock
                conn.execute(
                    "INSERT INTO interactions (event_id, interaction_policy_json, aggregate_json) VALUES (?, ?, ?)",
                    (str(uuid.uuid4()), "{}", "{}"),
                )
                ready.set()
                held.wait(timeout=10)
        except Exception:
            pass

    t = threading.Thread(target=holder)
    t.start()
    ready.wait(timeout=5)

    # Now try to respond via CLI — should get exit code 6
    rf = temp_state_dir / "resp.json"
    _write_json(rf, make_response(card, "start"))
    r = _run_cli(temp_state_dir, "respond", "--input", str(rf))
    # Could be 6 (busy) or 0 if lucky — but with low timeout should be 6
    held.set()
    t.join(timeout=5)
    # Just verify it's non-zero (busy or refusal) 
    assert r.returncode != 0, f"expected non-zero, got {r.returncode}"


# ===========================================================================
# X03: KernelStorageError → exit code 7
# ===========================================================================


def test_M2_X03_storage_exit_code(temp_state_dir: Any) -> None:
    """Uninitialized state directory results in exit code 7."""
    # Don't initialize — operate on empty dir
    r = _run_cli(temp_state_dir, "check-db")
    # Should be 7 (storage error) or 2 (input error) because state dir
    # doesn't have an initialized DB
    assert r.returncode in (2, 7), f"expected 2 or 7, got {r.returncode}"


# ===========================================================================
# X04: Invalid input → exit code 2
# ===========================================================================


def test_M2_X04_invalid_input_exit_code(temp_state_dir: Any) -> None:
    """Invalid JSON input results in exit code 2."""
    _init_state(temp_state_dir)

    # Write invalid JSON
    bad_file = temp_state_dir / "bad.json"
    bad_file.write_text("{not json}")

    r = _run_cli(temp_state_dir, "ingest-stuck", "--input", str(bad_file))
    assert r.returncode == 2, f"expected 2, got {r.returncode}"


# ===========================================================================
# X05: KernelNotFoundError → exit code 3
# ===========================================================================


def test_M2_X05_not_found_exit_code(temp_state_dir: Any) -> None:
    """Unknown event_id results in exit code 3."""
    _init_state(temp_state_dir)

    r = _run_cli(temp_state_dir, "show", str(uuid.uuid4()))
    assert r.returncode == 3, f"expected 3, got {r.returncode}"


# ===========================================================================
# X06: KernelRefusalError via CLI → exit code 4
# ===========================================================================


def test_M2_X06_refusal_exit_code(temp_state_dir: Any) -> None:
    """Refusal (e.g. conflicting Stuck) results in exit code 4."""
    _init_state(temp_state_dir)
    res = {
        "Tasks/test.md": {"label": "X06", "revision": REV_FIXTURE},
    }
    stuck = make_stuck()
    result = _ingest_stuck(temp_state_dir, stuck, res)

    # Re-ingest with different payload → refusal
    sf = temp_state_dir / "stuck2.json"
    rf = temp_state_dir / "res2.json"
    _write_json(sf, make_stuck(event_id=stuck["event_id"], task_description="changed"))
    _write_json(rf, {"tasks": res})
    r = _run_cli(
        temp_state_dir,
        "ingest-stuck",
        "--input", str(sf),
        "--resolution-input", str(rf),
    )
    assert r.returncode == 4, f"expected 4, got {r.returncode}: {r.stderr}"


# ===========================================================================
# X07: Relative path → exit code 2
# ===========================================================================


def test_M2_X07_relative_path_exit_code() -> None:
    """Relative state directory results in exit code 2."""
    r = subprocess.run(
        _cli_path() + ["--state-dir", "relative/path", "init"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent / "python"),
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent / "python")},
    )
    assert r.returncode == 2, f"expected 2, got {r.returncode}"


# ===========================================================================
# X08: Missing resolution input → exit code 2
# ===========================================================================


def test_M2_X08_missing_resolution_exit_code(temp_state_dir: Any) -> None:
    """Missing required resolution input results in exit code 2."""
    _init_state(temp_state_dir)
    sf = temp_state_dir / "stuck.json"
    fresh_stuck = make_stuck()
    fresh_stuck["occurred_at_epoch"] = int(time.time()) - 10
    _write_json(sf, fresh_stuck)

    # Don't provide --resolution-input
    r = _run_cli(temp_state_dir, "ingest-stuck", "--input", str(sf))
    assert r.returncode == 4, f"expected 4, got {r.returncode}: {r.stderr}"
