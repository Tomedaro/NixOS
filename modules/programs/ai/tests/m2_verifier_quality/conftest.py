"""Self-tests for the verifier quality gate — conftest.

Ensures the verifier quality gate module is available.
"""
import sys
from pathlib import Path

_verifier_dir = Path(__file__).resolve().parent.parent.parent / "dev" / "m2_verifier"
sys.path.insert(0, str(_verifier_dir))
