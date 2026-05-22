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
declare -A SEEN=()

add_if_exists() {
  local path="$1"

  if [ -z "$path" ]; then
    return
  fi

  if [ "${SEEN[$path]+seen}" = "seen" ]; then
    return
  fi

  if [ -e "$path" ]; then
    FILES+=("$path")
    SEEN["$path"]=1
  else
    echo "[warn] missing: $path" >&2
  fi
}

# Curated core docs first. Keep this order stable for ChatGPT handoff context.
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

# Append every active Markdown doc under modules/programs/ai.
# Exclude generated bundles, archived workflow docs, and cache artifacts.
while IFS= read -r -d '' path; do
  add_if_exists "$path"
done < <(
  find "$AI_DIR" \
    -type f \
    -name '*.md' \
    ! -path "$AI_DIR/chatgpt-bundles/*" \
    ! -path "$AI_DIR/workflow/archive/*" \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 \
    | sort -z
)

tar -czf "$OUT" "${FILES[@]}"

echo "[ok] wrote bundle:"
echo "$OUT"
echo
echo "[info] included ${#FILES[@]} files:"
for file in "${FILES[@]}"; do
  echo " - $file"
done
