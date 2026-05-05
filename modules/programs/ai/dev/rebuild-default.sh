#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

export GIT_PAGER=cat
export PAGER=cat
export NO_COLOR=1

ALLOW_DIRTY=0
for arg in "$@"; do
  case "$arg" in
    --allow-dirty)
      ALLOW_DIRTY=1
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--allow-dirty]" >&2
      exit 2
      ;;
  esac
done

LOG="${AI_DEV_LOG:-/tmp/ai-rebuild-default-$(date +%Y%m%d-%H%M%S).txt}"
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
echo "===== git status before rebuild ====="
git status --short

if [ "$ALLOW_DIRTY" != "1" ] && [ -n "$(git status --short)" ]; then
  echo
  echo "Refusing to rebuild from a dirty tree."
  echo "Commit changes first, or rerun with --allow-dirty for an explicit development rebuild."
  exit 1
fi

echo
echo "===== available flake nixos configurations ====="
nix eval --json "$REPO_ROOT#nixosConfigurations" --apply 'builtins.attrNames' || true

echo
echo "===== rebuild Default ====="
sudo nixos-rebuild switch --flake "$REPO_ROOT#Default"

echo
echo "===== restart user AI services touched by recent workflow ====="
if systemctl --user list-unit-files phone-bridge.service >/dev/null 2>&1; then
  systemctl --user restart phone-bridge.service
fi

echo
echo "===== phone bridge status ====="
systemctl --user status phone-bridge.service --no-pager || true

echo
echo "===== git status after rebuild ====="
git status --short
