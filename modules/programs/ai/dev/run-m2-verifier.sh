#!/usr/bin/env bash
# M2 Verifier: Full verifier suite runner.
#
# Runs all verifier components in order:
#   1. Hash production files
#   2. Dependency probe (hard failure if missing)
#   3. Manifest validation
#   4. Lock verification
#   5. Test quality gate
#   6. Quality canaries (V01-V19)
#   7. Acceptance run (baseline mode)
#   8. Semantic mutants (verifier-probe)
#   9. Stateful tests
#  10. Release gate (baseline mode)
#
# Strict timeout: 900s (15 minutes).
# Exit code reflects combined success/failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERIFIER_DIR="$SCRIPT_DIR/m2_verifier"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$REPO_ROOT/python"

TIMEOUT=900
START_TIME=$(date +%s)

fail() {
    echo "*** $1 ***"
    exit 1
}

echo "=========================================="
echo " M2 Verifier Suite"
echo " Repo: $REPO_ROOT"
echo " Timeout: ${TIMEOUT}s (15 minutes)"
echo "=========================================="

# 1. Hash production files
echo ""
echo "--- 1/10 Hash Production Files ---"
python3 "$VERIFIER_DIR/hash_production.py" || fail "hash_production failed"

# 2. Dependency probe (hard failure)
echo ""
echo "--- 2/10 Dependency Probe ---"
python3 -c 'import pytest, hypothesis, coverage, mutmut' || {
    echo "FATAL: Missing required dependencies."
    echo "Install: pip install pytest hypothesis coverage mutmut"
    fail "dependency probe failed"
}
echo "Dependencies: OK"

# 3. Manifest validation
echo ""
echo "--- 3/10 Manifest Validation ---"
python3 "$VERIFIER_DIR/validate_manifest.py" || fail "manifest validation failed"

# 4. Lock verification
echo ""
echo "--- 4/10 Lock Verification ---"
python3 "$VERIFIER_DIR/verify_lock.py" || fail "lock verification failed"

# 5. Test quality gate
echo ""
echo "--- 5/10 Test Quality Gate ---"
python3 "$VERIFIER_DIR/test_quality.py" || fail "test_quality failed"

# 6. Quality canaries
echo ""
echo "--- 6/10 Quality Canaries (V01-V19) ---"
python3 "$VERIFIER_DIR/run_quality_canaries.py" || fail "quality canaries failed"

# 7. Acceptance run (baseline)
echo ""
echo "--- 7/10 Acceptance Run (baseline) ---"
python3 "$VERIFIER_DIR/run_acceptance.py" --mode baseline || fail "acceptance baseline failed"

# 8. Semantic mutants
echo ""
echo "--- 8/10 Semantic Mutants (verifier-probe) ---"
python3 "$VERIFIER_DIR/run_semantic_mutants.py" --phase verifier-probe || fail "semantic mutants failed"

# 9. Stateful tests
echo ""
echo "--- 9/10 Stateful Tests ---"
python3 -m pytest "$REPO_ROOT/tests/m2_stateful_v2/" -q --no-header --tb=short \
    --timeout=120 2>/dev/null || \
    python3 -m pytest "$REPO_ROOT/tests/m2_stateful_v2/" -q --no-header --tb=short \
    || fail "stateful tests failed"

# 10. Release gate (baseline)
echo ""
echo "--- 10/10 Release Gate (baseline) ---"
python3 "$VERIFIER_DIR/release_gate.py" --mode baseline || fail "release gate failed"

# Check elapsed
ELAPSED=$(($(date +%s) - START_TIME))
if [ "$ELAPSED" -gt "$TIMEOUT" ]; then
    fail "TIMEOUT: ${ELAPSED}s exceeds ${TIMEOUT}s limit"
fi

echo ""
echo "=========================================="
echo " M2 Verifier: ALL PASSED (${ELAPSED}s)"
echo "=========================================="
exit 0
