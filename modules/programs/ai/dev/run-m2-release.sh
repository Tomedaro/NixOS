#!/usr/bin/env bash
# M2 Release Gate: Master release gate runner.
#
# Runs the release gate in --mode release.
# Exit 0 only when verifier_status=ready AND milestone_status=ready.
# Dependency probe is a hard failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERIFIER_DIR="$SCRIPT_DIR/m2_verifier"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$REPO_ROOT/python"

TIMEOUT=600

echo "=========================================="
echo " M2 Release Gate"
echo " Repo: $REPO_ROOT"
echo "=========================================="

# Dependency probe (hard failure)
echo ""
echo "--- Dependency Probe ---"
python3 -c 'import pytest, hypothesis, coverage, mutmut' || {
    echo "FATAL: Missing required dependencies."
    echo "Install: pip install pytest hypothesis coverage mutmut"
    exit 1
}
echo "Dependencies: OK"

# Run release gate
echo ""
echo "--- Release Gate (release mode) ---"
timeout "$TIMEOUT" python3 "$VERIFIER_DIR/release_gate.py" --mode release

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo " M2 Release Gate: PASSED"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo " M2 Release Gate: BLOCKED (exit $EXIT_CODE)"
    echo "=========================================="
fi
exit $EXIT_CODE
