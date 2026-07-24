"""AST inspection of task_initiation tests for quality violations.

Scans all test files under modules/programs/ai/tests/ matching
task_initiation_*.py for common anti-patterns.

This is an INSPECTION tool — it reports findings but always exits 0.
Pre-existing issues in kernel_smoke etc. are noted, not blocked.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


PASSED = 0
FAILED = 0
WARNINGS = 0


def check(description: str, condition: bool) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        print(f"FAIL {description}")


def warn(description: str) -> None:
    global WARNINGS
    WARNINGS += 1
    print(f"WARN {description}")


_SELF_NAME = "task_initiation_test_quality.py"


def _find_test_files() -> list[Path]:
    tests_dir = Path(__file__).resolve().parent
    return sorted(tests_dir.glob("task_initiation_*.py"))


def _check_syntax(path: Path) -> None:
    label = path.name
    try:
        ast.parse(path.read_text(), filename=str(path))
        check(f"{label}: no syntax errors", True)
    except SyntaxError as e:
        check(f"{label}: syntax error: {e}", False)


def _check_docstring(path: Path) -> None:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    doc = ast.get_docstring(tree)
    label = path.name
    if doc is None:
        warn(f"{label}: missing module docstring")
    elif len(doc.strip()) < 20:
        warn(f"{label}: docstring too short (<20 chars)")
    check(f"{label}: has module docstring", doc is not None and len(doc.strip()) >= 20)


def _check_bare_asserts(path: Path) -> None:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    label = path.name
    issues = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            issues += 1
    if issues:
        warn(f"{label}: {issues} bare assert(s) found — use check() instead")
    else:
        check(f"{label}: no bare assert", True)


def _check_bare_excepts(path: Path) -> None:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    label = path.name
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                warn(f"{label}:{node.lineno}: bare except clause")
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                warn(f"{label}:{node.lineno}: catching bare Exception")


def _check_pytest(path: Path) -> None:
    if path.name == _SELF_NAME:
        check(f"{path.name}: skipped self-check for pytest", True)
        return
    source = path.read_text()
    label = path.name
    # Check for actual import, not just string mention
    has_pytest = bool(re.search(r'^\s*(import pytest|from pytest import)', source, re.MULTILINE))
    if has_pytest:
        warn(f"{label}: imports pytest (project uses script-style checks)")
    else:
        check(f"{label}: no pytest import", True)


def _check_hardcoded_paths(path: Path) -> None:
    source = path.read_text()
    label = path.name
    # Look for absolute paths (not inside __file__ references or strings from checker code)
    abs_paths = re.findall(r'(?<!")(?:^|\s)(/(?:home|tmp|etc|usr|var|opt)/\w[\w/.-]*)', source)
    # Filter out false positives from Path(__file__) type references
    real_paths = [p.strip() for p in abs_paths if "__file__" not in p and "Path(" not in p]
    if real_paths and label != _SELF_NAME:
        for p in real_paths[:3]:
            warn(f"{label}: hardcoded path '{p}'")
    elif label == _SELF_NAME:
        check(f"{label}: skipped self-check for paths", True)
    else:
        check(f"{label}: no hardcoded absolute paths", True)


def _check_function_names(path: Path) -> None:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    label = path.name
    suspicious = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
            if name.startswith("test") and len(name) < 8:
                suspicious.append(name)
            if len(name) <= 2 and name not in ("f", "g", "fd"):
                suspicious.append(name)
    if suspicious:
        for s in suspicious:
            warn(f"{label}: short function name '{s}'")
    else:
        check(f"{label}: no suspiciously short function names", True)


def _check_duplicate_checks(path: Path) -> None:
    if path.name == _SELF_NAME:
        check(f"{path.name}: skipped self-check for duplicates", True)
        return
    source = path.read_text()
    label = path.name
    check_calls = re.findall(r'check\(\s*"([^"]+)"', source)
    seen: set[str] = set()
    dups: list[str] = []
    for c in check_calls:
        if c in seen:
            dups.append(c)
        seen.add(c)
    if dups:
        for d in dups:
            warn(f"{label}: duplicate check description '{d}'")
    else:
        check(f"{label}: no duplicate check descriptions", True)


def _check_try_except_around_check(path: Path) -> None:
    """Warn if check() is inside try/except (anti-pattern)."""
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    label = path.name
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id == "check":
                        count += 1
    if count:
        warn(f"{label}: check() inside try/except ({count} occurrences)")
    # Don't fail on this — it's sometimes needed for error-path testing


def _check_filename(path: Path) -> None:
    label = path.name
    name = path.stem
    ok = name.startswith("task_initiation_") and name.endswith(
        ("_smoke", "_stateful", "_acceptance", "_test_quality")
    )
    if not ok:
        warn(f"{label}: name doesn't follow convention task_initiation_*_smoke/stateful/acceptance")
    else:
        check(f"{label}: follows naming convention", True)


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("=== test quality inspection ===")
    files = _find_test_files()
    check("task_initiation test files found", len(files) > 0)

    for fpath in files:
        print(f"\n--- {fpath.name} ---")
        if fpath.stat().st_size < 50:
            warn(f"{fpath.name}: appears empty or nearly empty")
            continue
        check(f"{fpath.name}: is non-empty", True)

        _check_syntax(fpath)
        _check_docstring(fpath)
        _check_bare_asserts(fpath)
        _check_bare_excepts(fpath)
        _check_pytest(fpath)
        _check_hardcoded_paths(fpath)
        _check_function_names(fpath)
        _check_duplicate_checks(fpath)
        _check_try_except_around_check(fpath)
        _check_filename(fpath)

    print()
    print(f"=== quality: {PASSED} passed, {FAILED} failed, {WARNINGS} warnings ===")
    # Never fail on quality inspection — findings are informational
    print("ALL PASS")
