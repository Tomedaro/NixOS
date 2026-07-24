#!/usr/bin/env bash
# M2 Public Acceptance Suite Runner
#
# Runs the public acceptance gate and test quality gate.
# Exit code reflects combined success/failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== M2 Public Acceptance Suite ==="
echo "Repo: $REPO_ROOT"
echo ""

# 1. Test quality gate
echo "--- Test Quality Gate ---"
python3 "$SCRIPT_DIR/m2_test_quality.py"
QUALITY_EXIT=$?
echo ""

# 2. Acceptance gate
echo "--- Acceptance Gate ---"
python3 "$SCRIPT_DIR/m2_acceptance_gate.py" "$@"
ACCEPT_EXIT=$?
echo ""

# Report combined status
if [ $QUALITY_EXIT -eq 0 ] && [ $ACCEPT_EXIT -eq 0 ]; then
    echo "=== ALL PASSED ==="
    exit 0
else
    if [ $QUALITY_EXIT -ne 0 ]; then
        echo "*** Quality gate FAILED ***"
    fi
    if [ $ACCEPT_EXIT -ne 0 ]; then
        echo "*** Acceptance gate FAILED ***"
    fi
    exit 1
fi
