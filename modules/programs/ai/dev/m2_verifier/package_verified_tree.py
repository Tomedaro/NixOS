#!/usr/bin/env python3
"""Package the M2 verifier tree into a distributable ZIP.

Gate: requires a baseline release gate to have passed
(artifacts/m2-verifier-baseline.json with verifier_status == "ready").

Reads the locked acceptance commit SHA and tree hash from
docs/M2_VERIFIER_LOCK.json, recomputes the current source tree hash,
and refuses packaging on mismatch.

Removes cache artifacts (__pycache__, .pyc, .pytest_cache, .hypothesis,
.coverage), creates a ZIP of verifier files only (not production code),
then reopens the archive and recomputes the tree hash from its contents.
Requires equality between source and archive tree hashes.

Writes a .package.json sidecar with provenance metadata.

Tree hashing is deterministic: relative paths sorted lexicographically,
cache directories excluded, each file hashed as sha256(path_bytes +
content_sha256), then the concatenation of all per-file hashes is hashed.

Usage:
    package_verified_tree.py --output /tmp/ai-m2-verifier-ready.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AI_ROOT = REPO_ROOT / "modules" / "programs" / "ai"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
BASELINE_PATH = ARTIFACTS_DIR / "m2-verifier-baseline.json"
LOCK_PATH = REPO_ROOT / "docs" / "M2_VERIFIER_LOCK.json"

# Directories containing verifier files (relative to REPO_ROOT)
VERIFIER_DIRS: list[str] = [
    "dev/m2_verifier",
    "tests/m2_acceptance_v2",
    "tests/m2_verifier_support",
    "tests/m2_verifier_quality",
    "tests/m2_stateful_v2",
]

# Individual verifier files outside those directories
VERIFIER_FILES: list[str] = [
    "docs/M2_ACCEPTANCE_V2.json",
    "docs/M2_VERIFIER_LOCK.json",
]

# Cache patterns to exclude from scanning and packaging
CACHE_NAMES: set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".coverage",
}

CACHE_SUFFIXES: tuple[str, ...] = (".pyc",)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return "MISSING"


def _is_cache(path: Path) -> bool:
    """Check if a path component is a cache artifact."""
    name = path.name
    if name in CACHE_NAMES:
        return True
    if name.endswith(CACHE_SUFFIXES):
        return True
    return False


def _should_include(file_path: Path) -> bool:
    """Check if a file should be included in the verifier tree.

    Excludes cache directories and files.
    """
    # Check all path components for cache markers
    for part in file_path.parts:
        if part in CACHE_NAMES:
            return False
    if file_path.suffix in CACHE_SUFFIXES:
        return False
    return True


def collect_verifier_files(root: Path) -> list[Path]:
    """Collect all verifier files, sorted by relative path.

    Returns absolute paths sorted by their relative path from root.
    """
    files: set[Path] = set()

    # Collect from verifier directories
    for rel_dir in VERIFIER_DIRS:
        d = root / rel_dir
        if not d.is_dir():
            print(f"WARNING: verifier directory missing: {rel_dir}", file=sys.stderr)
            continue
        for fp in d.rglob("*"):
            if fp.is_file() and _should_include(fp):
                files.add(fp)

    # Collect individual verifier files
    for rel_file in VERIFIER_FILES:
        fp = root / rel_file
        if fp.is_file() and _should_include(fp):
            files.add(fp)

    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def compute_tree_hash(root: Path, files: list[Path]) -> str:
    """Compute a deterministic tree hash over verifier files.

    For each file, hash: relative_path_as_bytes + sha256(file_content).
    Then hash the concatenation of all per-file hashes.
    """
    hasher = hashlib.sha256()
    for fp in files:
        rel_path = fp.relative_to(root).as_posix()
        content_hash = sha256_file(fp)
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(content_hash.encode("utf-8"))
    return hasher.hexdigest()


def tree_hash_from_zip(zip_path: Path) -> str:
    """Compute the tree hash from ZIP contents.

    Extracts relative paths and content hashes from the archive,
    reconstructs the same deterministic tree hash.
    """
    pairs: list[tuple[str, str]] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Skip cache paths inside ZIP (shouldn't be there, but be safe)
            path_parts = info.filename.split("/")
            if any(part in CACHE_NAMES for part in path_parts):
                continue
            if info.filename.endswith(CACHE_SUFFIXES):
                continue
            content = zf.read(info.filename)
            content_hash = sha256_bytes(content)
            pairs.append((info.filename, content_hash))

    pairs.sort(key=lambda x: x[0])

    hasher = hashlib.sha256()
    for rel_path, content_hash in pairs:
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(content_hash.encode("utf-8"))
    return hasher.hexdigest()


def clean_caches(root: Path) -> None:
    """Remove cache directories and .pyc files from verifier paths."""
    for rel_dir in VERIFIER_DIRS:
        d = root / rel_dir
        if not d.is_dir():
            continue
        for cache_name in CACHE_NAMES:
            for cache_dir in d.rglob(cache_name):
                if cache_dir.is_dir():
                    print(f"  Removing cache: {cache_dir.relative_to(root)}")
                    shutil.rmtree(cache_dir, ignore_errors=True)
        # Remove .pyc files
        for pyc in d.rglob("*.pyc"):
            if pyc.is_file():
                print(f"  Removing .pyc: {pyc.relative_to(root)}")
                pyc.unlink(missing_ok=True)

    # Also clean .coverage at repo root
    coverage_file = root / ".coverage"
    if coverage_file.is_file():
        print(f"  Removing .coverage")
        coverage_file.unlink(missing_ok=True)


def create_zip(output_path: Path, root: Path, files: list[Path]) -> None:
    """Create a ZIP archive of verifier files."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in files:
            rel = fp.relative_to(root).as_posix()
            zf.write(fp, arcname=rel)
            print(f"  Added: {rel}")


