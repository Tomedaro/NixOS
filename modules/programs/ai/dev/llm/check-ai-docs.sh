#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"

echo "[check] git diff whitespace"
git diff --check -- "$AI_DIR"

echo
echo "[check] markdown links"
"$AI_DIR/dev/llm/check-markdown-links.sh"

echo
echo "[check] known typo/drift patterns"
"$AI_DIR/dev/llm/grep-known-typos.sh"

echo
echo "[ok] AI docs checks completed"
