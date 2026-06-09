{ pkgs, lib, paths, piWrapped, piNpm, scripts }:

let
  git = "${pkgs.git}/bin/git";
  date = "${pkgs.coreutils}/bin/date";
  mkdir = "${pkgs.coreutils}/bin/mkdir";
  cat = "${pkgs.coreutils}/bin/cat";
  rm = "${pkgs.coreutils}/bin/rm";
  mktemp = "${pkgs.coreutils}/bin/mktemp";
  realpath = "${pkgs.coreutils}/bin/realpath";
  find = "${pkgs.findutils}/bin/find";
  sort = "${pkgs.coreutils}/bin/sort";
  sha256sum = "${pkgs.coreutils}/bin/sha256sum";
  cut = "${pkgs.coreutils}/bin/cut";
  jq = "${pkgs.jq}/bin/jq";
  du = "${pkgs.coreutils}/bin/du";
  mv = "${pkgs.coreutils}/bin/mv";
  chmod = "${pkgs.coreutils}/bin/chmod";

  srcGlobalSettings = ./settings/global.json;
  srcNixosAgents = ./resources/nixos/AGENTS.md;
  srcNixosPrompts = ./resources/nixos/prompts;
  srcNixosSkill = ./resources/nixos/skills/pi-nix-self-maintenance;

  wrapperPrelude = profile: ''
    set -euo pipefail
    export PI_PERMISSION_SYSTEM_POLICY_AGENT_DIR="${paths.piPoliciesDir}/${profile}"
    export PI_CODING_AGENT_SESSION_DIR="${paths.piSessionsDir}/${profile}"
    export NPM_CONFIG_PREFIX="${paths.piNpmDir}"
    export PI_SKIP_VERSION_CHECK=1
    export PI_TELEMETRY=0
    export PI_CACHE_RETENTION=long
    ${rejectManagedPolicyBypassOverrides}

    preflight_fail() {
      local msg="$1"
      echo "Pi permission preflight failed for profile '${profile}': $msg" >&2
      shift
      for line in "$@"; do echo "$line" >&2; done
      echo "Escape hatch: pi-raw" >&2
      exit 2
    }

    if [ ! -f "$PI_PERMISSION_SYSTEM_POLICY_AGENT_DIR/pi-permissions.jsonc" ]; then
      echo "Pi policy missing for profile '${profile}'. Run: pi-admin sync global" >&2
      exit 1
    fi

    expected_permission_version="$(${jq} -er '
      [
        .packages[]
        | if type == "object" then (.source // empty) else . end
        | select(type == "string" and startswith("npm:@gotgenes/pi-permission-system@"))
        | sub("^npm:@gotgenes/pi-permission-system@"; "")
      ][0] // empty
    ' "${srcGlobalSettings}" 2>/dev/null || true)"

    if [ -z "$expected_permission_version" ]; then
      preflight_fail "could not find pinned @gotgenes/pi-permission-system package in source settings." \
        "Source settings: ${srcGlobalSettings}" \
        "Refusing to start without a verifiable permission-system pin."
    fi

    permission_pkg_dir="${paths.piNpmDir}/node_modules/@gotgenes/pi-permission-system"
    permission_ext="$permission_pkg_dir/src/index.ts"
    permission_pkg_json="$permission_pkg_dir/package.json"

    if [ ! -f "$permission_ext" ]; then
      preflight_fail "@gotgenes/pi-permission-system extension entrypoint is missing." \
        "Expected: $permission_ext" \
        "Run: pi-admin sync global && pi-raw update --extensions && pi-admin compat" \
        "Refusing to start without policy enforcement."
    fi

    if [ ! -f "$permission_pkg_json" ]; then
      preflight_fail "@gotgenes/pi-permission-system package.json is missing." \
        "Expected: $permission_pkg_json" \
        "Run: pi-admin sync global && pi-raw update --extensions && pi-admin compat" \
        "Refusing to start without a verifiable permission-system version."
    fi

    actual_permission_version="$(${jq} -r '.version // empty' "$permission_pkg_json" 2>/dev/null || true)"

    if [ -z "$actual_permission_version" ]; then
      preflight_fail "could not read @gotgenes/pi-permission-system installed version." \
        "Package JSON: $permission_pkg_json" \
        "Run: pi-admin sync global && pi-raw update --extensions && pi-admin compat" \
        "Refusing to start without a verifiable permission-system version."
    fi

    if [ "$actual_permission_version" != "$expected_permission_version" ]; then
      preflight_fail "@gotgenes/pi-permission-system version mismatch." \
        "Expected from source: $expected_permission_version" \
        "Installed: $actual_permission_version" \
        "Package JSON: $permission_pkg_json" \
        "Run: pi-admin sync global && pi-raw update --extensions && pi-admin compat" \
        "Refusing to start with mismatched policy enforcement package."
    fi

    ${mkdir} -p "$PI_CODING_AGENT_SESSION_DIR"
  '';

  rejectManagedPolicyBypassOverrides = ''
    for arg in "$@"; do
      case "$arg" in
        --no-extensions|--no-extensions=*|-ne)
          echo "Pi managed profile rejects extension-disable flag: $arg" >&2
          echo "This profile depends on @gotgenes/pi-permission-system for policy enforcement." >&2
          echo "Use pi-raw only if you intentionally want to bypass managed profile policy." >&2
          exit 2
          ;;
      esac
    done
  '';

  rejectCautiousOverrides = ''
    for arg in "$@"; do
      case "$arg" in
        @*)
          echo "pi cautious mode rejects @file arguments: $arg" >&2
          echo "Paste text explicitly, or use normal pi/another mode when file attachment is intentional." >&2
          exit 2
          ;;
        --tools|--tools=*|-t|--extension|--extension=*|-e|--no-extensions|-ne|--no-builtin-tools|-nbt|--api-key|--api-key=*|--provider|--provider=*|--model|--model=*|--models|--models=*|--mode|--mode=*|--theme|--theme=*|--export|--export=*|--list-models|--list-models=*|--session-dir|--session-dir=*|--system-prompt|--system-prompt=*|--append-system-prompt|--append-system-prompt=*|--skill|--skill=*|--prompt-template|--prompt-template=*|--mcp-config|--mcp-config=*|--continue|-c|--resume|-r|--session|--session=*|--fork|--fork=*|--no-session|--approve|--approve=*|-a)
          echo "pi cautious mode rejects override flag: $arg" >&2
          echo "Use normal pi, pi-raw, or another PI_PROFILE when changing tools/model/resources/session behavior." >&2
          exit 2
          ;;
      esac
    done
  '';

  piRaw = pkgs.writeShellScriptBin "pi-raw" ''
    set -euo pipefail
    exec ${piWrapped}/bin/pi "$@"
  '';

  piReadonly = pkgs.writeShellScriptBin "pi-readonly" ''
    ${wrapperPrelude "safe"}
    ${rejectCautiousOverrides}
    export PI_OFFLINE=1

    launch_dir="${paths.piAgentDir}/readonly-workspace"
    ${mkdir} -p "$launch_dir"
    cd "$launch_dir"
    echo "Pi cautious mode: empty scope $launch_dir" >&2
    echo "This is policy-backed convenience, not an OS/network sandbox." >&2
    echo "Do not use it as a security boundary for untrusted repositories or symlink-heavy trees." >&2
    exec ${piWrapped}/bin/pi \
      --offline \
      --no-context-files \
      --no-extensions \
      --extension "$permission_ext" \
      --no-skills \
      --no-prompt-templates \
      --no-themes \
      --tools read,grep,find,ls \
      "$@"
  '';

  piCautious = pkgs.writeShellScriptBin "pi-cautious" ''
    exec ${piReadonly}/bin/pi-readonly "$@"
  '';

  piSafe = pkgs.writeShellScriptBin "pi-safe" ''
    echo "pi-safe is deprecated terminology." >&2
    echo "It now launches policy-backed cautious mode, which is not an OS/network sandbox." >&2
    exec ${piReadonly}/bin/pi-readonly "$@"
  '';

  piNixos = pkgs.writeShellScriptBin "pi-nixos" ''
    ${wrapperPrelude "nixos"}
    repo="''${PI_NIXOS_REPO:-${paths.nixosRepo}}"
    if [ ! -d "$repo" ]; then
      echo "NixOS repo not found: $repo" >&2
      exit 1
    fi
    repo="$(${realpath} -m "$repo")"
    cd "$repo"
    ${mkdir} -p .pi/checkpoints
    if ${git} rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      ts="$(${date} -u +%Y%m%dT%H%M%SZ)"
      ${git} status --short > ".pi/checkpoints/$ts.status"
      ${git} diff --binary > ".pi/checkpoints/$ts.unstaged.diff" || true
      ${git} diff --cached --binary > ".pi/checkpoints/$ts.staged.diff" || true
      echo "Pi checkpoint written under .pi/checkpoints/$ts.*" >&2
    fi
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi \
      --append-system-prompt "${srcNixosAgents}" \
      --prompt-template "${srcNixosPrompts}" \
      --skill "${srcNixosSkill}" \
      "$@"
  '';

  piStudy = pkgs.writeShellScriptBin "pi-study" ''
    ${wrapperPrelude "study"}
    learning="''${PI_LEARNING_DIR:-${paths.learningDir}}"
    ${scripts.piStudyInit}/bin/pi-study-init --quiet
    cd "$learning"
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi "$@"
  '';

  piStudyTutor = pkgs.writeShellScriptBin "pi-study-tutor" ''
    ${wrapperPrelude "study"}
    learning="''${PI_LEARNING_DIR:-${paths.learningDir}}"
    ${scripts.piStudyTutorInit}/bin/pi-study-tutor-init --quiet
    cd "$learning"
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi "$@"
  '';

  piWork = pkgs.writeShellScriptBin "pi-work" ''
    ${wrapperPrelude "work"}
    if [ -n "''${PI_WORK_DIR:-}" ]; then
      work="$PI_WORK_DIR"
    elif root_file="$(${mktemp})" && ${git} rev-parse --show-toplevel > "$root_file" 2>/dev/null; then
      work="$(${cat} "$root_file")"
      ${rm} -f "$root_file"
    elif [ -f flake.nix ] || [ -f package.json ] || [ -f pyproject.toml ] || [ -d .git ]; then
      work="$PWD"
    elif [ -d "${paths.workDir}" ]; then
      work="${paths.workDir}"
    else
      echo "No work project detected and ${paths.workDir} does not exist." >&2
      echo "Run from a project directory or set PI_WORK_DIR=/path/to/project." >&2
      exit 2
    fi

    if [ ! -d "$work" ]; then
      echo "Work directory does not exist: $work" >&2
      exit 2
    fi

    work="$(${realpath} -m "$work")"
    nixos_repo="$(${realpath} -m "${paths.nixosRepo}")"
    if [ "$work" = "$nixos_repo" ] && [ "''${PI_WORK_ALLOW_NIXOS:-0}" != "1" ]; then
      echo "Refusing to run pi-work inside $nixos_repo. Use pi-nixos or smart pi from the NixOS repo." >&2
      echo "Override only if intentional: PI_WORK_ALLOW_NIXOS=1 PI_WORK_DIR=$nixos_repo pi-work" >&2
      exit 2
    fi

    export PI_WORK_DIR="$work"
    ${scripts.piWorkInit}/bin/pi-work-init --quiet
    cd "$work"
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi "$@"
  '';

  piResearch = pkgs.writeShellScriptBin "pi-research" ''
    ${wrapperPrelude "research"}
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi "$@"
  '';

  piTrusted = pkgs.writeShellScriptBin "pi-trusted" ''
    ${wrapperPrelude "trusted"}
    echo "Warning: pi-trusted is more permissive. It is still not a sandbox." >&2
    unset PI_OFFLINE || true
    exec ${piWrapped}/bin/pi "$@"
  '';

  piSmart = pkgs.writeShellScriptBin "pi" ''
    set -euo pipefail

    mode="''${PI_PROFILE:-auto}"
    current="$(${realpath} -m "$PWD")"
    nixos_repo="$(${realpath} -m "${paths.nixosRepo}")"
    learning_dir="$(${realpath} -m "${paths.learningDir}")"

    if [ "$mode" = "auto" ]; then
      case "$current" in
        "$nixos_repo"|"$nixos_repo"/*)
          mode="nixos"
          ;;
        "$learning_dir"|"$learning_dir"/*)
          mode="study"
          ;;
        *)
          root_file="$(${mktemp})"
          if ${git} rev-parse --show-toplevel > "$root_file" 2>/dev/null; then
            git_root="$(${cat} "$root_file")"
            ${rm} -f "$root_file"
            git_root="$(${realpath} -m "$git_root")"
            if [ "$git_root" = "$nixos_repo" ]; then
              mode="nixos"
            else
              export PI_WORK_DIR="$git_root"
              mode="work"
            fi
          else
            ${rm} -f "$root_file"
            if [ -f flake.nix ] || [ -f package.json ] || [ -f pyproject.toml ] || [ -f Cargo.toml ] || [ -d .git ]; then
              export PI_WORK_DIR="$current"
              mode="work"
            else
              mode="research"
            fi
          fi
          ;;
      esac
    fi

    case "$mode" in
      raw)
        exec ${piRaw}/bin/pi-raw "$@"
        ;;
      nixos)
        echo "Pi mode: nixos - scope: ${paths.nixosRepo}" >&2
        exec ${piNixos}/bin/pi-nixos "$@"
        ;;
      study)
        echo "Pi mode: study - scope: ''${PI_LEARNING_DIR:-${paths.learningDir}}}" >&2
        exec ${piStudy}/bin/pi-study "$@"
        ;;
      study-tutor|tutor)
        echo "Pi mode: study-tutor - scope: ''${PI_LEARNING_DIR:-${paths.learningDir}}}" >&2
        exec ${piStudyTutor}/bin/pi-study-tutor "$@"
        ;;
      work)
        echo "Pi mode: work - scope: ''${PI_WORK_DIR:-$current}" >&2
        exec ${piWork}/bin/pi-work "$@"
        ;;
      research)
        echo "Pi mode: research - scope: $current" >&2
        exec ${piResearch}/bin/pi-research "$@"
        ;;
      trusted)
        echo "Pi mode: trusted - scope: $current" >&2
        exec ${piTrusted}/bin/pi-trusted "$@"
        ;;
      cautious|readonly|safe)
        echo "Pi mode: cautious - policy-backed, not a sandbox" >&2
        exec ${piReadonly}/bin/pi-readonly "$@"
        ;;
      *)
        echo "Unknown PI_PROFILE: $mode" >&2
        echo "Known: auto, raw, nixos, study, study-tutor, work, research, trusted, cautious" >&2
        exit 2
        ;;
    esac
  '';

  piAdmin = pkgs.writeShellScriptBin "pi-admin" ''
    set -euo pipefail

    usage() {
      ${cat} <<'EOF'
pi-admin - maintenance for the NixOS-managed Pi setup

Usage:
  pi-admin status
  pi-admin sync [global|study|study-tutor|work|current|all]
  pi-admin doctor
  pi-admin drift
  pi-admin compat
  pi-admin mode
  pi-admin source-check
  pi-admin security
  pi-admin help

Daily use should be plain: pi
Escape hatch: pi-raw
EOF
    }

    source_hash() {
      if [ -d "${paths.piSourceDir}" ]; then
        (cd "${paths.piSourceDir}" && ${find} . -type f ! -name '*.before-*' | ${sort} | while IFS= read -r f; do ${sha256sum} "$f"; done) | ${sha256sum} | ${cut} -d ' ' -f 1
      else
        echo unknown
      fi
    }

    write_state_stamp() {
      ${mkdir} -p "${paths.piAgentDir}"
      tmp="$(${mktemp})"
      hash="$(source_hash)"
      now="$(${date} -u +%Y-%m-%dT%H:%M:%SZ)"
      version="$(${piWrapped}/bin/pi --version 2>/dev/null || true)"
      ${cat} > "$tmp" <<EOF
{
  "sourceRoot": "${paths.piSourceDir}",
  "sourceHash": "$hash",
  "syncedAtUtc": "$now",
  "piVersion": "$version"
}
EOF
      ${mv} "$tmp" "${paths.piAgentDir}/nix-managed-state.json"
      ${chmod} 600 "${paths.piAgentDir}/nix-managed-state.json"
    }

    detect_mode() {
      current="$(${realpath} -m "$PWD")"
      nixos_repo="$(${realpath} -m "${paths.nixosRepo}")"
      learning_dir="$(${realpath} -m "${paths.learningDir}")"
      case "$current" in
        "$nixos_repo"|"$nixos_repo"/*) echo nixos ;;
        "$learning_dir"|"$learning_dir"/*) echo study ;;
        *)
          if ${git} rev-parse --show-toplevel >/dev/null 2>&1; then echo work; else echo research; fi
          ;;
      esac
    }

    cmd="''${1:-help}"
    shift || true

    case "$cmd" in
      help|-h|--help)
        usage
        ;;
      mode)
        echo "Detected mode: $(detect_mode)"
        echo "Override with PI_PROFILE=raw|nixos|study|study-tutor|work|research|trusted|cautious pi"
        ;;
      status)
        echo "Pi status"
        echo "Version: $(${piWrapped}/bin/pi --version 2>/dev/null || echo unknown)"
        echo "Detected mode: $(detect_mode)"
        echo "Source: ${paths.piSourceDir}"
        echo "Source hash: $(source_hash)"
        if [ -f "${paths.piAgentDir}/nix-managed-state.json" ]; then
          echo "Last sync:"
          ${jq} '{syncedAtUtc,piVersion,sourceHash}' "${paths.piAgentDir}/nix-managed-state.json" 2>/dev/null || true
        else
          echo "Last sync: no nix-managed-state.json stamp yet"
        fi
        echo
        echo "Global model:"
        ${jq} '{defaultProvider,defaultModel,defaultThinkingLevel,theme,powerline}' "${paths.piAgentDir}/settings.json" 2>/dev/null || true
        echo
        echo "Control packages:"
        for pkg in @gotgenes/pi-permission-system pi-mcp-adapter pi-powerline-footer pi-themes pi-ask-user; do
          if [ -f "${paths.piNpmDir}/node_modules/$pkg/package.json" ]; then
            version="$(${jq} -r '.version // "unknown"' "${paths.piNpmDir}/node_modules/$pkg/package.json" 2>/dev/null || echo unknown)"
            echo "OK: $pkg@$version"
          else
            echo "MISSING: $pkg"
          fi
        done
        echo
        echo "Cache sizes:"
        ${du} -sh "${paths.piNpmDir}" "${paths.learningDir}/.pi/npm" "''${PI_WORK_DIR:-${paths.workDir}}/.pi/npm" 2>/dev/null || true
        echo
        echo "Use 'pi-admin doctor' for verbose diagnostics and 'pi-admin drift' for source/runtime drift."
        ;;
      sync)
        target="''${1:-current}"
        case "$target" in
          global)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            write_state_stamp
            ;;
          study)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            ${scripts.piStudyInit}/bin/pi-study-init
            write_state_stamp
            ;;
          study-tutor|tutor)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            ${scripts.piStudyTutorInit}/bin/pi-study-tutor-init
            write_state_stamp
            ;;
          work)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            ${scripts.piWorkInit}/bin/pi-work-init
            write_state_stamp
            ;;
          all)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            ${scripts.piStudyInit}/bin/pi-study-init
            if [ -n "''${PI_WORK_DIR:-}" ]; then
              ${scripts.piWorkInit}/bin/pi-work-init
            else
              echo "Skipping work sync because PI_WORK_DIR is not set."
            fi
            write_state_stamp
            ;;
          current)
            ${scripts.piBootstrap}/bin/pi-bootstrap
            mode="$(detect_mode)"
            case "$mode" in
              study) ${scripts.piStudyInit}/bin/pi-study-init ;;
              work)
                if ${git} rev-parse --show-toplevel >/dev/null 2>&1; then
                  export PI_WORK_DIR="$(${git} rev-parse --show-toplevel)"
                  ${scripts.piWorkInit}/bin/pi-work-init
                fi
                ;;
              *) : ;;
            esac
            write_state_stamp
            ;;
          *)
            echo "Unknown sync target: $target" >&2
            usage >&2
            exit 2
            ;;
        esac
        ;;
      doctor)
        exec ${scripts.piDoctor}/bin/pi-doctor "$@"
        ;;
      source-check)
        exec ${scripts.piSourceCheck}/bin/pi-source-check "$@"
        ;;
      drift)
        exec ${scripts.piDriftCheck}/bin/pi-drift-check "$@"
        ;;
      compat)
        exec ${scripts.piCompatCheck}/bin/pi-compat-check "$@"
        ;;
      security)
        ${cat} <<'EOF'
Pi security summary

- Plain `pi` is the daily smart launcher, not a sandbox.
- `pi-cautious` / `PI_PROFILE=cautious pi` is policy-backed convenience only; `pi-readonly` and `pi-safe` are compatibility aliases.
- Historical symlink tests showed policy-only external-directory checks can be bypassed if paths are checked textually instead of canonically.
- Do not use cautious mode as a security boundary for untrusted repositories.
- Real isolation requires canonical path checks and/or OS-level sandboxing such as bubblewrap/pi-sandbox after audit.
- Read docs: modules/programs/cli/pi/docs/SECURITY.md and SECURITY_LIMITATIONS.md
EOF
        ;;
      *)
        echo "Unknown pi-admin command: $cmd" >&2
        usage >&2
        exit 2
        ;;
    esac
  '';
in
{
  inherit piSmart piRaw piAdmin piReadonly piCautious piSafe piNixos piStudy piStudyTutor piWork piResearch piTrusted;
}
