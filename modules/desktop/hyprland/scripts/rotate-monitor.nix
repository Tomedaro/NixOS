{pkgs, ...}:
pkgs.writeShellScriptBin "rotate-monitor" ''
  monitor="HDMI-A-1"

  current_transform=$(
    hyprctl monitors -j \
      | ${pkgs.jq}/bin/jq -er --arg monitor "$monitor" \
          '.[] | select(.name == $monitor) | .transform'
  ) || exit 0

  case "$current_transform" in
    0) next_transform=1 ;;
    1) next_transform=0 ;;
    *) next_transform=0 ;;
  esac

  hyprctl eval "hl.monitor({ output = '$monitor', transform = $next_transform })"
''
