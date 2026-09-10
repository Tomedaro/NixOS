"""Self-tests proving the quality gate rejects each prohibited pattern (Section 12).

Each test function creates a temp file containing one prohibited pattern,
runs inspect_file on it, and asserts the pattern was detected (FAILED > 0).

Uses generated strings (code-point construction) — no hardcoded prohibited
patterns in source that could trigger the quality gate on these files themselves.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_verifier_dir = Path(__file__).resolve().parent.parent.parent / "dev" / "m2_verifier"
sys.path.insert(0, str(_verifier_dir))

import test_quality as tq
from test_quality import inspect_file


def _fk() -> int:
    """Return current FAILED count from the test_quality module."""
    return tq.FAILED


def _mk(*codes: int) -> str:
    """Build a string from code points to avoid literal pattern matches."""
    return "".join(chr(c) for c in codes)


# Generated prohibited-pattern strings — no literal matches in source
_SKIP_STR = _mk(83, 75, 73, 80)
_KNOWN_DEFECT_STR = _mk(75, 78, 79, 87, 78, 32, 68, 69, 70, 69, 67, 84)
_KNOWN_ISSUE_STR = _mk(75, 78, 79, 87, 78, 32, 73, 83, 83, 85, 69)
_PSKIP_STR = _mk(112, 121, 116, 101, 115, 116, 46, 115, 107, 105, 112)
_PXFAIL_STR = _mk(112, 121, 116, 101, 115, 116, 46, 120, 102, 97, 105, 108)
_PIMPORT_STR = _mk(112, 121, 116, 101, 115, 116, 46, 105, 109, 112, 111, 114, 116, 111, 114, 115, 107, 105, 112)
_PMARK_SKIP_STR = _mk(64, 112, 121, 116, 101, 115, 116, 46, 109, 97, 114, 107, 46, 115, 107, 105, 112)
_PMARK_XFAIL_STR = _mk(64, 112, 121, 116, 101, 115, 116, 46, 109, 97, 114, 107, 46, 120, 102, 97, 105, 108)
def _temp_file(content: str) -> Path:
    fd, fname = tempfile.mkstemp(suffix=".py", prefix="m2qt_")
    import os
    os.write(fd, content.encode())
    os.close(fd)
    return Path(fname)


def _reset_failed() -> None:
    import test_quality as tq
    tq.FAILED = 0


# ---------------------------------------------------------------------------
# Rejection tests
# ---------------------------------------------------------------------------

def test_reject_assert_true() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    assert True\n")
    inspect_file(fp)
    assert _fk() > 0, "assert True was not rejected"
    fp.unlink()


def test_reject_assert_false() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    assert False\n")
    inspect_file(fp)
    assert _fk() > 0, "assert False was not rejected"
    fp.unlink()


def test_reject_raises_exception() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    raise Exception('bad')\n")
    inspect_file(fp)
    assert _fk() > 0, "raise Exception was not rejected"
    fp.unlink()


def test_reject_except_exception_pass() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    try:\n        pass\n    except Exception:\n        pass\n")
    inspect_file(fp)
    assert _fk() > 0, "except Exception: pass was not rejected"
    fp.unlink()


def test_reject_bare_except_pass() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    try:\n        pass\n    except:\n        pass\n")
    inspect_file(fp)
    assert _fk() > 0, "bare except: pass was not rejected"
    fp.unlink()


def test_reject_bare_except_empty() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    try:\n        pass\n    except:\n        pass\n")
    inspect_file(fp)
    assert _fk() > 0, "bare except empty was not rejected"
    fp.unlink()


def test_reject_except_exception_empty() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    try:\n        pass\n    except Exception:\n        pass\n")
    inspect_file(fp)
    assert _fk() > 0, "except Exception empty was not rejected"
    fp.unlink()


def test_reject_pytest_skip_call() -> None:
    _reset_failed()
    code = f"import pytest\ndef test_x():\n    {_PSKIP_STR}('nope')\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "pytest skip call was not rejected"
    fp.unlink()


def test_reject_pytest_xfail_call() -> None:
    _reset_failed()
    code = f"import pytest\ndef test_x():\n    {_PXFAIL_STR}('nope')\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "pytest xfail call was not rejected"
    fp.unlink()

def test_reject_conditional_import() -> None:
    _reset_failed()
    code = f"def test_x():\n    {_PIMPORT_STR}('nonexistent')\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "conditional import was not rejected"
    fp.unlink()


def test_reject_skip_decorator() -> None:
    _reset_failed()
    code = f"{_PMARK_SKIP_STR}\ndef test_x():\n    assert 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "skip decorator was not rejected"
    fp.unlink()


def test_reject_xfail_decorator() -> None:
    _reset_failed()
    code = f"{_PMARK_XFAIL_STR}\ndef test_x():\n    assert 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "xfail decorator was not rejected"
    fp.unlink()


def test_reject_skip_comment() -> None:
    _reset_failed()
    code = f"# {_SKIP_STR}: not ready\ndef test_x():\n    assert 1 == 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "skip comment was not rejected"
    fp.unlink()


def test_reject_known_defect_comment() -> None:
    _reset_failed()
    code = f"# {_KNOWN_DEFECT_STR}: fix later\ndef test_x():\n    assert 1 == 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "known defect comment was not rejected"
    fp.unlink()


def test_reject_known_issue_comment() -> None:
    _reset_failed()
    code = f"# {_KNOWN_ISSUE_STR} #1\ndef test_x():\n    assert 1 == 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() > 0, "known issue comment was not rejected"
    fp.unlink()


def test_reject_unconditional_return() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    return None\n    assert False\n")
    inspect_file(fp)
    assert _fk() > 0, "unconditional return was not rejected"
    fp.unlink()


def test_reject_import_time_execution() -> None:
    _reset_failed()
    fp = _temp_file("check('bad', True)\ndef test_x():\n    pass\n")
    inspect_file(fp)
    assert _fk() > 0, "import-time check() was not rejected"
    fp.unlink()


def test_reject_test_without_assert() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    pass\n")
    inspect_file(fp)
    assert _fk() > 0, "empty test function was not rejected"
    fp.unlink()


def test_reject_time_sleep() -> None:
    _reset_failed()
    fp = _temp_file("import time\ndef test_x():\n    time.sleep(1)\n    assert True\n")
    inspect_file(fp)
    assert _fk() > 0, "time.sleep was not rejected"
    fp.unlink()


def test_reject_print_in_test() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    print('debug')\n    assert True\n")
    inspect_file(fp)
    assert _fk() > 0, "print() in test was not rejected"
    fp.unlink()


# ---------------------------------------------------------------------------
# Allowance tests
# ---------------------------------------------------------------------------

def test_allow_valid_test() -> None:
    _reset_failed()
    fp = _temp_file("def test_x():\n    assert 1 + 1 == 2\n")
    inspect_file(fp)
    assert _fk() == 0, f"valid test was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_if_main_block() -> None:
    _reset_failed()
    fp = _temp_file("if __name__ == '__main__':\n    check('ok', True)\n")
    inspect_file(fp)
    assert _fk() == 0, f"if __main__ block was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_string_fixture_pytest_skip() -> None:
    """String literal containing 'pytest.skip' should not be rejected."""
    _reset_failed()
    code = "def test_x():\n    msg = 'see pytest.skip for details'\n    assert len(msg) > 0\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() == 0, f"string fixture for pytest.skip was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_string_fixture_importorskip() -> None:
    """String literal containing 'importorskip' should not be rejected."""
    _reset_failed()
    code = "def test_x():\n    doc = 'uses importorskip pattern'\n    assert 1\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() == 0, f"string fixture for importorskip was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_string_fixture_skip_comment() -> None:
    """String literal containing 'SKIP' (not in a comment) should not be rejected."""
    _reset_failed()
    code = "def test_x():\n    label = 'SKIP_THIS_TOKEN'\n    assert label\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() == 0, f"string fixture for SKIP was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_string_fixture_known_defect() -> None:
    """String literal containing 'KNOWN DEFECT' (not in a comment) should not be rejected."""
    _reset_failed()
    code = "def test_x():\n    msg = 'This is a KNOWN DEFECT tracker'\n    assert msg\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() == 0, f"string fixture for KNOWN DEFECT was incorrectly rejected ({_fk()} failures)"
    fp.unlink()


def test_allow_string_fixture_known_issue() -> None:
    """String literal containing 'KNOWN ISSUE' (not in a comment) should not be rejected."""
    _reset_failed()
    code = "def test_x():\n    note = 'KNOWN ISSUE #1'\n    assert note\n"
    fp = _temp_file(code)
    inspect_file(fp)
    assert _fk() == 0, f"string fixture for KNOWN ISSUE was incorrectly rejected ({_fk()} failures)"
    fp.unlink()
