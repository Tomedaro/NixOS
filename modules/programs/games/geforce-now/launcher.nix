{
  appId,
  appOrigin,
  gamescope,
  hyprland,
  lib,
  pkgs,
  targetModelRegex,
}: let
  bridge = pkgs.writeShellApplication {
    name = "geforce-now-gamescope-bridge";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.flatpak
      pkgs.util-linux
    ];

    text = ''
      app_id=${lib.escapeShellArg appId}
      runtime_dir="''${XDG_RUNTIME_DIR:-/run/user/$UID}"
      nested_display="''${WAYLAND_DISPLAY:-}"

      # The NixOS wrapper raises Gamescope's requested capability into its
      # ambient set, which ordinary child execs inherit. Clear only the sets
      # that propagate through execve before
      # entering Flatpak, then re-run this bridge so the assertion below
      # checks the exact credentials Flatpak will inherit.
      if [[ "''${GFN_BRIDGE_CAPS_CLEARED:-}" != 1 ]]; then
        export GFN_BRIDGE_CAPS_CLEARED=1
        exec setpriv \
          --inh-caps=-all \
          --ambient-caps=-all \
          "$0" "$@"
      fi
      unset GFN_BRIDGE_CAPS_CLEARED

      if [[ ! "$nested_display" =~ ^gamescope-[0-9]+$ ]]; then
        echo "Invalid Gamescope Wayland display: $nested_display" >&2
        exit 70
      fi

      nested_socket="$runtime_dir/$nested_display"
      if [[ ! -S "$nested_socket" ]]; then
        echo "Gamescope Wayland socket is missing: $nested_socket" >&2
        exit 71
      fi

      # Flatpak/Bubblewrap must receive an unprivileged process context. Keep
      # this as a post-drop assertion so a future capability-policy change
      # fails closed instead of reaching the sandbox boundary.
      while read -r capability value _; do
        case "$capability" in
          CapInh:|CapPrm:|CapEff:|CapAmb:)
            [[ "$value" =~ ^0+$ ]] || {
              echo "Unsafe capability context reached the Flatpak bridge: $capability $value" >&2
              exit 72
            }
            ;;
        esac
      done </proc/self/status

      flatpak_args=(
        --system
        --nosocket=wayland
        "--filesystem=xdg-run/$nested_display"
      )

      # --nosocket=wayland clears the display environment while constructing
      # the sandbox. Pass the validated name as argv, then export it from the
      # sandbox entry shell so only the private Gamescope socket is selected.
      case "''${1:---launch}" in
        --probe)
          probe_marker="''${2:-}"
          probe_name="''${probe_marker##*/}"
          if [[ "$probe_marker" != "$runtime_dir/$probe_name" \
            || ! "$probe_name" =~ ^geforce-now-bridge-probe\.[A-Za-z0-9]+$ \
            || ! -f "$probe_marker" \
            || -L "$probe_marker" \
            || ! -O "$probe_marker" ]]; then
            echo "Invalid bridge-probe marker: $probe_marker" >&2
            exit 73
          fi

          flatpak run \
            "''${flatpak_args[@]}" \
            --command=/usr/bin/sh \
            "$app_id" \
            -eu -c \
            "WAYLAND_DISPLAY=\$1; export WAYLAND_DISPLAY; test -S \"\$XDG_RUNTIME_DIR/\$WAYLAND_DISPLAY\"" \
            sh "$nested_display"
          printf 'passed\n' >"$probe_marker"
          ;;
        --launch)
          exec flatpak run \
            "''${flatpak_args[@]}" \
            --command=/usr/bin/sh \
            "$app_id" \
            -eu -c \
            "WAYLAND_DISPLAY=\$1; export WAYLAND_DISPLAY; exec /app/bin/GeForceNOW --no-relaunch" \
            sh "$nested_display"
          ;;
        *)
          echo "Unknown bridge mode: $1" >&2
          exit 64
          ;;
      esac
    '';
  };
