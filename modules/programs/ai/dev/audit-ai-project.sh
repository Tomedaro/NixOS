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

AI_DIR="${AI_DIR:-/home/daniil/Sync/Perseverance.Gu/AI}"
LOG="${AI_DEV_LOG:-/tmp/ai-project-audit-$(date +%Y%m%d-%H%M%S).txt}"
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

section() {
  echo
  echo "===== $* ====="
}

section "repo"
pwd
git status --short

section "recent commits"
git log --oneline -12

section "python compile all AI scripts/tests"
nix shell nixpkgs#python3 -c python3 -m compileall -q modules/programs/ai

section "shell syntax for dev scripts"
while IFS= read -r script; do
  echo "$script"
  bash -n "$script"
done < <(find modules/programs/ai/dev -maxdepth 1 -type f -name '*.sh' | sort)

section "source tree overview"
find modules/programs/ai -maxdepth 3 -type f \
  | sed 's#^\./##' \
  | sort \
  | grep -Ev '(__pycache__|\.pyc)$' \
  | sed -n '1,260p'

section "core runtime files"
for path in \
  modules/programs/ai/phone-bridge/phone_bridge.py \
  modules/programs/ai/phone-webview/ai-pi-gruvbox-card-v1.html \
  modules/programs/ai/phone-webview/import/PerseveranceAI-v3.prj.xml \
  modules/programs/ai/ARCHITECTURE.md
do
  if [ -e "$path" ]; then
    wc -c "$path"
  else
    echo "MISSING $path"
  fi
done

section "known legacy or malformed references"
find modules/programs/ai -type f \
  ! -path '*/__pycache__/*' \
  ! -name '*.pyc' \
  -print0 \
  | xargs -0 grep -nE \
      'Perseverance_AI_Phone_Interaction_v[12]|ai-pi-material-card|tasker-interaction-client-v2|%ai_event_epoch|webview-start-recovery-debug|launch_task_requested|DEBUG_WRITES|writeDebug|bak-debug|bak-snooze|bak-start' \
      || true


section "legacy guard"

legacy_hits="$(
  grep -RIn --color=never -E \
    'Perseverance_AI_Phone_Interaction_v[12]|ai-pi-material-card|tasker-interaction-client-v2|bak-debug|bak-snooze|bak-start|webview-start-recovery-debug|launch_task_requested|DEBUG_WRITES|writeDebug|default\.nix\.inline-backup' \
    modules/programs/ai \
    | grep -v 'dev/audit-ai-project.sh' \
    | grep -v 'ARCHITECTURE.md' \
    | grep -v 'README.md' \
    | grep -v 'phone-webview/install-to-vault.sh' \
    || true
)"

if [ -n "$legacy_hits" ]; then
  echo "$legacy_hits"
  echo
  echo "ERROR: legacy implementation references found outside allowed docs/audit files."
  exit 1
fi

malformed_hits="$(
  grep -RIn --color=never '%ai_event_epoch' modules/programs/ai \
    | grep -v 'tests/phone_bridge_smoke.py' \
    | grep -v 'dev/audit-ai-project.sh' \
    | grep -v 'ARCHITECTURE.md' \
    || true
)"

if [ -n "$malformed_hits" ]; then
  echo "$malformed_hits"
  echo
  echo "ERROR: unexpanded Tasker variable reference found outside allowed docs/tests/audit files."
  exit 1
fi

echo "OK legacy guard"

section "queue directories"
for dir in \
  "$AI_DIR/inbox/from-phone/events" \
  "$AI_DIR/inbox/from-phone/failed" \
  "$AI_DIR/inbox/from-phone/processed" \
  "$AI_DIR/inbox/actions" \
  "$AI_DIR/inbox/actions-failed" \
  "$AI_DIR/inbox/actions-processed"
do
  echo "--- $dir ---"
  if [ -d "$dir" ]; then
    find "$dir" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 20 || true
  else
    echo "missing"
  fi
done

section "materialized state summary"
for path in \
  "$AI_DIR/outbox/to-phone/interaction-state.json" \
  "$AI_DIR/outbox/to-phone/current-nudge.json" \
  "$AI_DIR/state/recovery/current.json" \
  "$AI_DIR/state/interventions/stats.json" \
  "$AI_DIR/state/recovery/status.md" \
  "$AI_DIR/state/interventions/status.md" \
  "$AI_DIR/state/recovery-trigger/status.md"
do
  echo "--- $path ---"
  if [ -f "$path" ]; then
    sed -n '1,220p' "$path"
  else
    echo "missing"
  fi
done

section "systemd user AI units"
systemctl --user list-units --all 'ai-*' 'phone-*' --no-pager || true
systemctl --user list-timers --all 'ai-*' 'phone-*' --no-pager || true

section "dev smoke script exists"
test -x modules/programs/ai/dev/run-smoke.sh
test -x modules/programs/ai/dev/check-ai-live.sh
test -x modules/programs/ai/dev/rebuild-default.sh

section "audit complete"
echo "RESULT ok"
