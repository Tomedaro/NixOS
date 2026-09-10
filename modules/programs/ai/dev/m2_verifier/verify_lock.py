#!/usr/bin/env python3
"""Verify M2_VERIFIER_LOCK.json integrity.

Recomputes all hashes listed in the lock file and compares against
stored values.  Fails on any mismatch.

Distinguishes:
  - "Git commit unavailable" — cannot verify the acceptance commit SHA
    (e.g., repo not a Git working tree, or the locked commit not in history).
  - "verified" — the Git HEAD matches the locked commit SHA.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCK_PATH = REPO_ROOT / "docs" / "M2_VERIFIER_LOCK.json"
TIMEOUT_SECONDS = 30


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return "MISSING"


def get_git_commit_sha(cwd: Path | None = None) -> str | None:
    """Return the current Git HEAD commit SHA, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(cwd or REPO_ROOT),
            timeout=TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def check_git_commit_exists(sha: str, cwd: Path | None = None) -> bool:
    """Check if a given commit SHA exists in the repo."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", sha],
            capture_output=True, text=True, cwd=str(cwd or REPO_ROOT),
            timeout=TIMEOUT_SECONDS,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def main() -> int:
    if not LOCK_PATH.is_file():
        print(f"ERROR: Lock file not found: {LOCK_PATH}", file=sys.stderr)
        return 2

    try:
        lock = json.loads(LOCK_PATH.read_text())
    except Exception as exc:
        print(f"ERROR: Cannot parse lock file: {exc}", file=sys.stderr)
        return 2

    errors = 0

    print(f"Lock version: {lock.get('lock_version', 'unknown')}")
    print(f"Generated at: {lock.get('generated_at', 'unknown')}")

    # --- Git commit verification ---
    locked_sha = lock.get("acceptance_commit_sha")
    if locked_sha:
        exists = check_git_commit_exists(locked_sha)
        current = get_git_commit_sha()
        if not exists and current is None:
            print(f"  Git commit: UNAVAILABLE — commit=null (git not available)")
        elif current is None:
            print(f"  Git commit: UNAVAILABLE — cannot get current HEAD")
            errors += 1
        elif current == locked_sha:
            print(f"  Git commit: VERIFIED — HEAD matches locked {locked_sha[:16]}...")
        else:
            print(f"  Git commit: MISMATCH — locked={locked_sha[:16]}... current={current[:16]}...")
            errors += 1
    else:
        print(f"  Git commit: NOT SET (commit=null in lock file)")

    # --- Aggregate hashes ---
    aggregate_hashes = {
        "manifest_sha256": "docs/M2_ACCEPTANCE_V2.json",
        "test_tree_sha256": "tests/m2_acceptance_v2",
        "corpus_sha256": "tests/m2_verifier_support/m2_transition_corpus.json",
    }

    for key, rel_path in aggregate_hashes.items():
        stored = lock.get(key, "")
        path = REPO_ROOT / rel_path
        if path.is_dir():
            # Compute directory tree hash: hash of all file hashes
            hasher = hashlib.sha256()
            for fp in sorted(path.rglob("*.py")):
                hasher.update(fp.relative_to(REPO_ROOT).as_posix().encode())
                hasher.update(sha256_file(fp).encode())
            current = hasher.hexdigest()
        else:
            current = sha256_file(path)

        if stored and stored != current:
            print(f"  MISMATCH {key}:")
            print(f"    stored:  {stored[:32]}...")
            print(f"    current: {current[:32]}...")
            errors += 1
        elif stored:
            print(f"  OK {key}: matches ({current[:16]}...)")
        else:
            print(f"  SKIP {key}: not in lock")

    # --- Individual file hashes ---
    files = lock.get("files", {})
    for rel_path, stored_hash in sorted(files.items()):
        path = REPO_ROOT / rel_path
        current = sha256_file(path)
        if current == "MISSING":
            print(f"  MISSING {rel_path}")
            errors += 1
        elif stored_hash != current:
            print(f"  MISMATCH {rel_path}:")
            print(f"    stored:  {stored_hash[:32]}...")
            print(f"    current: {current[:32]}...")
            errors += 1
        else:
            print(f"  OK {rel_path}: matches ({current[:16]}...)")

    if errors:
        print(f"\nLOCK VERIFICATION FAILED: {errors} error(s)")
        return 1

    print("\nLOCK VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
