"""Pytest configuration for m2_acceptance_v2 verifier tests.

Imports shared fixtures from tests/m2_verifier_support/.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add the tests directory to path for m2_verifier_support imports
_test_dir = str(Path(__file__).resolve().parent.parent)
if _test_dir not in sys.path:
    sys.path.insert(0, _test_dir)

# Also add python source
_py_dir = str(Path(__file__).resolve().parent.parent.parent / "python")
if _py_dir not in sys.path:
    sys.path.insert(0, _py_dir)

import pytest  # noqa: E402

# Register m2_verifier_support as a pytest plugin
pytest_plugins = ["m2_verifier_support"]
