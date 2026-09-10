"""Stateful v2 tests — conftest.

Ensures hypothesis and kernel modules are available.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "python"))
