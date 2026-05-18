#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"
MODE="worktree"

if [ "${1:-}" = "--staged" ]; then
  MODE="staged"
fi

RAW_DIFF="$(mktemp)"
CHECK_DIFF="$(mktemp)"
trap 'rm -f "$RAW_DIFF" "$CHECK_DIFF"' EXIT

if [ "$MODE" = "staged" ]; then
  git diff --cached -- "$AI_DIR" > "$RAW_DIFF"
  echo "[check] staged AI diff whitespace"
  git diff --cached --check -- "$AI_DIR"
else
  git diff -- "$AI_DIR" > "$RAW_DIFF"
  echo "[check] worktree AI diff whitespace"
  git diff --check -- "$AI_DIR"
fi

if [ ! -s "$RAW_DIFF" ]; then
  echo "[info] no AI project diff found"
  exit 0
fi

# Avoid self-triggering on checker scripts' own pattern definitions.
awk '
  /^diff --git / {
    skip = ($0 ~ /modules\/programs\/ai\/dev\/llm\/check-llm-patch\.sh/ || $0 ~ /modules\/programs\/ai\/dev\/llm\/grep-known-typos\.sh/)
  }
  !skip { print }
' "$RAW_DIFF" > "$CHECK_DIFF"

echo
echo "[info] changed AI files:"
if [ "$MODE" = "staged" ]; then
  git diff --cached --name-only -- "$AI_DIR"
else
  git diff --name-only -- "$AI_DIR"
fi

echo
echo "[check] dangerous shell patterns"

DANGEROUS_PATTERN='rm -rf|curl .*\| *sh|wget .*\| *sh|chmod -R 777|sudo |eval \$|dd if=|mkfs\.|: *\(\) *\{ *: *\| *:'

if grep -nE "$DANGEROUS_PATTERN" "$CHECK_DIFF"; then
  echo
  echo "[fail] dangerous-looking command pattern found in AI diff"
  exit 1
fi

echo "[ok] no dangerous shell patterns found"

echo
echo "[check] workflow boundary drift"

FOUND=0

BOUNDARY_PATTERNS=(
  'ChatGPT memory is the source of truth|Project memory is canonical|custom GPT remembers prior chats'
  'LLM may apply|agent may commit|automatically commit|auto-commit|autocommit'
  'AI-owned commitment|LLM-owned commitment|agent-owned commitment'
  'roadmap item is current|planned feature is implemented|implemented future work'
)

for pattern in "${BOUNDARY_PATTERNS[@]}"; do
  if grep -nE "$pattern" "$CHECK_DIFF"; then
    FOUND=1
  fi
done

if [ "$FOUND" -ne 0 ]; then
  echo
  echo "[fail] likely workflow boundary drift found in AI diff"
  exit 1
fi

echo "[ok] no obvious workflow boundary drift found"
