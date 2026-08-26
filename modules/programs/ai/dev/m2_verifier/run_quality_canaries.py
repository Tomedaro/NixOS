#!/usr/bin/env python3
"""Apply 19 verifier mutations (V01-V19) one at a time in temp worktrees
and verify the quality gate rejects each.

Each mutation injects a prohibited pattern into a test file, runs the quality
gate, and confirms it fails. Exit 0 only if all 19 are rejected.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QUALITY_GATE = Path(__file__).resolve().parent / "test_quality.py"
VERIFIER_TEST_DIR = REPO_ROOT / "tests" / "m2_verifier_quality"


# ---------------------------------------------------------------------------
# V01-V19: Mutation definitions
# ---------------------------------------------------------------------------

MUTATIONS: list[dict] = [
    {
        "id": "V01",
        "description": "assert True in test function",
        "inject": "def test_v01_bad():\n    assert True\n",
    },
    {
        "id": "V02",
        "description": "raise Exception instead of specific",
        "inject": "def test_v02_bad():\n    raise Exception('generic')\n",
    },
    {
        "id": "V03",
        "description": "except Exception: pass",
        "inject": "def test_v03_bad():\n    try:\n        pass\n    except Exception:\n        pass\n",
    },
    {
        "id": "V04",
        "description": "bare except: pass",
        "inject": "def test_v04_bad():\n    try:\n        pass\n    except:\n        pass\n",
    },
    {
        "id": "V05",
        "description": "pytest.skip() call",
        "inject": "import pytest\ndef test_v05_bad():\n    pytest.skip('skip this')\n",
    },
    {
        "id": "V06",
        "description": "pytest.xfail() call",
        "inject": "import pytest\ndef test_v06_bad():\n    pytest.xfail('expected fail')\n",
    },
    {
        "id": "V07",
        "description": "SKIP comment",
        "inject": "# SKIP: not ready yet\ndef test_v07_good():\n    assert 1 == 1\n",
    },
    {
        "id": "V08",
        "description": "KNOWN DEFECT comment",
        "inject": "# KNOWN DEFECT: will fix later\ndef test_v08_good():\n    assert 1 == 1\n",
    },
    {
        "id": "V09",
        "description": "unconditional return before assertion",
        "inject": "def test_v09_bad():\n    return None\n    assert False\n",
    },
    {
        "id": "V10",
        "description": "import-time check() call",
        "inject": "check('v10', True)\ndef test_v10_good():\n    pass\n",
    },
    {
        "id": "V11",
        "description": "pytest.importorskip call",
        "inject": "def test_v11_bad():\n    import pytest; pytest.importorskip('nonexistent')\n",
    },
    {
        "id": "V12",
        "description": "KNOWN ISSUE comment",
        "inject": "# KNOWN ISSUE #999\ndef test_v12_good():\n    assert 1 == 1\n",
    },
    {
        "id": "V13",
        "description": "bare except with empty body",
        "inject": "def test_v13_bad():\n    try:\n        pass\n    except:\n        pass\n",
    },
    {
        "id": "V14",
        "description": "test function without assertions",
        "inject": "def test_v14_bad():\n    x = 1\n    y = 2\n",
    },
    {
        "id": "V15",
        "description": "except Exception with empty body",
        "inject": "def test_v15_bad():\n    try:\n        pass\n    except Exception:\n        pass\n",
    },
    {
        "id": "V16",
        "description": "@pytest.mark.skip decorator",
        "inject": chr(64) + "pytest.mark.skip\ndef test_v16_bad():\n    assert 1\n",
    },
    {
        "id": "V17",
        "description": "@pytest.mark.xfail decorator",
        "inject": chr(64) + "pytest.mark.xfail\ndef test_v17_bad():\n    assert 1\n",
    },
    {
        "id": "V18",
        "description": "assert False (tautological)",
        "inject": "def test_v18_bad():\n    assert False\n",
    },
    {
        "id": "V19",
        "description": "time.sleep() in test function",
        "inject": "import time\ndef test_v19_bad():\n    time.sleep(0.1)\n    assert 1 == 1\n",
    },
]


def create_mutated_worktree(mutation: dict) -> Path:
    """Create a temp directory with a contaminated test file."""
    td = tempfile.mkdtemp(prefix=f"m2canary_{mutation['id']}_")
    tdir = Path(td)

    # Copy existing verifier quality tests (if any)
    if VERIFIER_TEST_DIR.is_dir():
        for f in VERIFIER_TEST_DIR.iterdir():
            if f.is_file() and f.suffix == ".py":
                (tdir / f.name).write_text(f.read_text())

    # Write the mutant file
    mutant_path = tdir / f"test_mutant_{mutation['id'].lower()}.py"
    mutant_path.write_text(mutation["inject"])
    return tdir


def run_quality_on(path: Path, mutation: dict) -> subprocess.CompletedProcess:
    """Run the quality gate against a specific test directory."""
    # Verify the mutation was applied before running the gate
    mutant_file = path / f"test_mutant_{mutation['id'].lower()}.py"
    if not mutant_file.is_file():
        raise RuntimeError(f"Mutation {mutation['id']}: mutant file not found")
    content = mutant_file.read_text()
    inject = mutation["inject"]
    # Verify the injected code is present
    first_line = inject.strip().split("\n")[0].strip()
    if first_line not in content:
        raise RuntimeError(
            f"Mutation {mutation['id']}: target NOT changed — "
            f"injected first line not found in mutant file"
        )
    # Build a wrapper script to run the quality gate on our temp dir
    wrapper = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(QUALITY_GATE.parent)!r})
        from test_quality import inspect_file
        from pathlib import Path

        td = Path({str(path)!r})
        test_files = sorted(td.glob("test_*.py"))
        import test_quality as tq
        tq.FAILED = 0
        for fp in test_files:
            inspect_file(fp)

        if tq.FAILED == 0:
            print("QUALITY GATE: PASSED (unexpected — mutation should fail)")
            sys.exit(0)
        else:
            print(f"QUALITY GATE: FAILED (correctly rejected {{tq.FAILED}} issue(s))")
            sys.exit(1)
    """)
    wrapper_path = path / "_run_quality.py"
    wrapper_path.write_text(wrapper)

    result = subprocess.run(
        [sys.executable, str(wrapper_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        timeout=60,
    )
    return result


def main() -> int:
    print(f"=== Quality Canaries (V01-V{len(MUTATIONS)}) ===")
    rejected = 0
    passed = 0

    for mutation in MUTATIONS:
        vid = mutation["id"]
        desc = mutation["description"]
        print(f"\n--- {vid}: {desc} ---")

        worktree = None
        try:
            worktree = create_mutated_worktree(mutation)
            result = run_quality_on(worktree, mutation)

            if result.returncode != 0:
                print(f"  REJECTED (exit {result.returncode})")
                rejected += 1
            else:
                print(f"  PASSED (UNEXPECTED — quality gate did not reject!)")
                print(f"  stdout: {result.stdout[-500:]}")
                passed += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            passed += 1
        finally:
            if worktree is not None:
                try:
                    shutil.rmtree(str(worktree))
                except Exception:
                    pass

    print(f"\n=== CANARY RESULTS: {rejected}/{len(MUTATIONS)} rejected ===")

    if rejected == len(MUTATIONS):
        print("ALL CANARIES: CORRECTLY REJECTED")
        return 0
    else:
        print(f"FAIL: {passed} mutation(s) slipped through quality gate")
        return 1


if __name__ == "__main__":
    sys.exit(main())
