#!/usr/bin/env python3
"""Master release gate for Milestone 2 verifier.

--mode baseline: runs ALL mandatory components, generates
    artifacts/m2-verifier-baseline.json.  Verdict computed from results.
    No --pass/--verdict arguments accepted.

--mode release: runs all components and enforces verifier_status=ready
    AND milestone_status=ready.

Exit 0 only when:
  baseline: verifier_status=ready AND milestone_status=blocked
  release:  verifier_status=ready AND milestone_status=ready
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
PYTHONPATH = str(REPO_ROOT / "python")
M2_VERIFIER_DIR = Path(__file__).resolve().parent

TIMEOUT_SECONDS = 300  # 5 minutes per sub-step

PRODUCTION_FILES: list[str] = [
    "python/ai_system/task_initiation_contracts.py",
    "python/ai_system/task_initiation_private.py",
    "python/ai_system/task_initiation_store.py",
    "python/ai_system/task_initiation_kernel.py",
    "python/ai_system/task_initiation_cli.py",
]

REQUIRED_DEPS: list[str] = ["pytest", "hypothesis", "coverage", "mutmut"]


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return "MISSING"


def run_step(argv: list[str], step_name: str, env: dict | None = None) -> dict:
    """Run a subprocess and return structured result.

    Raw stdout/stderr are saved to artifacts/m2-verifier-logs/<step_name>.{stdout,stderr}.
    """
    t0 = time.time()
    full_env = {**os.environ}
    if env:
        full_env.update(env)
    logs_dir = ARTIFACTS_DIR / "m2-verifier-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, cwd=str(REPO_ROOT),
            env=full_env, timeout=TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        # Save raw logs
        (logs_dir / f"{step_name}.stdout").write_text(result.stdout)
        (logs_dir / f"{step_name}.stderr").write_text(result.stderr)
        return {
            "step": step_name,
            "exit_code": result.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - t0) * 1000)
        timeout_msg = f"TIMEOUT after {TIMEOUT_SECONDS}s"
        (logs_dir / f"{step_name}.stdout").write_text("")
        (logs_dir / f"{step_name}.stderr").write_text(timeout_msg)
        return {
            "step": step_name,
            "exit_code": -1,
            "elapsed_ms": elapsed_ms,
            "stdout": "",
            "stderr": timeout_msg,
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        err_msg = str(exc)
        (logs_dir / f"{step_name}.stdout").write_text("")
        (logs_dir / f"{step_name}.stderr").write_text(err_msg)
        return {
            "step": step_name,
            "exit_code": -2,
            "elapsed_ms": elapsed_ms,
            "stdout": "",
            "stderr": err_msg,
        }

def main() -> int:
    parser = argparse.ArgumentParser(description="M2 Verifier Release Gate")
    parser.add_argument("--mode", choices=["baseline", "release"], default="baseline",
                        help="baseline: record baseline; release: enforce gate")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    env = {"PYTHONPATH": PYTHONPATH}

    print(f"=== M2 Verifier Release Gate ({args.mode}) ===")

    # 1. Production hashes
    print("\n--- 1. Production Hashes ---")
    prod_hashes = {rel: sha256_file(REPO_ROOT / rel) for rel in PRODUCTION_FILES}
    for rel, h in prod_hashes.items():
        print(f"  {h[:16]}...  {rel}")

    # 2. Dependency probe
    print("\n--- 2. Dependency Probe ---")
    dep_result = run_step(
        [sys.executable, "-c", "import pytest, hypothesis, coverage, mutmut"],
        "dependency_probe", env=env,
    )
    deps_ok = dep_result["exit_code"] == 0
    print(f"  Dependencies: {'OK' if deps_ok else 'MISSING'}")
    if not deps_ok:
        print(f"  stderr: {dep_result['stderr'][:500]}")

    # 3. Collection
    print("\n--- 3. Test Collection ---")
    collection_result = run_step(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header",
         "tests/m2_acceptance_v2/", "tests/m2_verifier_quality/", "tests/m2_stateful_v2/"],
        "collection", env=env,
    )
    collection_ok = collection_result["exit_code"] == 0
    print(f"  Collection: {'OK' if collection_ok else 'FAILED'}")

    # 4. Manifest validation
    print("\n--- 4. Manifest Validation ---")
    manifest_validation = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "validate_manifest.py")],
        "manifest_validation", env=env,
    )
    manifest_ok = manifest_validation["exit_code"] == 0
    print(f"  Manifest Validation: {'PASS' if manifest_ok else 'FAIL'}")

    # 5. Lock verification
    print("\n--- 5. Lock Verification ---")
    lock_result = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "verify_lock.py")],
        "lock_verification", env=env,
    )
    lock_ok = lock_result["exit_code"] == 0
    print(f"  Lock Verification: {'PASS' if lock_ok else 'FAIL'}")

    # 6. Quality gate
    print("\n--- 6. Quality Gate ---")
    quality_result = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "test_quality.py")],
        "quality_gate", env=env,
    )
    quality_ok = quality_result["exit_code"] == 0
    print(f"  Quality Gate: {'PASS' if quality_ok else 'FAIL'}")

    # 7. Quality canaries
    print("\n--- 7. Quality Canaries ---")
    canary_result = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "run_quality_canaries.py")],
        "quality_canaries", env=env,
    )
    canaries_ok = canary_result["exit_code"] == 0
    print(f"  Canaries: {'PASS' if canaries_ok else 'FAIL'}")

    # 8. Acceptance run
    print("\n--- 8. Acceptance Run ---")
    acceptance_result = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "run_acceptance.py"),
         "--mode", args.mode],
        "acceptance", env=env,
    )
    acceptance_ok = acceptance_result["exit_code"] == 0
    print(f"  Acceptance: {'PASS' if acceptance_ok else 'FAIL'}")

    # 9. Semantic mutants
    print("\n--- 9. Semantic Mutants ---")
    mutant_result = run_step(
        [sys.executable, str(M2_VERIFIER_DIR / "run_semantic_mutants.py"),
         "--phase", "verifier-probe"],
        "semantic_mutants", env=env,
    )
    mutants_ok = mutant_result["exit_code"] == 0
    print(f"  Semantic Mutants: {'PASS' if mutants_ok else 'FAIL'}")

    # 10. Stateful tests
    print("\n--- 10. Stateful Tests ---")
    stateful_result = run_step(
        [sys.executable, "-m", "pytest", "tests/m2_stateful_v2/", "-q", "--no-header", "--tb=short"],
        "stateful", env=env,
    )
    stateful_ok = stateful_result["exit_code"] == 0
    print(f"  Stateful: {'PASS' if stateful_ok else 'FAIL'}")

    # 11. Coverage probe (informational)
    print("\n--- 11. Coverage ---")
    coverage_result = run_step(
        [sys.executable, "-m", "coverage", "run", "-m", "pytest",
         "tests/m2_acceptance_v2/", "-q", "--no-header", "--tb=line"],
        "coverage_run", env=env,
    )
    coverage_ok = coverage_result["exit_code"] == 0
    print(f"  Coverage run: {'OK' if coverage_ok else 'FAIL'}")

    # Determine verifier readiness
    verifier_ready = all([
        deps_ok, collection_ok, manifest_ok, lock_ok, quality_ok,
        canaries_ok, acceptance_ok, mutants_ok, stateful_ok,
    ])
    verifier_status = "ready" if verifier_ready else "blocked"

    # Milestone status: always blocked in baseline
    if args.mode == "baseline":
        milestone_status = "blocked"
        milestone_reason = "baseline mode — no release candidate"
    else:
        milestone_status = "ready" if verifier_ready else "blocked"
        milestone_reason = "all gates passed" if verifier_ready else "verifier not ready"

    # Build output
    manifest_path = None
    for mp in [REPO_ROOT / "docs" / "M2_ACCEPTANCE_V2.json",
               REPO_ROOT / "docs" / "M2_ACCEPTANCE.json"]:
        if mp.is_file():
            manifest_path = mp
            break
    manifest_hash = sha256_file(manifest_path) if manifest_path else ""

    output: dict = {
        "schema_version": "m2_verifier_baseline.v1",
        "mode": args.mode,
        "timestamp_epoch": int(time.time()),
        "production_hashes": prod_hashes,
        "verifier_status": verifier_status,
        "milestone_status": milestone_status,
        "milestone_reason": milestone_reason,
        "steps": {
            "dependency_probe": dep_result,
            "collection": collection_result,
            "manifest_validation": manifest_validation,
            "lock_verification": lock_result,
            "manifest": {
                "path": str(manifest_path) if manifest_path else None,
                "hash": manifest_hash,
                "ok": manifest_ok,
            },
            "quality_gate": quality_result,
            "quality_canaries": canary_result,
            "acceptance": acceptance_result,
            "semantic_mutants": mutant_result,
            "stateful": stateful_result,
            "coverage": coverage_result,
        },
        "gates": {
            "deps_ok": deps_ok,
            "collection_ok": collection_ok,
            "manifest_ok": manifest_ok,
            "lock_ok": lock_ok,
            "quality_ok": quality_ok,
            "canaries_ok": canaries_ok,
            "acceptance_ok": acceptance_ok,
            "mutants_ok": mutants_ok,
            "stateful_ok": stateful_ok,
            "coverage_ok": coverage_ok,
        },
    }

    out_path = args.output or (ARTIFACTS_DIR / "m2-verifier-baseline.json")
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(f"\nOutput: {out_path}")

    if args.mode == "baseline":
        exit_code = 0 if (verifier_status == "ready" and milestone_status == "blocked") else 1
    else:
        exit_code = 0 if (verifier_status == "ready" and milestone_status == "ready") else 1

    print(f"\n=== GATE: verifier={verifier_status} milestone={milestone_status} ===")
    print(f"Exit: {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
