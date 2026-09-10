#!/usr/bin/env python3
"""Run acceptance tests from M2_ACCEPTANCE_V2.json (or M2_ACCEPTANCE.json).

Two modes:
  --mode baseline   Each criterion has baseline_expectation.
                    expected_pass → exit 0 required.
                    expected_fail  → nonzero exit with correct exception required.
                    Timeout, collection error, wrong failure reason → failure.
  --mode release    Every criterion with release_expectation="pass"
                    MUST exit 0.  expected_fail entries are skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

DEFAULT_MANIFEST_PATHS = [
    REPO_ROOT / "docs" / "M2_ACCEPTANCE_V2.json",
    REPO_ROOT / "docs" / "M2_ACCEPTANCE.json",
]

PYTHONPATH = str(REPO_ROOT / "python")
TIMEOUT_SECONDS = 30  # per-node timeout for subprocess


def find_manifest() -> Path:
    for p in DEFAULT_MANIFEST_PATHS:
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"No manifest found at {DEFAULT_MANIFEST_PATHS}"
    )


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def run_pytest_collect() -> dict:
    """Run pytest --collect-only -q to discover available node IDs."""
    env = {**os.environ, "PYTHONPATH": PYTHONPATH}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"collected": [], "raw_stdout": "", "error": "pytest collect timed out"}

    collected: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("=") and "ERROR" not in line:
            parts = line.split()
            for part in parts:
                if "::" in part and part.count("::") == 1:
                    collected.add(part)
    return {"collected": sorted(collected), "raw_stdout": result.stdout}


def run_criterion(nodeid: str) -> dict:
    """Execute a single criterion's pytest node with 30s timeout."""
    env = {**os.environ, "PYTHONPATH": PYTHONPATH}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q", "--no-header", "--tb=short"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            timeout=TIMEOUT_SECONDS,
        )
        return {
            "nodeid": nodeid,
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "nodeid": nodeid,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after {TIMEOUT_SECONDS}s",
        }
    except Exception as exc:
        return {
            "nodeid": nodeid,
            "exit_code": -2,
            "stdout": "",
            "stderr": str(exc),
        }


def _parse_exception_from_tb(stderr: str, stdout: str) -> str | None:
    """Extract the exception type from pytest short traceback output."""
    combined = stderr + stdout
    # pytest short traceback format: E   ExceptionType: message
    m = re.search(r'^\s*E\s+(\w+(?:Error|Exception|Warning|RefusalError|CorruptionError|BusyError|StorageError))', combined, re.MULTILINE)
    if m:
        return m.group(1)
    # Fallback: any ExceptionName in error lines
    m2 = re.search(r'(\w+Error|\w+Exception)', combined)
    return m2.group(1) if m2 else None


def _expected_exception_from_description(desc: str) -> str | None:
    """Guess the expected exception from the criterion description."""
    exceptions = [
        "KernelCorruptionError", "KernelRefusalError", "KernelBusyError",
        "KernelStorageError", "TaskInitiationContractError",
        "ValueError", "TypeError", "KeyError", "RuntimeError",
        "ValidationError",
    ]
    for exc in exceptions:
        if exc.lower() in desc.lower():
            return exc
    return None


