#!/usr/bin/env bash
# Replaces screenpipe's broken wlroots screencopy with grim
set -euo pipefail

API="http://localhost:3030"
TOKEN_FILE="$HOME/.screenpipe/auth_token"
INTERVAL="${SCREENPIPE_GRIM_INTERVAL:-2}"  # seconds between captures

get_token() {
  [[ -f "$TOKEN_FILE" ]] && cat "$TOKEN_FILE" || echo ""
}

wait_for_api() {
  until curl -sf "$API/health" >/dev/null 2>&1; do sleep 1; done
}

capture_loop() {
  local token
  token=$(get_token)
  local tmpfile
  tmpfile=$(mktemp /tmp/screenpipe-frame-XXXXX.png)
  trap 'rm -f "$tmpfile"' EXIT

  while true; do
    # Capture all outputs merged (grim default)
    if grim "$tmpfile" 2>/dev/null; then
      curl -sf -X POST "$API/vision/frames" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@$tmpfile" >/dev/null 2>&1 || true
    fi
    sleep "$INTERVAL"
  done
}

wait_for_api
capture_loop
