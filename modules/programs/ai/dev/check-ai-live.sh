#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export GIT_PAGER=cat
export PAGER=cat
export NO_COLOR=1

AI_DIR="${AI_DIR:-/home/daniil/Sync/Perseverance.Gu/AI}"

PROCESS_ACTIONS=0
RUN_RECOVERY=0
RUN_TRIGGER=0
RUN_OUTCOMES=0

usage() {
  cat <<'USAGE'
Usage: modules/programs/ai/dev/check-ai-live.sh [options]

Default mode is inspect-only, except phone-bridge --once is run because it is passive and already safe.

Options:
  --process-actions   Run the installed action bridge with --once if found.
  --run-recovery      Run the installed recovery manager with --once if found.
  --run-trigger       Run the installed recovery trigger with --once if found.
  --run-outcomes      Run the installed intervention outcome reporter if found.
  --help              Show this help.

The mutating options are explicit on purpose. They may process real live queue/state.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --process-actions)
      PROCESS_ACTIONS=1
      ;;
    --run-recovery)
      RUN_RECOVERY=1
      ;;
    --run-trigger)
      RUN_TRIGGER=1
      ;;
    --run-outcomes)
      RUN_OUTCOMES=1
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

LOG="${AI_DEV_LOG:-/tmp/ai-check-ai-live-$(date +%Y%m%d-%H%M%S).txt}"
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

json_or_cat() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "missing: $path"
    return 0
  fi

  echo "--- $path ---"
  if command -v jq >/dev/null 2>&1; then
    jq . "$path" 2>/dev/null || cat "$path"
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool "$path" 2>/dev/null || cat "$path"
  else
    cat "$path"
  fi
}

status_md_or_missing() {
  local path="$1"
  if [ -f "$path" ]; then
    echo "--- $path ---"
    sed -n '1,160p' "$path"
  else
    echo "missing: $path"
  fi
}

find_units() {
  local pattern="$1"
  systemctl --user list-unit-files --all --no-legend 2>/dev/null \
    | awk '{print $1}' \
    | grep --color=never -Ei "$pattern" \
    | sort -u || true
}

unit_execstart() {
  local unit="$1"
  systemctl --user cat "$unit" --no-pager 2>/dev/null \
    | sed -n 's/^ExecStart=//p' \
    | tail -1
}

unit_exec_bin() {
  local unit="$1"
  local line
  line="$(unit_execstart "$unit")"
  if [ -z "$line" ]; then
    return 1
  fi
  printf '%s\n' "$line" | awk '{print $1}'
}

print_unit_group() {
  local title="$1"
  local pattern="$2"

  echo
  echo "===== $title unit candidates ====="

  mapfile -t units < <(find_units "$pattern")
  if [ "${#units[@]}" -eq 0 ]; then
    echo "none found"
    return 0
  fi

  printf '%s\n' "${units[@]}"

  for unit in "${units[@]}"; do
    echo
    echo "----- unit: $unit -----"
    systemctl --user status "$unit" --no-pager || true
    echo
    systemctl --user cat "$unit" --no-pager || true
  done
}

run_first_unit_once() {
  local title="$1"
  local pattern="$2"
  shift 2
  local args=("$@")

  echo
  echo "===== run $title ====="

  # Prefer executable service units over companion .path/.timer units.
  mapfile -t units < <(find_units "$pattern" | grep --color=never -E '\\.service$' || true)
  if [ "${#units[@]}" -eq 0 ]; then
    mapfile -t units < <(find_units "$pattern")
  fi
  if [ "${#units[@]}" -eq 0 ]; then
    echo "SKIP: no matching unit found"
    return 0
  fi

  local unit="${units[0]}"
  local bin
  bin="$(unit_exec_bin "$unit" || true)"

  echo "unit=$unit"
  echo "bin=$bin"

  if [ -z "$bin" ] || [ ! -x "$bin" ]; then
    echo "SKIP: executable not found"
    return 0
  fi

  "$bin" "${args[@]}"
}

list_queue() {
  local title="$1"
  local dir="$2"
  local depth="${3:-1}"

  echo
  echo "===== $title ====="
  if [ ! -d "$dir" ]; then
    echo "missing: $dir"
    return 0
  fi

  find "$dir" -maxdepth "$depth" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -40 || true
}

count_pending_json() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo 0
    return 0
  fi
  find "$dir" -maxdepth 1 -type f -name '*.json' | wc -l
}

echo "===== repo ====="
pwd

echo
echo "===== git status before live AI check ====="
git status --short

echo
echo "===== AI_DIR ====="
echo "$AI_DIR"

print_unit_group "phone bridge" 'phone.*bridge|phone-bridge'
print_unit_group "action bridge" 'action.*bridge|ai-action|action-bridge'
print_unit_group "recovery" 'recovery|recovery-manager|recovery-trigger'
print_unit_group "intervention outcomes" 'intervention|outcome'

list_queue "pending phone telemetry inbox" "$AI_DIR/inbox/from-phone/events" 1
list_queue "failed phone telemetry newest" "$AI_DIR/inbox/from-phone/failed" 3
list_queue "processed phone telemetry newest" "$AI_DIR/inbox/from-phone/processed" 3
list_queue "pending action inbox" "$AI_DIR/inbox/actions" 1
list_queue "failed actions newest" "$AI_DIR/inbox/actions-failed" 3
list_queue "processed actions newest" "$AI_DIR/inbox/actions-processed" 3

echo
echo "===== current materialized state ====="
json_or_cat "$AI_DIR/outbox/to-phone/interaction-state.json"
json_or_cat "$AI_DIR/outbox/to-phone/current-nudge.json"
json_or_cat "$AI_DIR/state/recovery/current.json"
json_or_cat "$AI_DIR/state/interventions/stats.json"

echo
echo "===== status markdown ====="
status_md_or_missing "$AI_DIR/state/recovery/status.md"
status_md_or_missing "$AI_DIR/state/interventions/status.md"
status_md_or_missing "$AI_DIR/state/recovery-trigger/status.md"

run_first_unit_once "phone bridge --once" 'phone.*bridge|phone-bridge' --once

echo
echo "===== explicit mutating checks ====="

pending_actions="$(count_pending_json "$AI_DIR/inbox/actions")"
echo "pending_actions=$pending_actions"

if [ "$PROCESS_ACTIONS" = "1" ]; then
  run_first_unit_once "action bridge --once" 'action.*bridge|ai-action|action-bridge' --once
else
  echo "SKIP action bridge processing; pass --process-actions to process live pending actions"
fi

if [ "$RUN_RECOVERY" = "1" ]; then
  run_first_unit_once "recovery manager --once" 'recovery.*manager|recovery-manager' --once
else
  echo "SKIP recovery manager run; pass --run-recovery to mutate live recovery state"
fi

if [ "$RUN_TRIGGER" = "1" ]; then
  run_first_unit_once "recovery trigger --once" 'recovery.*trigger|recovery-trigger' --once
else
  echo "SKIP recovery trigger run; pass --run-trigger to possibly write live nudges"
fi

if [ "$RUN_OUTCOMES" = "1" ]; then
  run_first_unit_once "intervention outcomes reporter" 'intervention.*outcome|outcome.*report' --write
else
  echo "SKIP intervention outcome reporter write; pass --run-outcomes to write live outcome state"
fi

echo
echo "===== live queues after check ====="
list_queue "pending phone telemetry inbox after" "$AI_DIR/inbox/from-phone/events" 1
list_queue "pending action inbox after" "$AI_DIR/inbox/actions" 1

echo
echo "===== git status after live AI check ====="
git status --short