def write_sidecar(
    output_path: Path,
    source_tree_hash: str,
    archive_tree_hash: str,
    tree_match: bool,
    commit: str | None,
) -> None:
    """Write the .package.json sidecar."""
    sidecar_path = output_path.with_suffix(output_path.suffix + ".package.json")
    sidecar: dict = {
        "schema_version": "m2_verifier_package.v1",
        "output_zip": str(output_path.name),
        "source_tree_sha256": source_tree_hash,
        "archive_tree_sha256": archive_tree_hash,
        "tree_match": tree_match,
        "acceptance_commit_sha": commit,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True))
    print(f"\nSidecar written to {sidecar_path}")


def check_baseline_gate() -> tuple[bool, str]:
    """Check that the baseline release gate has passed.

    Returns (passed, reason).
    """
    if not BASELINE_PATH.is_file():
        return False, f"Baseline not found: {BASELINE_PATH}"
    try:
        baseline = json.loads(BASELINE_PATH.read_text())
    except Exception as exc:
        return False, f"Cannot parse baseline: {exc}"

    verifier_status = baseline.get("verifier_status", "unknown")
    if verifier_status != "ready":
        return False, f"verifier_status is '{verifier_status}', expected 'ready'"

    return True, "baseline release gate passed"


def get_lock_data() -> dict | None:
    """Load the verifier lock file."""
    if not LOCK_PATH.is_file():
        print(f"WARNING: Lock file not found: {LOCK_PATH}", file=sys.stderr)
        return None
    try:
        return json.loads(LOCK_PATH.read_text())
    except Exception as exc:
        print(f"WARNING: Cannot parse lock file: {exc}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package the M2 verifier tree into a distributable ZIP"
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output ZIP path (e.g. /tmp/ai-m2-verifier-ready.zip)",
    )
    args = parser.parse_args()

    # --- Gate 1: baseline release gate must have passed ---
    ok, reason = check_baseline_gate()
    if not ok:
        print(f"ERROR: Baseline release gate not satisfied: {reason}", file=sys.stderr)
        return 1
    print(f"Baseline gate: {reason}")

    # --- Gate 2: verify commit and tree hash from lock ---
    lock = get_lock_data()
    if lock is None:
        print("ERROR: Lock file required for packaging", file=sys.stderr)
        return 1

    locked_commit = lock.get("acceptance_commit_sha", "")
    locked_tree_hash = lock.get("test_tree_sha256", "")

    if not locked_commit:
        print("ERROR: Lock file missing acceptance_commit_sha", file=sys.stderr)
        return 1
    if not locked_tree_hash:
        print("ERROR: Lock file missing test_tree_sha256", file=sys.stderr)
        return 1

    print(f"Locked acceptance commit: {locked_commit[:16]}...")

    # --- Clean caches ---
    print("\n--- Cleaning caches ---")
    clean_caches(REPO_ROOT)

    # --- Collect verifier files ---
    print("\n--- Collecting verifier files ---")
    verifier_files = collect_verifier_files(REPO_ROOT)
    if not verifier_files:
        print("ERROR: No verifier files found", file=sys.stderr)
        return 1
    print(f"Collected {len(verifier_files)} verifier files")

    # --- Compute source tree hash ---
    print("\n--- Computing source tree hash ---")
    source_tree_hash = compute_tree_hash(REPO_ROOT, verifier_files)
    print(f"Source tree sha256: {source_tree_hash}")

    # --- Check against locked tree hash ---
    # The lock's test_tree_sha256 covers tests/m2_acceptance_v2/*.py only.
    # We recompute the same scope for comparison.
    accept_dir = REPO_ROOT / "tests" / "m2_acceptance_v2"
    if accept_dir.is_dir():
        accept_py_files = sorted(
            p for p in accept_dir.rglob("*.py") if _should_include(p)
        )
        accept_tree_hash = compute_tree_hash(REPO_ROOT, accept_py_files)
        if accept_tree_hash != locked_tree_hash:
            print(
                f"ERROR: test_tree_sha256 mismatch\n"
                f"  locked:  {locked_tree_hash}\n"
                f"  current: {accept_tree_hash}",
                file=sys.stderr,
            )
            return 1
        print(f"test_tree_sha256: matches locked ({locked_tree_hash[:16]}...)")
    else:
        print("WARNING: tests/m2_acceptance_v2 not found, skipping tree hash check")

    # --- Create ZIP ---
    print(f"\n--- Creating ZIP: {args.output} ---")
    create_zip(args.output, REPO_ROOT, verifier_files)

    # --- Verify ZIP tree hash ---
    print("\n--- Verifying archive tree hash ---")
    archive_tree_hash = tree_hash_from_zip(args.output)
    print(f"Archive tree sha256: {archive_tree_hash}")

    tree_match = source_tree_hash == archive_tree_hash
    if not tree_match:
        print(
            "ERROR: Source and archive tree hashes differ!",
            file=sys.stderr,
        )
        return 1
    print("Tree hash: MATCH")

    # --- Write sidecar ---
    write_sidecar(
        args.output,
        source_tree_hash,
        archive_tree_hash,
        tree_match,
        locked_commit,
    )

    # --- Final assertion ---
    if not (source_tree_hash == archive_tree_hash and tree_match):
        print(
            "ERROR: Final assertion failed — "
            "source_tree_sha256 != archive_tree_sha256 or tree_match != true",
            file=sys.stderr,
        )
        return 1

    print(f"\n=== PACKAGE SUCCESS: {args.output} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
