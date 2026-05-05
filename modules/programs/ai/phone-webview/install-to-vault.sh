#!/usr/bin/env bash
set -euo pipefail

VAULT_ROOT="${VAULT_ROOT:-/home/daniil/Sync/Perseverance.Gu}"
MODE="${1:---check}"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

SRC_HTML="$SCRIPT_DIR/ai-pi-gruvbox-card-v1.html"
SRC_XML="$SCRIPT_DIR/import/PerseveranceAI-v3.prj.xml"
SRC_README="$SCRIPT_DIR/README.vault-tasker.md"

DST_HTML="$VAULT_ROOT/AI/state/phone/ai-pi-gruvbox-card-v1.html"
DST_XML="$VAULT_ROOT/AI/tasker/import/PerseveranceAI-v3.prj.xml"
DST_README="$VAULT_ROOT/AI/tasker/README.md"

case "$MODE" in
  --check|--install) ;;
  *)
    echo "usage: $0 [--check|--install]" >&2
    exit 2
    ;;
esac

require_file() {
  if [ ! -f "$1" ]; then
    echo "MISSING $1"
    return 1
  fi
  echo "OK $1"
}

check_markers() {
  local ok=0


  grep -q 'function baseNudgeActionPayload' "$SRC_HTML" || {
    echo "BAD missing baseNudgeActionPayload in repo HTML"
    ok=1
  }

  grep -q 'intervention_id: nudgeInterventionId(n)' "$SRC_HTML" || {
    echo "BAD missing intervention_id propagation in repo HTML"
    ok=1
  }

  grep -q 'launch_task: launchTask' "$SRC_HTML" || {
    echo "BAD missing launch_task propagation in repo HTML"
    ok=1
  }

  grep -q 'writeAction("start_recovery_target"' "$SRC_HTML" || {
    echo "BAD missing start_recovery_target writer in repo HTML"
    ok=1
  }

  grep -q 'opened_ankidroid' "$SRC_XML" || {
    echo "BAD missing opened_ankidroid profile/export marker in repo XML"
    ok=1
  }

  grep -q 'closed_ankidroid' "$SRC_XML" || {
    echo "BAD missing closed_ankidroid profile/export marker in repo XML"
    ok=1
  }

  return "$ok"
}

check_same() {
  local src="$1"
  local dst="$2"

  if [ ! -f "$dst" ]; then
    echo "DRIFT missing $dst"
    return 1
  fi

  if cmp -s "$src" "$dst"; then
    echo "OK synced $dst"
    return 0
  fi

  echo "DRIFT differs $dst"
  return 1
}

install_file() {
  local src="$1"
  local dst="$2"
  local stamp

  stamp="$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$(dirname -- "$dst")"

  if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp -f -- "$dst" "$dst.bak-$stamp"
    echo "backup $dst.bak-$stamp"
  fi

  cp -f -- "$src" "$dst"
  echo "installed $dst"
}

echo "===== source files ====="
require_file "$SRC_HTML"
require_file "$SRC_XML"
require_file "$SRC_README"

echo
echo "===== marker checks ====="

  if grep -qE 'DEBUG_WRITES|writeDebug|webview-start-recovery-debug|launch_task_requested' "$SRC_HTML"; then
    echo "BAD repo HTML still contains debug write surface"
    return 1
  fi
check_markers

if [ "$MODE" = "--install" ]; then
  echo
  echo "===== install to vault ====="
  install_file "$SRC_HTML" "$DST_HTML"
  install_file "$SRC_XML" "$DST_XML"
  install_file "$SRC_README" "$DST_README"
fi

echo
echo "===== drift check ====="
failed=0
check_same "$SRC_HTML" "$DST_HTML" || failed=1
check_same "$SRC_XML" "$DST_XML" || failed=1
check_same "$SRC_README" "$DST_README" || failed=1

if [ "$failed" -ne 0 ]; then
  echo "RESULT drift_or_missing"
  exit 1
fi

echo "RESULT ok"
