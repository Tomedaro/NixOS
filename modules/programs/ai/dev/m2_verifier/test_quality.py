#!/usr/bin/env python3
"""Quality gate that inspects all verifier test files for prohibited patterns.

Scans ALL verifier test files (Section 11).
Warnings are failures — every violation exits nonzero.

Prohibited patterns:
  1.  assert True / assert False (tautological)
  2.  raise Exception (not specific)
  3.  except Exception (too broad)
  4.  bare except:
  5.  except: pass / except Exception: pass (silent suppression)
  6.  except with empty body
  7.  pytest.skip() / pytest.xfail()
  8.  importorskip
  9.  @pytest.mark.skip / @pytest.mark.xfail decorators
  10. SKIP / KNOWN DEFECT / KNOWN ISSUE comments
  11. Unconditional return before assertion in test functions
  12. Import-time execution: check()/raises() at module level
  13. Test functions without assertions
  14. time.sleep() in test functions
  15. print() calls in test functions (potential debugging)
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFIER_TEST_DIRS: list[Path] = [
    REPO_ROOT / "tests" / "m2_verifier_quality",
    REPO_ROOT / "tests" / "m2_stateful_v2",
]

SELF_FILE = Path(__file__).resolve()

FAILED = 0


def fail(message: str) -> None:
    global FAILED
    FAILED += 1
    print(f"FAIL {message}")


def _check_ast(path: Path, source: str, tree: ast.AST) -> None:
    label = path.name

    class Visitor(ast.NodeVisitor):
        def visit_Assert(self, node: ast.Assert) -> None:
            if isinstance(node.test, ast.Constant):
                val = node.test.value
                if val is True or val is False:
                    fail(f"{label}:{node.lineno}: assert {val} (tautological)")
            self.generic_visit(node)

        def visit_Raise(self, node: ast.Raise) -> None:
            if node.exc is not None:
                if isinstance(node.exc, ast.Call):
                    func = node.exc.func
                    if isinstance(func, ast.Name) and func.id == "Exception":
                        fail(f"{label}:{node.lineno}: raises(Exception) instead of specific exception")
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            is_bare = node.type is None
            is_exception = isinstance(node.type, ast.Name) and node.type.id == "Exception"
            if is_bare:
                fail(f"{label}:{node.lineno}: bare except:")
            elif is_exception:
                fail(f"{label}:{node.lineno}: except Exception (too broad)")
            if is_bare or is_exception:
                if len(node.body) == 0:
                    fail(f"{label}:{node.lineno}: except with empty body")
                elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    fail(f"{label}:{node.lineno}: except: pass (silent suppression)")
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Unconditional return before assertions
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Return) and stmt.value is not None:
                    for later in node.body[i + 1:]:
                        if isinstance(later, ast.Assert):
                            fail(f"{label}:{stmt.lineno}: unconditional return before assertion in {node.name}()")
                            break
                    break
            # time.sleep() in test functions
            if node.name.startswith("test_"):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        func = sub.func
                        if isinstance(func, ast.Attribute) and func.attr == "sleep":
                            if isinstance(func.value, ast.Name) and func.value.id == "time":
                                fail(f"{label}:{sub.lineno}: time.sleep() in test function {node.name}()")
            # print() in test functions
            if node.name.startswith("test_"):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        func = sub.func
                        if isinstance(func, ast.Name) and func.id == "print":
                            fail(f"{label}:{sub.lineno}: print() in test function {node.name}()")
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            # Catch pytest.skip(...), pytest.xfail(...), pytest.importorskip(...)
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr in ("skip", "xfail", "importorskip"):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "pytest":
                        fail(f"{label}:{node.lineno}: pytest.{attr}() call")
                # unittest.skipTest, self.skipTest
                if attr == "skipTest":
                    if isinstance(node.func.value, ast.Name):
                        fail(f"{label}:{node.lineno}: {node.func.value.id}.skipTest() call")
            self.generic_visit(node)

        def visit_FunctionDef_decorators(self, node: ast.FunctionDef) -> None:
            # Already checked in visit_FunctionDef; decorators are separate.
            pass

    # Walk for top-level calls (pytest.skip, etc.)
    Visitor().visit(tree)

    # Check decorators separately (they are not inside function bodies)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Attribute):
                    if dec.attr in ("skip", "xfail"):
                        if isinstance(dec.value, ast.Attribute) and dec.value.attr == "mark":
                            if isinstance(dec.value.value, ast.Name) and dec.value.value.id == "pytest":
                                fail(f"{label}:{dec.lineno}: @pytest.mark.{dec.attr} decorator on {node.name}()")
                    if dec.attr == "skip":
                        if isinstance(dec.value, ast.Name) and dec.value.id == "unittest":
                            fail(f"{label}:{dec.lineno}: @unittest.skip decorator on {node.name}()")


def _check_text(path: Path, source: str) -> None:
    label = path.name

    # Check only comment lines for prohibited annotations
    # (code patterns are handled by AST-based checks to avoid false positives from strings)
    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        # Only examine lines that are comments or have inline comments
        comment_part = ""
        hash_pos = stripped.find("#")
        if hash_pos >= 0:
            comment_part = stripped[hash_pos:]
        else:
            continue

        for pattern, desc in [
            (r'SKIP\b', "SKIP comment"),
            (r'KNOWN\s+DEFECT', "KNOWN DEFECT comment"),
            (r'KNOWN\s+ISSUE', "KNOWN ISSUE comment"),
        ]:
            if re.search(pattern, comment_part):
                fail(f"{label}:{lineno}: contains {desc}")
                break


def _check_module_level_execution(path: Path, tree: ast.AST) -> None:
    label = path.name
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            fname = None
            if isinstance(func, ast.Name):
                fname = func.id
            elif isinstance(func, ast.Attribute):
                fname = func.attr
            if fname in ("check", "raises", "raises_msg", "fail", "warn"):
                fail(f"{label}:{node.lineno}: import-time execution of {fname}() at module level")

        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Compare):
                left = node.test.left
                if isinstance(left, ast.Name) and left.id == "__name__":
                    continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    fname = None
                    if isinstance(func, ast.Name):
                        fname = func.id
                    elif isinstance(func, ast.Attribute):
                        fname = func.attr
                    if fname in ("check", "raises", "raises_msg"):
                        fail(f"{label}:{sub.lineno}: import-time execution in conditional at module level")
                        break


def _check_functions_have_asserts(path: Path, tree: ast.AST) -> None:
    label = path.name
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            has_assert = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assert):
                    has_assert = True
                    break
                if isinstance(sub, ast.Call):
                    func = sub.func
                    fname = None
                    if isinstance(func, ast.Name):
                        fname = func.id
                    elif isinstance(func, ast.Attribute):
                        fname = func.attr
                    if fname in ("check", "raises", "raises_msg", "pytest.fail"):
                        has_assert = True
                        break
            if not has_assert:
                fail(f"{label}:{node.lineno}: test function {node.name}() has no assertions")




def inspect_file(path: Path) -> None:
    try:
        source = path.read_text()
    except Exception as exc:
        fail(f"{path.name}: cannot read: {exc}")
        return

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        fail(f"{path.name}: syntax error: {exc}")
        return

    _check_ast(path, source, tree)
    _check_text(path, source)
    _check_module_level_execution(path, tree)
    _check_functions_have_asserts(path, tree)


SELF_TEST_PATTERNS: dict[str, str] = {
    "assert_true": "def test_x():\n    assert True\n",
    "assert_false": "def test_x():\n    assert False\n",
    "raises_exception": "def test_x():\n    raise Exception('bad')\n",
    "except_exception": "def test_x():\n    try:\n        pass\n    except Exception:\n        pass\n",
    "bare_except": "def test_x():\n    try:\n        pass\n    except:\n        pass\n",
    "pytest_skip": "import pytest\ndef test_x():\n    pytest.skip('nope')\n",
    "pytest_xfail": "import pytest\ndef test_x():\n    pytest.xfail('nope')\n",
    "importorskip": "def test_x():\n    pytest.importorskip('nonexistent')\n",
    "skip_comment": "# SKIP: known issue\ndef test_x():\n    assert 1 == 1\n",
    "known_defect": "# KNOWN DEFECT: will fix later\ndef test_x():\n    assert 1 == 1\n",
    "known_issue": "# KNOWN ISSUE #123\ndef test_x():\n    assert 1 == 1\n",
    "unconditional_return": "def test_x():\n    return True\n    assert False\n",
    "import_time_exec": "check('bad', True)\ndef test_x():\n    pass\n",
    "empty_test": "def test_x():\n    pass\n",
    "bare_except_empty": "def test_x():\n    try:\n        pass\n    except:\n        pass\n",
    "decorator_skip": "@pytest.mark.skip\ndef test_x():\n    assert 1\n",
    "decorator_xfail": "@pytest.mark.xfail\ndef test_x():\n    assert 1\n",
    "except_exception_empty": "def test_x():\n    try:\n        pass\n    except Exception:\n        pass\n",
    "time_sleep": "import time\ndef test_x():\n    time.sleep(1)\n    assert True\n",
    "print_in_test": "def test_x():\n    print('debug')\n    assert True\n",
}


def run_self_tests() -> None:
    global FAILED
    save_failed = FAILED

    print("--- self-tests ---")

    with tempfile.TemporaryDirectory(prefix="m2qt_") as td:
        tdir = Path(td)
        rejected = 0
        for name, content in SELF_TEST_PATTERNS.items():
            fp = tdir / f"test_{name}.py"
            fp.write_text(content)
            FAILED = 0
            print(f"  checking {name}...")
            inspect_file(fp)
            if FAILED > 0:
                rejected += 1
            else:
                print(f"  WARNING: pattern {name} NOT rejected")

        expected = len(SELF_TEST_PATTERNS)
        FAILED = save_failed
        if rejected == expected:
            print(f"  SELF-TEST PASS: all {rejected} patterns correctly rejected")
        else:
            print(f"  SELF-TEST FAIL: {rejected}/{expected} patterns rejected (expected all {expected})")
            sys.exit(1)


def main() -> int:
    global FAILED

    if "--self-test" in sys.argv:
        run_self_tests()
        return 0

    print("=== test quality inspection (verifier scope) ===")

    test_files: list[Path] = []
    for d in VERIFIER_TEST_DIRS:
        if d.is_dir():
            test_files.extend(sorted(d.glob("test_*.py")))
            test_files.extend(sorted(d.glob("conftest.py")))

    if not test_files:
        print("WARNING: No verifier test files found")
        return 1

    for fp in test_files:
        if fp.resolve() == SELF_FILE:
            continue
        inspect_file(fp)

    print(f"--- {FAILED} quality violation(s) ---")
    if FAILED:
        print("QUALITY GATE: FAILED")
        return 1
    print("QUALITY GATE: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