def _find_test_nodeids_for_criterion(
    criterion_id: str, nodeids: list[str], collected_ids: set[str]
) -> list[str]:
    """Find pytest test node IDs that match a criterion.

    Matches by criterion id token (e.g. M2-V01 → M2_V01 in test name).
    """
    cid_token = criterion_id.replace("-", "_")
    matches: list[str] = []
    for c in collected_ids:
        if cid_token in c:
            matches.append(c)
    if not matches:
        # Fallback: try matching individual nodeid substrings
        for c in collected_ids:
            for nid in nodeids:
                if nid in c:
                    matches.append(c)
                    break
            if matches:
                break
    return sorted(set(matches))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M2 acceptance criteria")
    parser.add_argument("--mode", choices=["baseline", "release"], default="release",
                        help="baseline: expect failures; release: expect all pass")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Path to acceptance manifest JSON")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write result JSON to file")
    args = parser.parse_args()

    manifest_path = args.manifest or find_manifest()
    print(f"Manifest: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        print(f"ERROR: Cannot parse manifest: {exc}", file=sys.stderr)
        return 2

    criteria = manifest.get("criteria", {})
    if not criteria:
        print("ERROR: No criteria in manifest", file=sys.stderr)
        return 2

    # Normalize to list of dicts
    if isinstance(criteria, dict):
        criteria_list = [
            {**v, "id": k} if "id" not in v else v
            for k, v in criteria.items()
        ]
    else:
        criteria_list = list(criteria)

    print(f"Criteria count: {len(criteria_list)}")

    # Collect available node IDs
    collection = run_pytest_collect()
    if "error" in collection:
        print(f"ERROR: pytest collection failed: {collection['error']}", file=sys.stderr)
        return 3
    collected_ids = set(collection["collected"])
    print(f"Collected node IDs: {len(collected_ids)}")

    # Production hashes
    production_hashes: dict[str, str] = {}
    for rel in [
        "python/ai_system/task_initiation_contracts.py",
        "python/ai_system/task_initiation_private.py",
        "python/ai_system/task_initiation_store.py",
        "python/ai_system/task_initiation_kernel.py",
        "python/ai_system/task_initiation_cli.py",
    ]:
        fp = REPO_ROOT / rel
        production_hashes[rel] = sha256_file(fp)

    results: list[dict] = []
    passed = 0
    failed = 0
    errors = 0
    skipped = 0

    for entry in criteria_list:
        cid = entry.get("id", "unknown")
        desc = entry.get("description", "")
        nodeids = entry.get("nodeids", [])
        baseline_expect = entry.get("baseline_expectation", "pass")
        release_expect = entry.get("release_expectation", "pass")

        print(f"\n--- {cid}: {desc} ---")
        print(f"  baseline_expectation={baseline_expect} release_expectation={release_expect}")

        # Find matching test node IDs
        test_nodeids = _find_test_nodeids_for_criterion(cid, nodeids, collected_ids)

        if not test_nodeids:
            print(f"  NO MATCHING TESTS for nodeids: {nodeids}")
            errors += 1
            results.append({
                "criterion": cid,
                "nodeids": nodeids,
                "test_nodeids": [],
                "exit_code": -3,
                "error": "no matching test collected",
                "expectation": baseline_expect if args.mode == "baseline" else release_expect,
            })
            continue

        print(f"  Matching tests: {test_nodeids}")

        # Run each matching test
        crit_passed = 0
        crit_failed = 0

        for nid in test_nodeids:
            r = run_criterion(nid)
            r["criterion"] = cid

            if args.mode == "release":
                # Release mode: skip expected_fail, require pass for expected_pass
                if release_expect == "fail":
                    r["disposition"] = "skipped_expected_fail"
                    skipped += 1
                    print(f"    SKIP (release/expected_fail): {nid}")
                else:
                    if r["exit_code"] == 0:
                        r["disposition"] = "pass"
                        crit_passed += 1
                        print(f"    PASS: {nid}")
                    elif r["exit_code"] == -1:
                        r["disposition"] = "timeout"
                        crit_failed += 1
                        print(f"    FAIL (TIMEOUT): {nid}")
                    elif r["exit_code"] == -2:
                        r["disposition"] = "error"
                        crit_failed += 1
                        print(f"    FAIL (ERROR): {nid}")
                    else:
                        r["disposition"] = "fail"
                        crit_failed += 1
                        print(f"    FAIL (exit {r['exit_code']}): {nid}")
            else:
                # Baseline mode: check expectation
                exp = baseline_expect

                if r["exit_code"] == -1:
                    # Timeout is always a failure
                    r["disposition"] = "timeout"
                    crit_failed += 1
                    print(f"    FAIL (TIMEOUT): {nid}")
                elif r["exit_code"] == -2:
                    r["disposition"] = "error"
                    crit_failed += 1
                    print(f"    FAIL (ERROR): {nid} - {r['stderr'][:200]}")
                elif exp == "pass":
                    if r["exit_code"] == 0:
                        r["disposition"] = "pass"
                        crit_passed += 1
                        print(f"    PASS: {nid}")
                    else:
                        r["disposition"] = "unexpected_fail"
                        r["expected"] = "pass"
                        crit_failed += 1
                        actual_exc = _parse_exception_from_tb(r["stderr"], r["stdout"])
                        print(f"    FAIL (expected pass, got exit {r['exit_code']}): {nid}  exception={actual_exc}")
                else:
                    # expected_fail: must be nonzero AND have the right exception
                    if r["exit_code"] == 0:
                        r["disposition"] = "unexpected_pass"
                        crit_failed += 1
                        print(f"    FAIL (expected_fail but got exit 0): {nid}")
                    else:
                        actual_exc = _parse_exception_from_tb(r["stderr"], r["stdout"])
                        expected_exc = _expected_exception_from_description(desc)
                        r["actual_exception"] = actual_exc
                        r["expected_exception"] = expected_exc

                        if actual_exc and expected_exc and actual_exc == expected_exc:
                            r["disposition"] = "expected_fail_correct"
                            crit_passed += 1
                            print(f"    PASS (expected_fail, correct exception {actual_exc}): {nid}")
                        elif actual_exc:
                            r["disposition"] = "expected_fail_wrong_exception"
                            crit_failed += 1
                            print(f"    FAIL (expected_fail, wrong exception: got {actual_exc}, expected {expected_exc}): {nid}")
                        else:
                            r["disposition"] = "expected_fail_no_exception"
                            crit_failed += 1
                            print(f"    FAIL (expected_fail, no exception parsed): {nid}")

            results.append(r)

        passed += crit_passed
        failed += crit_failed

    # Build output
    output: dict = {
        "schema_version": "m2_acceptance_result.v1",
        "mode": args.mode,
        "manifest": str(manifest_path),
        "manifest_hash": sha256_file(manifest_path),
        "production_hashes": production_hashes,
        "collection_count": len(collected_ids),
        "manifest_criteria_count": len(criteria_list),
        "total_ran": passed + failed,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "results": results,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = args.output or (ARTIFACTS_DIR / "m2-acceptance-result.json")
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(f"\nResults written to {out_path}")

    if args.mode == "release":
        exit_code = 0 if (failed == 0 and errors == 0) else 1
        print(f"RELEASE MODE: {'PASS' if exit_code == 0 else 'FAIL'} ({passed} passed, {failed} failed, {errors} errors, {skipped} skipped)")
        return exit_code
    else:
        exit_code = 0 if errors == 0 else 1
        print(f"BASELINE MODE: {passed} passed, {failed} failed, {errors} errors")
        return exit_code


if __name__ == "__main__":
    sys.exit(main())
