#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"
TARGET="${1:-$AI_DIR}"

FOUND=0

check_pattern() {
  pattern="$1"
  label="$2"

  hits="$(grep -RInE \
    --exclude-dir=.git \
    --exclude-dir=__pycache__ \
    --exclude-dir=chatgpt-bundles \
    --exclude='grep-known-typos.sh' \
    --exclude='check-llm-patch.sh' \
    "$pattern" "$TARGET" 2>/dev/null || true)"

  if [ -n "$hits" ]; then
    echo
    echo "[warn] $label"
    echo "$hits"
    FOUND=1
  fi
}

echo "[info] scanning known typo and workflow-drift patterns under $TARGET"

check_pattern 'orworkflow|currenttruth|handoffdrift|roadmaptruth' \
  'Possible joined-word typo'

check_pattern 'Tasknotes|Task Notes' \
  'Possible TaskNotes spelling drift'

check_pattern 'AI-owned commitment|LLM-owned commitment|agent-owned commitment' \
  'Possible human-commitment boundary drift'

check_pattern 'ChatGPT memory is the source of truth|Project memory is canonical|custom GPT remembers prior chats' \
  'Possible model-memory overtrust'

check_pattern 'auto-commit|autocommit|automatically commit|agent may commit|LLM may apply' \
  'Possible unsafe automation or authority drift'

check_pattern 'roadmap item is current|planned feature is implemented|implemented future work' \
  'Possible current-state / roadmap confusion'

if [ "$FOUND" -eq 0 ]; then
  echo "[ok] no known typo/drift patterns found"
else
  echo
  echo "[warn] review hits above"
fi
