#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

AI_DIR="modules/programs/ai"
BAD=0

FILES=()
while IFS= read -r file; do
  FILES+=("$file")
done < <(
  find "$AI_DIR" \
    -path "$AI_DIR/chatgpt-bundles" -prune -o \
    -name '*.md' -type f -print
)

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "[warn] no markdown files found under $AI_DIR"
  exit 0
fi

for file in "${FILES[@]}"; do
  dir="$(dirname "$file")"

  while IFS= read -r hit; do
    line="${hit%%:*}"
    link="${hit#*:}"

    target="$(printf '%s' "$link" | sed -E 's/^.*\]\(([^)]*)\).*$/\1/')"
    target="${target%%#*}"
    target="${target%% *}"
    target="${target#<}"
    target="${target%>}"

    case "$target" in
      ""|\#*|http://*|https://*|mailto:*|tel:*|file:*)
        continue
        ;;
    esac

    resolved="$(realpath -m "$dir/$target")"

    case "$resolved" in
      "$ROOT"/*) ;;
      *) continue ;;
    esac

    if [ ! -e "$resolved" ]; then
      echo "[bad-link] $file:$line -> $target"
      BAD=1
    fi
  done < <(grep -nE '\[[^]]+\]\([^)]+\)' "$file" || true)
done

if [ "$BAD" -ne 0 ]; then
  echo "[fail] broken local markdown links found"
  exit 1
fi

echo "[ok] checked markdown links in ${#FILES[@]} files"
