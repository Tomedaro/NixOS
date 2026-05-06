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
VERBOSE=0

usage() {
  cat <<'USAGE'
Usage: modules/programs/ai/dev/audit-ai-project.sh [options]

Default mode is compact and suitable before push.

Options:
  --verbose, -v   Show full source tree, allowed legacy-reference hits, and longer state files.
  --help, -h      Show this help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --verbose|-v)
      VERBOSE=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

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

count_lines() {
  if [ -n "${1:-}" ]; then
    printf '%s\n' "$1" | wc -l | tr -d ' '
  else
    echo 0
  fi
}

list_queue() {
  local title="$1"
  local dir="$2"
  local depth="${3:-3}"
  local limit="${4:-20}"

  section "$title"
  if [ ! -d "$dir" ]; then
    echo "missing: $dir"
    return 0
  fi

  find "$dir" -maxdepth "$depth" -type f -printf '%T@ %p\n' 2>/dev/null \
    | sort -n \
    | tail -n "$limit" || true
}

report_malformed_processed_phone_telemetry() {
  local dir="$AI_DIR/inbox/from-phone/processed"
  local malformed_token="%"
  malformed_token="${malformed_token}ai_event_epoch"

  section "malformed processed phone telemetry"
  if [ ! -d "$dir" ]; then
    echo "missing: $dir"
    return 0
  fi

  local hits
  hits="$(find "$dir" -type f -name "*${malformed_token}*" -printf '%T@ %p\n' 2>/dev/null | sort -n || true)"
  if [ -z "$hits" ]; then
    echo "none"
    return 0
  fi

  echo "$hits"
  echo
  echo "WARN: malformed phone telemetry remains in processed; delete or move it to failed."
}

status_md_summary() {
  local path="$1"
  local lines="${2:-36}"

  echo "--- $path ---"
  if [ -f "$path" ]; then
    sed -n "1,${lines}p" "$path"
  else
    echo "missing"
  fi
}

compact_json_state() {
  section "compact materialized state"

  if ! command -v jq >/dev/null 2>&1; then
    echo "jq not found; falling back to markdown/state excerpts"
    return 0
  fi

  local interaction="$AI_DIR/outbox/to-phone/interaction-state.json"
  local recovery="$AI_DIR/state/recovery/current.json"
  local stats="$AI_DIR/state/interventions/stats.json"

  if [ -f "$interaction" ]; then
    jq -r '
      "interaction_state updated_at=\(.updated_at // "unknown") active_nudge=\(.active_nudge.status // "none") nudge_id=\(.active_nudge.nudge_id // "none") active_question=\(if .active_question == null then "none" else (.active_question.status // "present") end)"
    ' "$interaction" 2>/dev/null || echo "interaction_state unreadable"
  else
    echo "interaction_state missing"
  fi

  if [ -f "$recovery" ]; then
    jq -r '
      "recovery status=\(.status // "unknown") target=\(.target.target_id // "unknown") updated_at=\(.updated_at // "unknown")"
    ' "$recovery" 2>/dev/null || echo "recovery state unreadable"
  else
    echo "recovery state missing"
  fi

  if [ -f "$stats" ]; then
    jq -r '
      "interventions total=\(.total // 0) shown=\(.shown_count // 0) acted=\(.acted_count // 0) success=\(.success_count // 0)"
    ' "$stats" 2>/dev/null || echo "intervention stats unreadable"
  else
    echo "intervention stats missing"
  fi
}

section "repo"
pwd
git status --short

section "recent commits"
if [ "$VERBOSE" -eq 1 ]; then
  git log --oneline -12
else
  git log --oneline -5
fi

section "python compile all AI scripts/tests"
nix shell nixpkgs#python3 -c python3 -m compileall -q modules/programs/ai

section "shell syntax for dev scripts"
while IFS= read -r script; do
  echo "$script"
  bash -n "$script"
done < <(find modules/programs/ai/dev -maxdepth 1 -type f -name '*.sh' | sort)

section "source tree overview"
source_files="$(
  find modules/programs/ai -maxdepth 3 -type f \
    | sed 's#^\./##' \
    | sort \
    | grep -Ev '(__pycache__|\.pyc)$' || true
)"
echo "source_files=$(count_lines "$source_files")"
find modules/programs/ai -mindepth 1 -maxdepth 1 -type d | sort
if [ "$VERBOSE" -eq 1 ]; then
  echo
  echo "$source_files" | sed -n '1,260p'
else
  echo "use --verbose to show the full file list"
fi

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
allowed_reference_hits="$(
  find modules/programs/ai -type f \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 \
    | xargs -0 grep -nE \
        'Perseverance_AI_Phone_Interaction_v[12]|ai-pi-material-card|tasker-interaction-client-v2|%ai_event_epoch|webview-start-recovery-debug|launch_task_requested|DEBUG_WRITES|writeDebug|bak-debug|bak-snooze|bak-start' \
        || true
)"

if [ -z "$allowed_reference_hits" ]; then
  echo "none"
elif [ "$VERBOSE" -eq 1 ]; then
  echo "$allowed_reference_hits"
else
  echo "reference_lines=$(count_lines "$allowed_reference_hits")"
  echo "use --verbose to show allowed docs/tests/audit references"
fi

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

list_queue "pending phone telemetry inbox" "$AI_DIR/inbox/from-phone/events" 1 40
list_queue "failed phone telemetry newest" "$AI_DIR/inbox/from-phone/failed" 3 12
list_queue "processed phone telemetry newest" "$AI_DIR/inbox/from-phone/processed" 3 12
report_malformed_processed_phone_telemetry
list_queue "pending action inbox" "$AI_DIR/inbox/actions" 1 40
list_queue "failed actions newest" "$AI_DIR/inbox/actions-failed" 3 12
list_queue "processed actions newest" "$AI_DIR/inbox/actions-processed" 3 12

if [ "$VERBOSE" -eq 1 ]; then
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
else
  compact_json_state

  section "status markdown summary"
  status_md_summary "$AI_DIR/state/recovery/status.md" 36
  status_md_summary "$AI_DIR/state/interventions/status.md" 36
  status_md_summary "$AI_DIR/state/recovery-trigger/status.md" 36
fi

section "systemd user AI units"
systemctl --user list-units --all 'ai-*' 'phone-*' --no-pager || true
systemctl --user list-timers --all 'ai-*' 'phone-*' --no-pager || true

section "dev scripts executable"
test -x modules/programs/ai/dev/run-smoke.sh
test -x modules/programs/ai/dev/check-ai-live.sh
test -x modules/programs/ai/dev/rebuild-default.sh
echo "OK dev scripts executable"

section "audit complete"
echo "RESULT ok"
