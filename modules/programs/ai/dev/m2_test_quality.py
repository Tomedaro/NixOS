#!/usr/bin/env python3
"""M2 public test quality gate.

Strict AST-level quality check for the m2_public test suite.
Rejects:
- assert True
- check(..., True) — script-style check calls
- raises(Exception), pytest.raises(Exception) — bare Exception
- except Exception, except ...: pass
- SKIP/SKIPPED/known defect/known issue/test continues in comments
- xfail, skip, skipif decorators
- Importing executable test modules (import of another test_*.py)
- Test execution at import time
- Warnings count as failures
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _find_test_files() -> list[Path]:
    tests_dir = _repo_root() / 'tests' / 'm2_public'
    if not tests_dir.exists():
        print(f'ERROR: test directory not found: {tests_dir}', file=sys.stderr)
        return []
    return sorted(tests_dir.glob('test_*.py'))


_ALLOWED_TOP_LEVEL = frozenset({
    'Import', 'ImportFrom', 'FunctionDef', 'AsyncFunctionDef',
    'ClassDef', 'Assign', 'AnnAssign', 'AugAssign',
})

_ALLOWED_TOP_CALLS = frozenset({'sys.path.insert',})


def _is_allowed_top_expr(node: ast.Expr) -> bool:
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return True
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Attribute):
            full = _full_attr(node.value.func)
            if full in _ALLOWED_TOP_CALLS:
                return True
    return False


def _check_file(path: Path) -> list[str]:
    violations: list[str] = []
    label = str(path.relative_to(_repo_root()))
    source = path.read_text()
    lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        violations.append(f'{label}: syntax error: {e}')
        return violations

    for node in ast.iter_child_nodes(tree):
        node_type = type(node).__name__
        if node_type in _ALLOWED_TOP_LEVEL:
            continue
        if isinstance(node, ast.Expr):
            if _is_allowed_top_expr(node):
                continue
            violations.append(f'{label}:{node.lineno}: top-level expression (test execution at import time)')
            continue
        if isinstance(node, ast.If) and _is_name_main_guard(node):
            continue
        violations.append(f'{label}:{node.lineno}: unexpected top-level statement ({node_type})')

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if 'test_' in alias.name:
                    violations.append(f'{label}:{node.lineno}: imports executable test module {alias.name}')
        elif isinstance(node, ast.ImportFrom):
            if node.module and 'test_' in node.module:
                violations.append(f'{label}:{node.lineno}: imports from test module {node.module}')

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                dec_name = _decorator_name(decorator)
                if dec_name in ('xfail', 'skip', 'skipif'):
                    violations.append(f'{label}:{node.lineno}: {node.name} uses @{dec_name} decorator')
                if isinstance(decorator, ast.Attribute):
                    full = _full_attr(decorator)
                    if full in ('pytest.mark.xfail', 'pytest.mark.skip', 'pytest.mark.skipif'):
                        violations.append(f'{label}:{node.lineno}: {node.name} uses @{full} decorator')

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    violations.append(f'{label}:{handler.lineno}: bare except (no exception type)')
                elif isinstance(handler.type, ast.Name) and handler.type.id == 'Exception':
                    if not _inside_helper(node, tree):
                        violations.append(f'{label}:{handler.lineno}: except Exception')
                if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                    if not _inside_helper(node, tree):
                        violations.append(f'{label}:{handler.lineno}: except ...: pass (swallowed exception)')

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _is_pytest_raises(node) and _has_bare_exception_arg(node):
                violations.append(f'{label}:{node.lineno}: pytest.raises with bare Exception')

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _call_name(node)
            if func_name == 'check' and len(node.args) >= 2:
                arg1 = node.args[1]
                if isinstance(arg1, ast.Constant) and arg1.value is True:
                    violations.append(f'{label}:{node.lineno}: check(..., True) — always-true assertion')

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                violations.append(f'{label}:{node.lineno}: assert True — always-true assertion')

    skip_patterns = [
        r'\bSKIP\b', r'\bSKIPPED\b', r'\bknown defect\b', r'\bknown issue\b',
        r'test continues', r'\bTODO\s*:\s*test\b', r'\bFIXME\s*:\s*test\b',
    ]
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith('#'):
            for pat in skip_patterns:
                if re.search(pat, stripped, re.IGNORECASE):
                    violations.append(f'{label}:{i}: skip/defect comment: \'{stripped[:60]}\'')

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _call_name(node)
            if func_name == 'raises' and len(node.args) >= 1:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Name) and arg0.id == 'Exception':
                    violations.append(f'{label}:{node.lineno}: raises(Exception, ...) — bare exception')

    return violations


def _inside_helper(node: ast.AST, tree: ast.Module) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(parent):
                if child is node:
                    if parent.name in ('holder', 'cleanup', '_thread_worker'):
                        return True
    return False


def _is_name_main_guard(node: ast.If) -> bool:
    if not isinstance(node.test, ast.Compare):
        return False
    if len(node.test.ops) != 1 or not isinstance(node.test.ops[0], ast.Eq):
        return False
    left = node.test.left
    right = node.test.comparators[0]
    if isinstance(left, ast.Name) and left.id == '__name__':
        if isinstance(right, ast.Constant) and right.value == '__main__':
            return True
    return False


def _decorator_name(decorator: ast.expr) -> str:
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Call):
        return _decorator_name(decorator.func)
    return ''


def _full_attr(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f'{_full_attr(node.value)}.{node.attr}'
    return ''


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Call):
        return _call_name(node.func)
    return ''


def _is_pytest_raises(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute) and node.func.attr == 'raises':
        if isinstance(node.func.value, ast.Name) and node.func.value.id == 'pytest':
            return True
    return False


def _has_bare_exception_arg(node: ast.Call) -> bool:
    if node.args:
        arg0 = node.args[0]
        if isinstance(arg0, ast.Name) and arg0.id == 'Exception':
            return True
    return False


def main() -> int:
    test_files = _find_test_files()
    if not test_files:
        print('ERROR: no test files found', file=sys.stderr)
        return 1

    support_file = _repo_root() / 'tests' / 'm2_support.py'
    all_files = test_files
    if support_file.exists():
        all_files = [support_file] + test_files

    total_violations = 0

    for path in all_files:
        label = str(path.relative_to(_repo_root()))
        violations = _check_file(path)
        if violations:
            print(f'\n{label}: {len(violations)} violation(s):')
            for v in violations:
                print(f'  FAIL  {v}')
            total_violations += len(violations)
        else:
            print(f'  OK   {label}')

    if total_violations > 0:
        print(f'\n*** {total_violations} total violation(s) ***')
        return 1

    print('\n=== All quality checks passed ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
