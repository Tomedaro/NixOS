#!/usr/bin/env python3
"""Print SHA-256 hashes of the 5 production task_initiation files.

Exit 0 on success; nonzero on any missing file.
"""
import hashlib
import sys
from pathlib import Path

PRODUCTION_FILES: list[str] = [
    "python/ai_system/task_initiation_contracts.py",
    "python/ai_system/task_initiation_private.py",
    "python/ai_system/task_initiation_store.py",
    "python/ai_system/task_initiation_kernel.py",
    "python/ai_system/task_initiation_cli.py",
]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    failed = False
    for rel in PRODUCTION_FILES:
        fp = REPO_ROOT / rel
        if not fp.is_file():
            print(f"MISSING {rel}", file=sys.stderr)
            failed = True
        else:
            h = sha256_file(fp)
            print(f"{h}  {rel}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
