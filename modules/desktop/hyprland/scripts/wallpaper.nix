{ pkgs, defaultWallpaper, ... }:
pkgs.writeShellScriptBin "wallpaper" ''
  # Wait for daemon to be ready (up to 5s)
  timeout=50
  until awww query &>/dev/null || [ $timeout -eq 0 ]; do
    sleep 0.1
    timeout=$((timeout - 1))
  done

  awww restore &>/dev/null

  if ! awww query | grep -qi "image:"; then
    awww img "${../../../themes/wallpapers/${defaultWallpaper}}" \
      --transition-step 255 --transition-duration 1 \
      --transition-fps 60 --transition-type none
  fi
''
