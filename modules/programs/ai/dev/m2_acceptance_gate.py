#!/usr/bin/env python3
"""M2 public acceptance gate.

Parses docs/M2_ACCEPTANCE.json, collects pytest nodeids, verifies every
nodeid exists, runs each criterion independently, and records exit codes
and output hashes.

Usage:
  python dev/m2_acceptance_gate.py [--verbose]
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_manifest() -> dict[str, Any]:
    manifest_path = _repo_root() / "docs" / "M2_ACCEPTANCE.json"
    with open(manifest_path) as f:
        return json.load(f)


def _collect_nodeids(pytest_args: list[str]) -> set[str]:
    """Run pytest --collect-only -q and extract nodeids from output."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"] + pytest_args,
        capture_output=True,
        text=True,
        cwd=_repo_root(),
        env={**os.environ, "PYTHONPATH": str(_repo_root() / "python")},
    )
    nodeids: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("no tests") and not line.startswith("="):
            # Extract the nodeid part (before any space)
            parts = line.split()
            for part in parts:
                if "::" in part and part.endswith("]"):
                    part = part[:-1]
                if "::" in part:
                    # Strip leading path if present
                    if part.startswith("tests/"):
                        nodeids.add(part)
                    elif "/" in part:
                        # Could be a summary line
                        pass
    # Also try the newer pytest format
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("<") and "::" in line:
            # <Function test_foo> or <Module ...>
            pass
    return nodeids


def _run_test(nodeid: str, verbose: bool = False) -> dict[str, Any]:
    """Run a single test nodeid and return exit code + output hash."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", nodeid],
        capture_output=True,
        text=True,
        cwd=_repo_root(),
        env={**os.environ, "PYTHONPATH": str(_repo_root() / "python")},
    )
    output_hash = hashlib.sha256(result.stdout.encode() + result.stderr.encode()).hexdigest()
    return {
        "exit_code": result.returncode,
        "output_sha256": output_hash,
        "passed": result.returncode == 0,
    }


def main() -> int:
    verbose = "--verbose" in sys.argv

    manifest = _load_manifest()

    if manifest.get("schema_version") != "m2_acceptance.v1":
        print(f"ERROR: unsupported manifest schema version: {manifest.get('schema_version')}", file=sys.stderr)
        return 1

    criteria = manifest.get("criteria", {})
    if not criteria:
        print("ERROR: no criteria in manifest", file=sys.stderr)
        return 1

    # Collect all declared nodeids
    declared_nodeids: set[str] = set()
    for crit_id, crit in criteria.items():
        for nid in crit.get("nodeids", []):
            declared_nodeids.add(nid)

    print(f"Manifest: {len(criteria)} criteria, {len(declared_nodeids)} unique nodeids")

    # Collect actual test nodeids from pytest
    actual_nodeids = _collect_nodeids(["tests/m2_public/"])
    print(f"Collected: {len(actual_nodeids)} nodeids from pytest")

    # Verify every declared nodeid exists
    missing = declared_nodeids - actual_nodeids
    extra = actual_nodeids - declared_nodeids

    if missing:
        print(f"\nERROR: {len(missing)} declared nodeids not found:")
        for nid in sorted(missing):
            print(f"  - {nid}")
        return 1

    if extra:
        print(f"\nWARNING: {len(extra)} collected nodeids not in manifest:")
        for nid in sorted(extra):
            print(f"  - {nid}")

    # Run each criterion independently
    print(f"\nRunning {len(criteria)} criteria independently...")
    results: dict[str, dict[str, Any]] = {}
    passed = 0
    failed = 0

    for crit_id in sorted(criteria.keys()):
        nodeids = criteria[crit_id]["nodeids"]
        for nid in nodeids:
            print(f"  {crit_id}: {nid} ... ", end="", flush=True)
            r = _run_test(nid, verbose=verbose)
            results[f"{crit_id}: {nid}"] = r
            if r["passed"]:
                print("PASS")
                passed += 1
            else:
                print(f"FAIL (exit={r['exit_code']})")
                failed += 1

    print(f"\n=== Results ===")
    print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")

    # Write results
    results_path = _repo_root() / "dev" / "m2_acceptance_results.json"
    with open(results_path, "w") as f:
        json.dump({
            "schema_version": "m2_acceptance_results.v1",
            "passed": passed,
            "failed": failed,
            "results": results,
        }, f, indent=2, sort_keys=True)
    print(f"Results written to: {results_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
