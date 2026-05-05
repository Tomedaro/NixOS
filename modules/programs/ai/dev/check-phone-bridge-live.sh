#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export GIT_PAGER=cat
export PAGER=cat
export NO_COLOR=1

AI_DIR="${AI_DIR:-/home/daniil/Sync/Perseverance.Gu/AI}"
RAW_EVENTS_DIR="$AI_DIR/inbox/from-phone/events"
FAILED_DIR="$AI_DIR/inbox/from-phone/failed"
PROCESSED_DIR="$AI_DIR/inbox/from-phone/processed"

LOG="${AI_DEV_LOG:-/tmp/ai-check-phone-bridge-live-$(date +%Y%m%d-%H%M%S).txt}"
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
echo "===== git status before live phone bridge check ====="
git status --short

echo
echo "===== phone bridge status before --once ====="
systemctl --user status phone-bridge.service --no-pager || true

echo
echo "===== current phone bridge unit ====="
systemctl --user cat phone-bridge.service --no-pager

BIN="$(systemctl --user cat phone-bridge.service --no-pager \
  | sed -n 's/^ExecStart=\(.*phone-bridge\)$/\1/p' \
  | tail -1)"

echo
echo "===== installed phone bridge wrapper ====="
echo "BIN=$BIN"
test -n "$BIN"
test -x "$BIN"
readlink -f "$BIN" || true

echo
echo "===== pending raw phone files before --once ====="
find "$RAW_EVENTS_DIR" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -20 || true

echo
echo "===== run live phone bridge --once ====="
"$BIN" --once

echo
echo "===== pending raw phone files after --once ====="
find "$RAW_EVENTS_DIR" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -20 || true

echo
echo "===== newest failed phone files ====="
find "$FAILED_DIR" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -20 || true

echo
echo "===== newest processed phone files ====="
find "$PROCESSED_DIR" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -30 || true

echo
echo "===== live store once marker ====="
grep --color=never -R "def run_once" /nix/store/*phone_bridge.py /nix/store/*phone-bridge* 2>/dev/null | tail -20 || true

echo
echo "===== phone bridge status after --once ====="
systemctl --user status phone-bridge.service --no-pager || true

echo
echo "===== git status after live phone bridge check ====="
git status --short
