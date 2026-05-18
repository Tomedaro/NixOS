#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"
OUT_DIR="$AI_DIR/chatgpt-bundles"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/ai-chatgpt-bundle-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"

FILES=()

add_if_exists() {
  if [ -e "$1" ]; then
    FILES+=("$1")
  else
    echo "[warn] missing: $1" >&2
  fi
}

add_if_exists "$AI_DIR/AGENTS.md"
add_if_exists "$AI_DIR/workflow/LLM_HANDOFF.md"
add_if_exists "$AI_DIR/workflow/DECISIONS.md"
add_if_exists "$AI_DIR/workflow/VERIFICATION_LOG.md"
add_if_exists "$AI_DIR/workflow/OPEN_QUESTIONS.md"
add_if_exists "$AI_DIR/workflow/CHATGPT_WORKFLOW.md"

add_if_exists "$AI_DIR/README.md"
add_if_exists "$AI_DIR/CURRENT_STATE.md"
add_if_exists "$AI_DIR/PHILOSOPHY.md"
add_if_exists "$AI_DIR/SAFETY_MODEL.md"
add_if_exists "$AI_DIR/PROTOCOLS.md"
add_if_exists "$AI_DIR/MODULES.md"
add_if_exists "$AI_DIR/ARCHITECTURE.md"
add_if_exists "$AI_DIR/DEVELOPMENT.md"
add_if_exists "$AI_DIR/OPERATIONS.md"
add_if_exists "$AI_DIR/ROADMAP.md"
add_if_exists "$AI_DIR/GLOSSARY.md"
add_if_exists "$AI_DIR/EXTENSION_MODEL.md"

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "[error] no files found for bundle" >&2
  exit 1
fi

tar -czf "$OUT" "${FILES[@]}"

echo "[ok] wrote bundle:"
echo "$OUT"
echo
echo "[info] included files:"
printf ' - %s\n' "${FILES[@]}"
