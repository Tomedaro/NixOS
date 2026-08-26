#!/usr/bin/env python3
"""Validate the M2 acceptance manifest against reality.

1. Parse M2_ACCEPTANCE_V2.json (with fallback to M2_ACCEPTANCE.json).
2. Run pytest --collect-only to discover available test node IDs.
3. Validate every manifest nodeid maps to at least one collected test.
4. Reject any test file containing pytest.skip / pytest.xfail / importorskip
   or @pytest.mark.skip / @pytest.mark.xfail decorators.
5. Exit nonzero on any error.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHONPATH = str(REPO_ROOT / "python")
TIMEOUT_SECONDS = 120

DEFAULT_MANIFEST_PATHS = [
    REPO_ROOT / "docs" / "M2_ACCEPTANCE_V2.json",
    REPO_ROOT / "docs" / "M2_ACCEPTANCE.json",
]

# Test directories to scan for xfail/skip markers
TEST_DIRS = [
    REPO_ROOT / "tests" / "m2_acceptance_v2",
    REPO_ROOT / "tests" / "m2_stateful_v2",
    REPO_ROOT / "tests" / "m2_verifier_quality",
]


def find_manifest() -> Path:
    for p in DEFAULT_MANIFEST_PATHS:
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"No manifest found at {DEFAULT_MANIFEST_PATHS}"
    )


def run_pytest_collect() -> set[str]:
    """Run pytest --collect-only -q and return set of collected node IDs."""
    env = {**os.environ, "PYTHONPATH": PYTHONPATH}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print("ERROR: pytest --collect-only timed out", file=sys.stderr)
        sys.exit(3)

    if result.returncode != 0:
        print(f"ERROR: pytest --collect-only failed (exit {result.returncode})", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        sys.exit(3)

    collected: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("=") and "ERROR" not in line:
            parts = line.split()
            for part in parts:
                if "::" in part and part.count("::") == 1:
                    collected.add(part)
    return collected


def scan_test_files_for_prohibited_markers() -> list[str]:
    """Scan test files for pytest.skip/xfail/importorskip markers."""
    violations: list[str] = []
    for test_dir in TEST_DIRS:
        if not test_dir.is_dir():
            continue
        for pyfile in sorted(test_dir.rglob("*.py")):
            try:
                source = pyfile.read_text()
            except Exception as exc:
                violations.append(f"{pyfile}: cannot read: {exc}")
                continue

            rel = pyfile.relative_to(REPO_ROOT)
            # pytest.skip / pytest.xfail / importorskip in source
            if "pytest.skip" in source:
                violations.append(f"{rel}: contains pytest.skip")
            if "pytest.xfail" in source:
                violations.append(f"{rel}: contains pytest.xfail")
            if "importorskip" in source:
                violations.append(f"{rel}: contains importorskip")
            if re.search(r'@pytest\.mark\.(skip|xfail)', source):
                violations.append(f"{rel}: contains @pytest.mark.skip/xfail decorator")

    return violations


def match_criterion_to_tests(
    criterion_id: str, nodeids: list[str], collected: set[str]
) -> dict:
    """Check if a criterion's nodeids have corresponding pytest test nodes.

    A nodeid is considered "matched" if any collected test nodeid
    contains the criterion id as a substring (e.g., "M2-V01" matches
    "test_M2_V01_stuck_ingestion") OR the literal nodeid appears in
    any collected test nodeid.
    """
    matched: list[str] = []
    unmatched: list[str] = []

    # Build mapping: criterion id token → test nodeids
    cid_token = criterion_id.replace("-", "_")  # M2-V01 → M2_V01

    for nid in nodeids:
        found = 0
        best_match = ""
        for c in collected:
            if nid in c or cid_token in c:
                found += 1
                best_match = c
        if found == 0:
            unmatched.append(nid)
        elif found > 1:
            unmatched.append(f"{nid} (ambiguous: matched {found} tests including {best_match})")
        else:
            matched.append(best_match)
    return {"criterion": criterion_id, "matched": matched, "unmatched": unmatched}


def main() -> int:
    errors = 0

    # 1. Find and parse manifest
    try:
        manifest_path = find_manifest()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

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

    # 2. Collect pytest node IDs
    print("\n--- Collecting pytest node IDs ---")
    collected = run_pytest_collect()
    print(f"Collected node IDs: {len(collected)}")

    # 3. Scan for prohibited markers
    print("\n--- Scanning for prohibited markers ---")
    marker_violations = scan_test_files_for_prohibited_markers()
    if marker_violations:
        print(f"FOUND {len(marker_violations)} prohibited marker(s):")
        for v in marker_violations:
            print(f"  PROHIBITED: {v}")
        errors += len(marker_violations)
    else:
        print("No prohibited markers found.")

    for entry in criteria_list:
        cid = entry.get("id", "unknown")
        nodeids = entry.get("nodeids", [])
        expect = entry.get("baseline_expectation", entry.get("release_expectation", "pass"))
        desc = entry.get("description", "")[:80]

        # Check for bare names (node IDs without ::)
        bare = [n for n in nodeids if "::" not in n]
        if bare:
            for b in bare:
                print(f"  BARE NAME {cid}: nodeid '{b}' is not a fully-qualified pytest node ID")
                errors += 1

        result = match_criterion_to_tests(cid, nodeids, collected)

        matched = result["matched"]
        unmatched = result["unmatched"]

        total_matched += len(matched)
        total_unmatched += len(unmatched)

        if unmatched:
            errors += len(unmatched)
            print(f"  MISMATCH {cid} [{expect}]: {desc}")
            for u in unmatched:
                print(f"    UNMATCHED nodeid: {u}")
        else:
            print(f"  OK {cid} [{expect}]: {len(matched)} test(s) covering {len(nodeids)} nodeid(s)")

    print(f"\n--- SUMMARY: {total_matched} matched, {total_unmatched} unmatched nodeid(s) ---")

    if errors:
        print(f"VALIDATION FAILED: {errors} error(s)")
        return 1

    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
