#!/usr/bin/env python3
"""Semantic mutant testing for the verifier.

Targets tests/m2_acceptance_v2/ (not m2_public/).
Two verifier-probe mutants:
  S01: Break replay identity (replay always returns False)
  S02: Remove first-response-wins (owner check bypassed)
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHONPATH = str(REPO_ROOT / "python")
M2_VERIFIER_DIR = Path(__file__).resolve().parent

TIMEOUT_SECONDS = 120

PRODUCTION_DIR = REPO_ROOT / "python" / "ai_system"

# Node IDs that should detect each mutant (from tests/m2_acceptance_v2/)
S01_ACCEPTANCE_NODES: list[str] = [
    "tests/m2_acceptance_v2/test_lifecycle.py::test_M2_V11_idempotent_stuck",
    "tests/m2_acceptance_v2/test_lifecycle.py::test_M2_V11_idempotent_response",
    "tests/m2_acceptance_v2/test_cross_surface.py::test_M2_C02_corrupt_aggregate_rejected_by_show",
]

S02_ACCEPTANCE_NODES: list[str] = [
    "tests/m2_acceptance_v2/test_lifecycle.py::test_M2_V06_dismiss_response",
    "tests/m2_acceptance_v2/test_policy.py::test_M2_P_owner_scoping",
]


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def create_temp_copy() -> Path:
    """Create a temp directory with a full copy of the production Python code."""
    td = tempfile.mkdtemp(prefix="m2sm_")
    tdir = Path(td)
    ai_system_dest = tdir / "ai_system"
    shutil.copytree(str(PRODUCTION_DIR), str(ai_system_dest), symlinks=False)
    return tdir


def run_pytest(nodes: list[str], pythonpath: str, worktree: Path) -> dict:
    """Run pytest against specific nodes using worktree copy."""
    env = {**__import__("os").environ, "PYTHONPATH": f"{worktree}{':' if worktree else ''}{pythonpath}"}
    all_passed = True
    results: list[dict] = []

    for nid in nodes:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", nid, "-q", "--no-header", "--tb=line"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
                timeout=TIMEOUT_SECONDS,
            )
            passed = result.returncode == 0
            results.append({"nodeid": nid, "exit_code": result.returncode, "passed": passed})
            if not passed:
                all_passed = False
        except subprocess.TimeoutExpired:
            results.append({"nodeid": nid, "exit_code": -1, "passed": False})
            all_passed = False

    return {"all_passed": all_passed, "results": results}


def apply_s01_patch(worktree: Path) -> None:
    """S01: Break replay identity in task_initiation_contracts.py.

    Modify _reserve_message to always return (new_state, False).
    """
    target = worktree / "ai_system" / "task_initiation_contracts.py"
    content = target.read_text()

    applied = False
    for old, new in [
        ("return result, True", "return result, False  # S01: broken replay identity"),
        ("return reserved, True", "return reserved, False  # S01: broken replay identity"),
    ]:
        if old in content:
            content = content.replace(old, new)
            applied = True
            break

    if applied:
        target.write_text(content)
        print(f"  S01 patch applied to {target.name}")
    else:
        print(f"  S01 WARNING: replay pattern not found in {target.name}")


def apply_s02_patch(worktree: Path) -> None:
    """S02: Remove first-response-wins in task_initiation_kernel.py.

    Remove the owner check that prevents a second responder.
    """
    target = worktree / "ai_system" / "task_initiation_kernel.py"
    content = target.read_text()

    # Look for owner checks
    found = False
    for owner_pattern in [
        'if state.get("owner") is not None',
        "if state.get('owner') is not None",
    ]:
        if owner_pattern in content:
            lines = content.splitlines()
            new_lines = []
            in_owner_check = False
            base_indent = ""

            for line in lines:
                if owner_pattern.replace('"', "'") in line.replace('"', "'"):
                    in_owner_check = True
                    base_indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f"{base_indent}# S02: first-response-wins removed")
                    new_lines.append(f"{base_indent}if False:  # was: {line.strip()}")
                    found = True
                    continue
                if in_owner_check and ("raise KernelRefusalError" in line or "raise TaskInitiationContractError" in line):
                    new_lines.append(f"{base_indent}    pass  # S02: refusal removed")
                    continue
                new_lines.append(line)

            content = "\n".join(new_lines)
            target.write_text(content)
            print(f"  S02 patch applied to {target.name}")
            break

    if not found:
        # Fallback: search for first-response pattern
        if "first_response" in content.lower() or "owner" in content.lower():
            print("  S02: owner check pattern found but couldn't patch precisely")
        else:
            print("  S02 WARNING: first-response-wins pattern not found")


def run_phase_verifier_probe() -> int:
    """Test S01 and S02 mutants against their acceptance nodes."""
    print("=== Semantic Mutants: Verifier Probe ===")

    all_detected = True

    # S01: Break replay identity
    print("\n--- S01: Break Replay Identity ---")
    try:
        wt = create_temp_copy()
        apply_s01_patch(wt)
        result = run_pytest(S01_ACCEPTANCE_NODES, str(wt), wt)
        detected = not result["all_passed"]
        print(f"  S01 detected: {detected}")
        for r in result["results"]:
            status = "PASS" if r["passed"] else "FAIL (correct detection)"
            print(f"    {status}: {r['nodeid']}")
        if not detected:
            print("  S01 FAILED: mutation not detected by any test")
            all_detected = False
        shutil.rmtree(str(wt), ignore_errors=True)
    except Exception as exc:
        print(f"  S01 ERROR: {exc}")
        all_detected = False

    # S02: Remove first-response-wins
    print("\n--- S02: Remove First-Response-Wins ---")
    try:
        wt = create_temp_copy()
        apply_s02_patch(wt)
        result = run_pytest(S02_ACCEPTANCE_NODES, str(wt), wt)
        detected = not result["all_passed"]
        for r in result["results"]:
            status = "PASS" if r["passed"] else "FAIL (correct detection)"
            print(f"    {status}: {r['nodeid']}")
        if not detected:
            print("  S02 FAILED: mutation not detected by any test")
            all_detected = False
        shutil.rmtree(str(wt), ignore_errors=True)
    except Exception as exc:
        print(f"  S02 ERROR: {exc}")
        all_detected = False

    print(f"\n=== VERIFIER PROBE: {'PASS' if all_detected else 'FAIL'} ===")
    return 0 if all_detected else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic mutant testing")
    parser.add_argument("--phase", choices=["verifier-probe"], default="verifier-probe")
    args = parser.parse_args()

    if args.phase == "verifier-probe":
        return run_phase_verifier_probe()
    else:
        print(f"Unknown phase: {args.phase}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
