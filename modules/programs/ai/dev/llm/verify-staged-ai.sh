#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"

if git diff --cached --quiet -- "$AI_DIR"; then
  echo "[error] no staged AI project changes"
  exit 1
fi

echo "[check] staged AI diff summary"
git diff --cached --stat -- "$AI_DIR"

echo
echo "[check] staged AI diff whitespace"
git diff --cached --check -- "$AI_DIR"

echo
echo "[check] LLM patch checks"
"$AI_DIR/dev/llm/check-llm-patch.sh" --staged

echo
echo "[check] AI docs checks"
"$AI_DIR/dev/llm/check-ai-docs.sh"

if [ -x "$AI_DIR/dev/run-smoke.sh" ]; then
  echo
  echo "[check] AI smoke checks"
  "$AI_DIR/dev/run-smoke.sh"
else
  echo
  echo "[skip] no executable smoke script at $AI_DIR/dev/run-smoke.sh"
fi

if [ "${RUN_LIVE_CHECKS:-0}" = "1" ] && [ -x "$AI_DIR/dev/check-ai-live.sh" ]; then
  echo
  echo "[check] AI live checks"
  "$AI_DIR/dev/check-ai-live.sh"
else
  echo
  echo "[skip] live checks disabled. Run with RUN_LIVE_CHECKS=1 if needed."
fi

echo
echo "[ok] staged AI verification completed"
