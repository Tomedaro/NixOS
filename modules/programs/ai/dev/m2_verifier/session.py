#!/usr/bin/env python3
"""Write the M2 verifier session artifact.

Creates artifacts/m2-verifier-session.json with repository metadata
captured before the release gate runs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AI_ROOT = REPO_ROOT / "modules" / "programs" / "ai"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

PRODUCTION_FILES: list[str] = [
    "python/ai_system/task_initiation_contracts.py",
    "python/ai_system/task_initiation_private.py",
    "python/ai_system/task_initiation_store.py",
    "python/ai_system/task_initiation_kernel.py",
    "python/ai_system/task_initiation_cli.py",
]


def sha256_file(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return "MISSING"


def get_git_commit(cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(cwd or REPO_ROOT),
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    commit = get_git_commit()
    production_hashes = {
        rel: sha256_file(REPO_ROOT / rel) for rel in PRODUCTION_FILES
    }

    session: dict = {
        "schema_version": "m2_verifier_session.v1",
        "repository_root": str(REPO_ROOT.resolve()),
        "ai_root": str(AI_ROOT.resolve()),
        "commit": commit,
        "started_at": int(time.time()),
        "production_hashes_before": production_hashes,
    }

    out_path = ARTIFACTS_DIR / "m2-verifier-session.json"
    out_path.write_text(json.dumps(session, indent=2, sort_keys=True))
    print(f"Session artifact written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
