#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export GIT_PAGER=cat
export PAGER=cat
export NO_COLOR=1
PYTHON_LIB="$REPO_ROOT/modules/programs/ai/python"
export PYTHONPATH="$PYTHON_LIB${PYTHONPATH:+:$PYTHONPATH}"

LOG="${AI_DEV_LOG:-/tmp/ai-run-smoke-$(date +%Y%m%d-%H%M%S).txt}"
mkdir -p "$(dirname "$LOG")"

finish() {
  status=$?
  echo
  echo "===== command exit status ====="
  echo "$status"
  if command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "$LOG" || true
    echo
    echo "===== copied full output to clipboard ====="
  else
    echo
    echo "===== wl-copy not found; output not copied ====="
  fi
  echo "$LOG"
  exit "$status"
}

exec > >(tee "$LOG") 2>&1
trap finish EXIT

echo "===== repo ====="
pwd

echo
echo "===== git status before smoke ====="
git status --short

echo
echo "===== python compile all AI scripts/tests ====="
mapfile -t py_files < <(
  find modules/programs/ai \
    -path '*/__pycache__' -prune -o \
    -name '*.py' -type f -print | sort
)

if [ "${#py_files[@]}" -eq 0 ]; then
  echo "No Python files found"
  exit 1
fi

nix shell nixpkgs#python3 -c python3 -m py_compile "${py_files[@]}"

tests=(
  modules/programs/ai/tests/phone_bridge_smoke.py
  modules/programs/ai/tests/action_bridge_smoke.py
  modules/programs/ai/tests/agent_context_smoke.py
  modules/programs/ai/tests/proposal_gate_smoke.py
  modules/programs/ai/tests/recovery_proposals_smoke.py
  modules/programs/ai/tests/recovery_smoke.py
  modules/programs/ai/tests/interventions_smoke.py
  modules/programs/ai/tests/intervention_outcomes_smoke.py
  modules/programs/ai/tests/intervention_outcomes_reporter_smoke.py
)

echo
echo "===== smoke tests ====="
for test_file in "${tests[@]}"; do
  echo
  echo "===== $test_file ====="
  test -f "$test_file"
  nix shell nixpkgs#python3 -c python3 "$test_file"
done

echo
echo "===== git status after smoke ====="
git status --short