in
  pkgs.writeShellApplication {
    name = "geforce-now";

    # cleanup is reached through EXIT/signal traps.
    excludeShellChecks = ["SC2329"];

    runtimeInputs = [
      bridge
      hyprland
      pkgs.coreutils
      pkgs.flatpak
      pkgs.gnugrep
      pkgs.jq
      pkgs.libnotify
      pkgs.util-linux
    ];

    text = ''
      app_id=${lib.escapeShellArg appId}
      app_origin=${lib.escapeShellArg appOrigin}
      gamescope_bin=${lib.escapeShellArg gamescope}
      bridge_bin=${lib.escapeShellArg (lib.getExe bridge)}
      target_model_regex=${lib.escapeShellArg targetModelRegex}

      runtime_dir="''${XDG_RUNTIME_DIR:-/run/user/$UID}"
      state_file="$runtime_dir/geforce-now-launch-state.json"
      lock_file="$runtime_dir/geforce-now-launch.lock"
      start_gate="$runtime_dir/geforce-now-launch-gate"
      hypr=(hyprctl)

      launched_by_us=false
      child_pid=""
      child_start=""
      pending_signal=""

      notify() {
        local urgency="$1"
        shift
        notify-send \
          --urgency="$urgency" \
          --app-name="GeForce NOW" \
          "GeForce NOW" \
          "$*" 2>/dev/null || true
      }

      die() {
        local message="$1"
        echo "ERROR: $message" >&2
        notify critical "$message"
        exit 1
      }

      validate_runtime_dir() {
        [[ -d "$runtime_dir" && -O "$runtime_dir" ]] \
          || die "XDG_RUNTIME_DIR is missing or is not owned by the current user: $runtime_dir"
      }

      compositor_available() {
        "''${hypr[@]}" -j monitors >/dev/null 2>&1
      }

      flatpak_running() {
        flatpak ps --columns=application 2>/dev/null \
          | grep -Fxq "$app_id"
      }

      pid_belongs_to_gfn() {
        local pid="$1"
        [[ "$pid" =~ ^[0-9]+$ ]] || return 1

        if [[ -r "/proc/$pid/environ" ]] \
          && tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null \
            | grep -Fxq "FLATPAK_ID=$app_id"; then
          return 0
        fi

        if [[ -r "/proc/$pid/root/.flatpak-info" ]] \
          && grep -Fxq "name=$app_id" \
            "/proc/$pid/root/.flatpak-info" 2>/dev/null; then
          return 0
        fi

        return 1
      }

      unmanaged_gfn_window_exists() {
        local clients pid
        clients="$("''${hypr[@]}" -j clients 2>/dev/null)" || return 1

        while IFS= read -r pid; do
          pid_belongs_to_gfn "$pid" && return 0
        done < <(
          jq -r '
            .[]
            | select((.mapped // true) == true)
            | select((.size[0] // 0) > 100 and (.size[1] // 0) > 100)
            | (.pid // 0)
          ' <<<"$clients"
        )

        return 1
      }

      proc_starttime() {
        local pid="$1"
        local stat rest start
        local -a fields

        [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/stat" ]] || return 1
        IFS= read -r stat <"/proc/$pid/stat" || return 1
        rest="''${stat#*) }"
        read -r -a fields <<<"$rest"
        start="''${fields[19]:-}"
        [[ "$start" =~ ^[0-9]+$ ]] || return 1
        printf '%s\n' "$start"
      }

      write_state() {
        local pid="''${1:-}"
        local start="''${2:-}"
        local temporary="$state_file.tmp.$BASHPID"

        umask 077
        jq -n \
          --arg pid "$pid" \
          --arg start "$start" \
          '{version: 1, gamescopePid: $pid, gamescopeStartTime: $start}' \
          >"$temporary"
        mv -f "$temporary" "$state_file"
      }

      clear_state() {
        rm -f "$state_file" "$state_file.tmp.$BASHPID"
      }

      terminate_exact_process() {
        local pid="$1"
        local start="$2"
        local actual

        [[ "$pid" =~ ^[0-9]+$ && "$start" =~ ^[0-9]+$ ]] || return 0
        actual="$(proc_starttime "$pid" 2>/dev/null || true)"
        [[ "$actual" == "$start" ]] || return 0

        kill -TERM "$pid" 2>/dev/null || true
        for _ in $(seq 1 40); do
          actual="$(proc_starttime "$pid" 2>/dev/null || true)"
          [[ "$actual" != "$start" ]] && return 0
          sleep 0.05
        done

        actual="$(proc_starttime "$pid" 2>/dev/null || true)"
        if [[ "$actual" == "$start" ]]; then
          kill -KILL "$pid" 2>/dev/null || true
        fi
      }

      terminate_recorded_gamescope() {
        local pid start

        [[ -f "$state_file" ]] || return 0
        pid="$(jq -r '.gamescopePid // empty' "$state_file" 2>/dev/null || true)"
        start="$(jq -r '.gamescopeStartTime // empty' "$state_file" 2>/dev/null || true)"
        terminate_exact_process "$pid" "$start"
      }

      reload_declarative_state() {
        compositor_available \
          && "''${hypr[@]}" reload >/dev/null 2>&1
      }

      recover_state() {
        [[ -f "$state_file" ]] || return 0

        rm -f "$start_gate"
        terminate_recorded_gamescope
        flatpak kill "$app_id" >/dev/null 2>&1 || true
        reload_declarative_state \
          || die "Recovery could not reload the declarative Hyprland state; the recovery marker was retained."
        clear_state
      }

      cleanup() {
        local rc
        rc=$?
        trap - EXIT INT TERM HUP
        rm -f "$start_gate"

        if [[ "$launched_by_us" == true ]]; then
          flatpak kill "$app_id" >/dev/null 2>&1 || true
        fi

        terminate_exact_process "$child_pid" "$child_start" || true
        terminate_recorded_gamescope || true

        if [[ -n "$child_pid" ]]; then
          wait "$child_pid" 2>/dev/null || true
        fi

        if [[ -f "$state_file" ]]; then
          if reload_declarative_state; then
            clear_state
          else
            notify critical \
              "Hyprland reload failed; run geforce-now --reset before the next launch. The recovery marker was retained."
          fi
        fi
        exit "$rc"
      }

      resolve_target_monitor() {
        local monitors="$1"

        jq -r --arg re "$target_model_regex" '
          (
            [
              .[]
              | select(
                  ((.model // "") | test($re; "i"))
                  or
                  ((.description // "") | test($re; "i"))
                )
            ][0]
            // [.[] | select(.focused == true)][0]
            // .[0]
          ).name // empty
        ' <<<"$monitors"
      }

      bitdepth_filter='if ((.currentFormat // "") | test("101010")) then 10 else 8 end'

      expected_geometry() {
        local monitors="$1"
        local target="$2"

        jq -cS --arg target "$target" "
          map({
            name,
            width,
            height,
            refreshCentihz: ((.refreshRate * 100) | round),
            x,
            y,
            scaleMilli: (
              ((if .name == \$target then 1 else .scale end) * 1000)
              | round
            ),
            transform,
            bitdepth: ($bitdepth_filter)
          })
          | sort_by(.name)
        " <<<"$monitors"
      }

      actual_geometry() {
        local monitors="$1"

        jq -cS "
          map({
            name,
            width,
            height,
            refreshCentihz: ((.refreshRate * 100) | round),
            x,
            y,
            scaleMilli: ((.scale * 1000) | round),
            transform,
            bitdepth: ($bitdepth_filter)
          })
          | sort_by(.name)
        " <<<"$monitors"
      }

      check_setup() {
        local notify_success="''${1:-false}"
        local runtime origin gamescope_version monitors target

        runtime="$(flatpak info --system --show-runtime "$app_id" 2>/dev/null)" \
          || die "The system GeForce NOW Flatpak is not installed."
        origin="$(flatpak info --system --show-origin "$app_id" 2>/dev/null)" \
          || die "The system GeForce NOW Flatpak origin could not be read."
        [[ "$origin" == "$app_origin" ]] \
          || die "GeForce NOW has unexpected Flatpak origin '$origin' (expected '$app_origin')."

        [[ -x "$gamescope_bin" ]] \
          || die "The NixOS Gamescope wrapper is missing: $gamescope_bin"

        gamescope_version="$("$gamescope_bin" --version 2>&1 | head -1 || true)"
        [[ -n "$gamescope_version" ]] \
          || die "The host Gamescope binary could not report its version."

        printf 'GFN app:          %s\n' "$app_id"
        printf 'GFN origin:       %s\n' "$origin"
        printf 'GFN runtime:      %s\n' "$runtime"
        printf 'Host Gamescope:   %s\n' "$gamescope_bin"
        printf 'Gamescope:        %s\n' "$gamescope_version"

        if compositor_available; then
          monitors="$("''${hypr[@]}" -j monitors)"
          target="$(resolve_target_monitor "$monitors")"
          jq -r --arg target "$target" "
            .[]
            | select(.name == \$target)
            | \"Target monitor:   \\(.name) | \\(.model // .description // \"?\") | \\(.width)x\\(.height)@\\(.refreshRate) | scale \\(.scale) | \\($bitdepth_filter)-bit\"
          " <<<"$monitors"
        else
          printf 'Hyprland:         not currently available\n'
        fi

        printf 'Compatibility:    OK\n'
        if [[ "$notify_success" == true ]]; then
          notify normal "Host Gamescope compatibility check passed."
        fi
      }

      bridge_check() {
        local gamescope_status probe_marker probe_result

        validate_runtime_dir
        compositor_available \
          || die "An active Hyprland session is required for the bridge check."
        check_setup false >/dev/null

        if flatpak_running; then
          die "Close GeForce NOW before running the Gamescope bridge check."
        fi

        probe_marker="$(
          mktemp "$runtime_dir/geforce-now-bridge-probe.XXXXXX"
        )" || die "Could not create the bridge-probe marker."
        printf 'pending\n' >"$probe_marker"

        # Gamescope 3.16.25 can segfault while tearing down a short-lived
        # nested session. Trust only the marker written by the host bridge
        # after Flatpak's in-sandbox socket test succeeds, never Gamescope's
        # cleanup status by itself.
        if timeout \
          --signal=TERM \
          --kill-after=5s \
          30s \
          "$gamescope_bin" \
          --backend wayland \
          --expose-wayland \
          -W 64 \
          -H 64 \
          -- \
          "$bridge_bin" --probe "$probe_marker"; then
          gamescope_status=0
        else
          gamescope_status=$?
        fi

        if [[ -f "$probe_marker" ]]; then
          probe_result="$(<"$probe_marker")"
        else
          probe_result=missing
        fi
        rm -f -- "$probe_marker"
        [[ "$probe_result" == passed ]] \
          || die "The in-sandbox Wayland-socket probe failed (Gamescope status $gamescope_status)."

        if (( gamescope_status != 0 )); then
          printf 'Gamescope probe cleanup status %d ignored after attested bridge success.\n' \
            "$gamescope_status"
        fi

        printf 'Gamescope bridge: OK\n'
        notify normal "Host Gamescope → Flatpak Wayland bridge check passed."
      }

      reset_setup() {
        validate_runtime_dir
        recover_state
        flatpak kill "$app_id" >/dev/null 2>&1 || true
        if compositor_available; then
          reload_declarative_state \
            || die "GFN was stopped, but Hyprland could not reload its declarative state."
        fi
        notify normal "GFN was stopped and the declarative Hyprland state was restored."
      }

      case "''${1:-}" in
        --check)
          check_setup true
          exit 0
          ;;
        --bridge-check)
          bridge_check
          exit 0
          ;;
        --reset)
          reset_setup
          exit 0
          ;;
        -h|--help)
          cat <<'EOF'
      Usage: geforce-now [--check|--bridge-check|--reset]

        no argument     Launch GFN through host Gamescope
        --check         Verify GFN, host Gamescope, and monitor discovery
        --bridge-check  Test the private Gamescope-to-Flatpak Wayland socket
        --reset         Stop managed GFN and restore declarative Hyprland state
      EOF
          exit 0
          ;;
        "")
          ;;
        *)
          die "Unknown option: $1"
          ;;
      esac

      validate_runtime_dir
      compositor_available \
        || die "An active Hyprland session is required for the managed launcher."

      exec 9>"$lock_file"
      if ! flock -n 9; then
        die "Another managed GeForce NOW launch is already active."
      fi

      # A previous wrapper may have been SIGKILLed after changing live state.
      recover_state
      check_setup false >/dev/null

      if unmanaged_gfn_window_exists; then
        die "An unmanaged GeForce NOW window is already open."
      fi

      if flatpak_running; then
        flatpak kill "$app_id" >/dev/null 2>&1 || true
        for _ in $(seq 1 20); do
          flatpak_running || break
          sleep 0.1
        done
        if flatpak_running; then
          die "A stale GeForce NOW sandbox could not be stopped safely."
        fi
      fi

      monitors="$("''${hypr[@]}" -j monitors)"
      jq -e 'type == "array" and length > 0' <<<"$monitors" >/dev/null \
        || die "Hyprland returned no active monitors."

      target_monitor="$(resolve_target_monitor "$monitors")"
      [[ -n "$target_monitor" ]] || die "No launch monitor could be resolved."

      output_width="$(
        jq -er --arg target "$target_monitor" \
          '.[] | select(.name == $target) | .width' <<<"$monitors"
      )"
      output_height="$(
        jq -er --arg target "$target_monitor" \
          '.[] | select(.name == $target) | .height' <<<"$monitors"
      )"
      expected="$(expected_geometry "$monitors" "$target_monitor")"

      # From this point onward, an extant state file means a reload is needed.
      write_state
      trap cleanup EXIT
      trap 'exit 130' INT
      trap 'exit 143' TERM HUP

      if jq -e --arg target "$target_monitor" \
        'any(.[]; .name == $target and .scale != 1)' \
        <<<"$monitors" >/dev/null; then
        monitor_lua="$(
          jq -r --arg target "$target_monitor" '
            map(
              "hl.monitor({\n" +
              "  output = " + (.name | @json) + ",\n" +
              "  mode = " +
                (((.width | tostring) + "x" +
                  (.height | tostring) + "@" +
                  (.refreshRate | tostring)) | @json) + ",\n" +
              "  position = " +
                (((.x | tostring) + "x" + (.y | tostring)) | @json) + ",\n" +
              "  scale = " +
                (if .name == $target then "1" else (.scale | tostring) end) + ",\n" +
              "  transform = " + (.transform | tostring) + ",\n" +
              "  bitdepth = " +
                (if ((.currentFormat // "") | test("101010")) then "10" else "8" end) +
              "\n})"
            )
            | join("\n\n")
          ' <<<"$monitors"
        )"

        "''${hypr[@]}" eval "$monitor_lua" >/dev/null

        geometry_ok=false
        for _ in $(seq 1 40); do
          current_monitors="$("''${hypr[@]}" -j monitors)"
          actual="$(actual_geometry "$current_monitors")"
          if [[ "$actual" == "$expected" ]]; then
            geometry_ok=true
            break
          fi
          sleep 0.05
        done

        [[ "$geometry_ok" == true ]] \
          || die "Hyprland did not apply the exact scale-1 geometry without collateral monitor changes."
      fi

      # Gamescope 3.16.25 uses the stable outer app-id `gamescope`. Applying
      # placement before map avoids the broken focus-and-move tiled window.
      rule_lua="$(
        jq -nr --arg monitor "$target_monitor" '
          "hl.window_rule({\n" +
          "  match = { class = \"^(gamescope)$\" },\n" +
          "  monitor = " + ($monitor | @json) + ",\n" +
          "  fullscreen = true,\n" +
          "})"
        '
      )"
      "''${hypr[@]}" eval "$rule_lua" >/dev/null

      launched_by_us=true

      supervisor_pid="$BASHPID"
      supervisor_start="$(proc_starttime "$supervisor_pid")"
      rm -f "$start_gate"

      # During the fork/identity handoff, defer signal exits until child_pid and
      # child_start are both available to PID-reuse-safe cleanup.
      trap 'pending_signal=130' INT
      trap 'pending_signal=143' TERM HUP

      # The subshell records its own PID and Linux start time before exec.
      # It does not enter Gamescope until the supervisor opens the start gate.
      # If the supervisor is SIGKILLed first, the child observes that its exact
      # PID/start-time identity vanished and exits without creating an orphan.
      (
        # The lock belongs only to the supervising wrapper. Closing the child
        # copy ensures SIGKILL releases it so the next launch can recover.
        exec 9>&-
        recorded_pid="$BASHPID"
        recorded_start="$(proc_starttime "$recorded_pid")"
        write_state "$recorded_pid" "$recorded_start"

        gate_open=false
        for _ in $(seq 1 100); do
          actual_supervisor_start="$(proc_starttime "$supervisor_pid" 2>/dev/null || true)"
          [[ "$actual_supervisor_start" == "$supervisor_start" ]] || exit 125
          if [[ -f "$start_gate" ]]; then
            gate_open=true
            break
          fi
          sleep 0.02
        done
        [[ "$gate_open" == true ]] || exit 125

        exec "$gamescope_bin" \
          --backend wayland \
          --expose-wayland \
          --force-grab-cursor \
          -W "$output_width" \
          -H "$output_height" \
          -f \
          -- \
          "$bridge_bin" --launch
      ) &
      child_pid=$!
      child_start="$(proc_starttime "$child_pid" 2>/dev/null || true)"
      trap 'exit 130' INT
      trap 'exit 143' TERM HUP

      if [[ -n "$pending_signal" ]]; then
        exit "$pending_signal"
      fi

      [[ "$child_start" =~ ^[0-9]+$ ]] \
        || die "Host Gamescope exited before its recovery state was recorded."

      state_recorded=false
      for _ in $(seq 1 40); do
        state_pid="$(jq -r '.gamescopePid // empty' "$state_file" 2>/dev/null || true)"
        state_start="$(jq -r '.gamescopeStartTime // empty' "$state_file" 2>/dev/null || true)"
        if [[ "$state_pid" == "$child_pid" && "$state_start" == "$child_start" ]]; then
          state_recorded=true
          break
        fi
        sleep 0.05
      done
      [[ "$state_recorded" == true ]] \
        || die "Host Gamescope recovery state was not recorded atomically."

      umask 077
      : >"$start_gate"

      window_address=""
      for _ in $(seq 1 300); do
        clients="$("''${hypr[@]}" -j clients 2>/dev/null || true)"
        window_address="$(
          jq -r --argjson pid "$child_pid" '
            [
              .[]
              | select((.mapped // true) == true)
              | select(.pid == $pid)
              | select((.class // "") == "gamescope")
              | .address
            ][0] // empty
          ' <<<"$clients" 2>/dev/null || true
        )"
        [[ -n "$window_address" ]] && break

        if ! kill -0 "$child_pid" 2>/dev/null; then
          if wait "$child_pid"; then rc=0; else rc=$?; fi
          child_pid=""
          die "Host Gamescope/GFN exited during startup (status $rc)."
        fi
        sleep 0.1
      done

      [[ -n "$window_address" ]] \
        || die "Host Gamescope started but no outer window appeared within 30 seconds."

      target_id="$(
        "''${hypr[@]}" -j monitors \
          | jq -r --arg target "$target_monitor" \
            '[.[] | select(.name == $target) | .id][0] // empty'
      )"
      [[ "$target_id" =~ ^[0-9]+$ ]] \
        || die "The target monitor disappeared while Gamescope was starting."
      placement_ok=false
      for _ in $(seq 1 40); do
        if "''${hypr[@]}" -j clients \
          | jq -e \
              --arg address "$window_address" \
              --argjson monitor "$target_id" '
                any(.[];
                  .address == $address
                  and .monitor == $monitor
                  and (.fullscreen // 0) != 0
                )
              ' >/dev/null; then
          placement_ok=true
          break
        fi
        sleep 0.05
      done

      [[ "$placement_ok" == true ]] \
        || die "The map-time Gamescope monitor/fullscreen rule did not take effect."

      # Brief remaps are tolerated; one continuous second of absence is close.
      missing=0
      while (( missing < 5 )); do
        if "''${hypr[@]}" -j clients \
          | jq -e --argjson pid "$child_pid" \
            'any(.[]; (.mapped // true) == true and .pid == $pid)' \
            >/dev/null 2>&1; then
          missing=0
        else
          missing=$((missing + 1))
        fi
        sleep 0.2
      done

      exit 0
    '';
  }
