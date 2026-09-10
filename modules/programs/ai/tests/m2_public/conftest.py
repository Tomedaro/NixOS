import sys
from pathlib import Path

# Add the tests directory to path so we can import m2_support
_test_dir = str(Path(__file__).resolve().parent.parent)
if _test_dir not in sys.path:
    sys.path.insert(0, _test_dir)

# Also add python source
_py_dir = str(Path(__file__).resolve().parent.parent.parent / "python")
if _py_dir not in sys.path:
    sys.path.insert(0, _py_dir)

import pytest

# Register m2_support as a plugin
pytest_plugins = ["m2_support"]
