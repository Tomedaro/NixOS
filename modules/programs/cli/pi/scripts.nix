{
  pkgs,
  lib,
  paths,
  piWrapped,
  piNpm,
  engramPackage,
}:

let
  jq = "${pkgs.jq}/bin/jq";
  chmod = "${pkgs.coreutils}/bin/chmod";
  cp = "${pkgs.coreutils}/bin/cp";
  cmp = "${pkgs.diffutils}/bin/cmp";
  date = "${pkgs.coreutils}/bin/date";
  dirname = "${pkgs.coreutils}/bin/dirname";
  du = "${pkgs.coreutils}/bin/du";
  find = "${pkgs.findutils}/bin/find";
  grep = "${pkgs.gnugrep}/bin/grep";
  head = "${pkgs.coreutils}/bin/head";
  install = "${pkgs.coreutils}/bin/install";
  mkdir = "${pkgs.coreutils}/bin/mkdir";
  mktemp = "${pkgs.coreutils}/bin/mktemp";
  mv = "${pkgs.coreutils}/bin/mv";
  rm = "${pkgs.coreutils}/bin/rm";
  sed = "${pkgs.gnused}/bin/sed";
  sort = "${pkgs.coreutils}/bin/sort";
  realpath = "${pkgs.coreutils}/bin/realpath";
  python3 = "${pkgs.python3}/bin/python3";
  tr = "${pkgs.coreutils}/bin/tr";

  jsoncStrip = pkgs.writeText "jsonc-strip.py" ''
    import json
    import sys

    text = sys.stdin.read()
    out = []
    i = 0
    n = len(text)
    in_string = False
    escape = False

    while i < n:
        ch = text[i]

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            i += 2
            while i < n and text[i] not in ('\n', '\r'):
                i += 1
            continue

        if ch == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            closed = False
            while i + 1 < n:
                if text[i] == '*' and text[i + 1] == '/':
                    i += 2
                    closed = True
                    break
                i += 1
            if not closed:
                sys.exit(1)
            continue

        out.append(ch)
        i += 1

    stripped = "".join(out).strip()
    if not stripped:
        sys.exit(1)

    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        sys.exit(1)
  '';

  srcGlobalSettings = ./settings/global.json;
  srcDeepseekProvider = ./settings/deepseek-provider.json;
  srcStudyOverlay = ./settings/study.overlay.json;
  srcStudyTutorOverlay = ./settings/study-tutor.overlay.json;
  srcWorkOverlay = ./settings/work.overlay.json;
  srcMcp = ./mcp/global.json;
  srcNixosMcp = ./mcp/nixos.json;
  srcStudyMcp = ./mcp/study.json;
  srcGlobalAgents = ./resources/global/AGENTS.md;
  srcSimplifyConventions = ./resources/global/simplify-conventions.md;
  srcPolicies = ./policies;
  srcPermissionExtensionConfig = ./extensions/pi-permission-system/config.json;
  srcLeanCtxExtensionConfig = ./extensions/pi-lean-ctx/config.json;
  srcHermesConfig = ./settings/hermes-memory-config.json;
  srcStudyManaged = ./resources/study/managed;
  srcStudySeed = ./resources/study/seed;
  srcWorkManaged = ./resources/work/managed;
  srcWorkSeed = ./resources/work/seed;

  composeSettingsJq = ''
    def npm_package_name:
      sub("^npm:"; "")
      | if startswith("@")
        then (try capture("^(?<name>@[^@/]+/[^@]+)(@.*)?$").name catch .)
        else (try capture("^(?<name>[^@]+)(@.*)?$").name catch .)
        end;
    def package_key:
      if type == "object" then
        (.source // tostring) as $s
        | if ($s | startswith("npm:")) then ($s | npm_package_name) else $s end
      elif type == "string" and startswith("npm:") then
        npm_package_name
      else
        .
      end;
    def stable_package_merge($base; $extra):
      reduce (($base // []) + ($extra // []))[] as $p
        ({seen: {}, out: []};
          ($p | package_key) as $k
          | if .seen[$k]
            then .
            else .seen[$k] = true | .out += [$p]
            end
        ) | .out;
    .[0] as $base
    | .[1] as $overlay
    | ($base * ($overlay | del(.extraPackages)))
    | .packages = stable_package_merge($base.packages; $overlay.extraPackages)
  '';

  commonShell = ''
    set -euo pipefail

    backup_file_once() {
      local f="$1"
      if [ -f "$f" ] && [ ! -f "$f.before-pi-nix" ]; then
        ${cp} "$f" "$f.before-pi-nix"
      fi
    }

    install_managed_file() {
      local src="$1"
      local dst="$2"
      local mode="''${3:-0644}"
      ${mkdir} -p "$(${dirname} "$dst")"
      backup_file_once "$dst"
      ${install} -m "$mode" "$src" "$dst"
    }

    compose_project_settings() {
      local overlay="$1"
      local dst="$2"
      local tmp
      tmp="$(${mktemp})"
      ${jq} -s '${composeSettingsJq}' "${srcGlobalSettings}" "$overlay" > "$tmp"
      ${mkdir} -p "$(${dirname} "$dst")"
      backup_file_once "$dst"
      ${install} -m 0600 "$tmp" "$dst"
      ${rm} -f "$tmp"
    }

    sync_managed_tree() {
      local src="$1"
      local dst="$2"
      local manifest="$3"
      local tmp_manifest ts stale
      ${mkdir} -p "$dst" "$(${dirname} "$manifest")"
      tmp_manifest="$(${mktemp})"

      (cd "$src" && ${find} . -type f | ${sort}) | while IFS= read -r rel; do
        rel="''${rel#./}"
        ${mkdir} -p "$dst/$(${dirname} "$rel")"
        backup_file_once "$dst/$rel"
        ${install} -m 0644 "$src/$rel" "$dst/$rel"
        printf '%s\n' "$rel" >> "$tmp_manifest"
      done

      if [ -f "$manifest" ]; then
        ts="$(${date} -u +%Y%m%dT%H%M%SZ)"
        while IFS= read -r rel; do
          [ -n "$rel" ] || continue
          if ! ${grep} -Fxq "$rel" "$tmp_manifest" && [ -f "$dst/$rel" ]; then
            stale="$dst/.pi/managed-stale/$rel.$ts"
            ${mkdir} -p "$(${dirname} "$stale")"
            ${mv} "$dst/$rel" "$stale"
            echo "Moved stale managed file to $stale"
          fi
        done < "$manifest"
      fi

      ${install} -m 0644 "$tmp_manifest" "$manifest"
      ${rm} -f "$tmp_manifest"
    }

    seed_tree() {
      local src="$1"
      local dst="$2"
      ${mkdir} -p "$dst"
      (cd "$src" && ${find} . -type f | ${sort}) | while IFS= read -r rel; do
        rel="''${rel#./}"
        if [ ! -f "$dst/$rel" ]; then
          ${mkdir} -p "$dst/$(${dirname} "$rel")"
          ${install} -m 0644 "$src/$rel" "$dst/$rel"
        fi
      done
    }
  '';

  piBootstrap = pkgs.writeShellScriptBin "pi-bootstrap" ''
    ${commonShell}

    agent_dir="${paths.piAgentDir}"
    ${mkdir} -p \
      "$agent_dir/npm/bin" \
      "$agent_dir/sessions" \
      "$agent_dir/readonly-workspace" \
      "$agent_dir/policies/safe" \
      "$agent_dir/policies/nixos" \
      "$agent_dir/policies/study" \
      "$agent_dir/policies/work" \
      "$agent_dir/policies/research" \
      "$agent_dir/policies/trusted"

    install_managed_file "${srcGlobalSettings}" "$agent_dir/settings.json" 0600
    install_managed_file "${srcMcp}" "$agent_dir/mcp.json" 0644

    ${mkdir} -p "$agent_dir/mcp"
    install_managed_file "${srcMcp}" "$agent_dir/mcp/global.json" 0644
    install_managed_file "${srcNixosMcp}" "$agent_dir/mcp/nixos.json" 0644
    install_managed_file "${srcStudyMcp}" "$agent_dir/mcp/study.json" 0644
    printf '{"mcpServers":{}}\n' > "$agent_dir/mcp/work.json"
    printf '{"mcpServers":{}}\n' > "$agent_dir/mcp/research.json"
    install_managed_file "${srcGlobalAgents}" "$agent_dir/AGENTS.md" 0644
    install_managed_file "${srcSimplifyConventions}" "$agent_dir/simplify-conventions.md" 0644
    install_managed_file "${srcPermissionExtensionConfig}" "$agent_dir/extensions/pi-permission-system/config.json" 0644
    install_managed_file "${srcLeanCtxExtensionConfig}" "$agent_dir/extensions/pi-lean-ctx/config.json" 0644
    install_managed_file "${srcHermesConfig}" "$agent_dir/hermes-memory-config.json" 0644

    for profile in safe nixos study work research trusted; do
      install_managed_file "${srcPolicies}/$profile.jsonc" "$agent_dir/policies/$profile/pi-permissions.jsonc" 0644
    done

    models="$agent_dir/models.json"
    backup_file_once "$models"
    if [ ! -f "$models" ]; then
      printf '{"providers":{}}\n' > "$models"
    fi

    tmp_models="$(${mktemp})"
    ${jq} --slurpfile deepseek "${srcDeepseekProvider}" '
      .providers = (.providers // {})
      | .providers.deepseek = $deepseek[0]
    ' "$models" > "$tmp_models"
    ${mv} "$tmp_models" "$models"
    ${chmod} 600 "$models"

    echo "Pi bootstrap complete."
    echo "Synced global settings, policies, MCP, global AGENTS, and DeepSeek provider."
  '';

  piStudyInit = pkgs.writeShellScriptBin "pi-study-init" ''
    ${commonShell}
    quiet=0
    if [ "''${1:-}" = "--quiet" ]; then quiet=1; fi
    learning="''${PI_LEARNING_DIR:-${paths.learningDir}}"
    ${mkdir} -p \
      "$learning/.pi/prompts" \
      "$learning/.pi/skills" \
      "$learning/.pi/sessions" \
      "$learning/vault/10-topics" \
      "$learning/vault/20-daily" \
      "$learning/vault/30-summaries" \
      "$learning/vault/40-exercises" \
      "$learning/vault/50-maps" \
      "$learning/vault/60-sources" \
      "$learning/vault/90-archive"

    compose_project_settings "${srcStudyOverlay}" "$learning/.pi/settings.json"
    sync_managed_tree "${srcStudyManaged}" "$learning" "$learning/.pi/managed-files.txt"
    seed_tree "${srcStudySeed}" "$learning"

    if [ "$quiet" -eq 0 ]; then
      echo "Learning project synced at $learning (local-first profile)."
      echo "First run should be interactive: cd $learning && pi-study"
      echo "If Pi asks to trust the project, use /trust, then restart pi-study."
    fi
  '';

  piStudyTutorInit = pkgs.writeShellScriptBin "pi-study-tutor-init" ''
    ${commonShell}
    quiet=0
    if [ "''${1:-}" = "--quiet" ]; then quiet=1; fi
    learning="''${PI_LEARNING_DIR:-${paths.learningDir}}"
    "${piStudyInit}/bin/pi-study-init" --quiet
    compose_project_settings "${srcStudyTutorOverlay}" "$learning/.pi/settings.json"
    if [ "$quiet" -eq 0 ]; then
      echo "Learning project synced at $learning (tutor profile)."
      echo "First run should be interactive: cd $learning && pi-study-tutor"
    fi
  '';

  piWorkInit = pkgs.writeShellScriptBin "pi-work-init" ''
    ${commonShell}
    quiet=0
    if [ "''${1:-}" = "--quiet" ]; then quiet=1; fi
    if [ -z "''${PI_WORK_DIR:-}" ]; then
      echo "pi-work-init requires PI_WORK_DIR=/path/to/project." >&2
      echo "This avoids accidentally creating ~/Work or writing .pi files into the wrong repo." >&2
      exit 2
    fi
    work="$PI_WORK_DIR"
    if [ ! -d "$work" ]; then
      echo "PI_WORK_DIR must point to an existing project directory: $work" >&2
      echo "This prevents typo paths from creating accidental workspaces." >&2
      exit 2
    fi
    work="$(${realpath} -m "$work")"
    nixos_repo="$(${realpath} -m "${paths.nixosRepo}")"
    if [ "$work" = "$nixos_repo" ] && [ "''${PI_WORK_ALLOW_NIXOS:-0}" != "1" ]; then
      echo "Refusing to initialize work resources inside $nixos_repo. Use pi-nixos for the NixOS repo." >&2
      echo "Override only if intentional: PI_WORK_ALLOW_NIXOS=1 PI_WORK_DIR=$nixos_repo pi-work-init" >&2
      exit 2
    fi
    if [ "''${PI_WORK_INIT_ALLOW_EMPTY:-0}" != "1" ] && [ ! -d "$work/.git" ] && [ ! -f "$work/flake.nix" ] && [ ! -f "$work/package.json" ] && [ ! -f "$work/pyproject.toml" ] && [ ! -f "$work/Cargo.toml" ]; then
      echo "PI_WORK_DIR exists but does not look like a project: $work" >&2
      echo "Expected one of: .git, flake.nix, package.json, pyproject.toml, Cargo.toml." >&2
      echo "Override for a new empty project: PI_WORK_INIT_ALLOW_EMPTY=1 PI_WORK_DIR=$work pi-work-init" >&2
      exit 2
    fi
    export PI_WORK_DIR="$work"
    ${mkdir} -p "$work/.pi/prompts" "$work/.pi/skills" "$work/.pi/sessions"
    compose_project_settings "${srcWorkOverlay}" "$work/.pi/settings.json"
    sync_managed_tree "${srcWorkManaged}" "$work" "$work/.pi/managed-files.txt"

    if [ ! -f "$work/AGENTS.md" ]; then
      seed_tree "${srcWorkSeed}" "$work"
    fi

    if [ "$quiet" -eq 0 ]; then
      echo "Work project synced at $work."
      echo "First run should be interactive: PI_WORK_DIR=$work pi-work"
    fi
  '';

  piCompatCheck = pkgs.writeShellScriptBin "pi-compat-check" ''
    set -euo pipefail
    status=0
    warn() { echo "WARN: $1"; status=1; }
    ok() { echo "OK: $1"; }

    echo "Pi compatibility check"
    echo

    version="$(${pkgs.coreutils}/bin/timeout 10 ${piWrapped}/bin/pi --version 2>/dev/null || true)"
    if [ -n "$version" ]; then
      echo "Pi version: $version"
    else
      warn "pi --version did not return a version"
    fi

    help="$(${pkgs.coreutils}/bin/timeout 15 ${piWrapped}/bin/pi --help 2>/dev/null || true)"
    check_help_flag() {
      local flag="$1"
      if printf '%s\n' "$help" | ${grep} -F -- "$flag" >/dev/null; then
        ok "Pi CLI supports $flag"
      else
        warn "Pi CLI help does not mention $flag; wrappers may need adjustment"
      fi
    }

    check_help_flag "--offline"
    check_help_flag "--no-context-files"
    check_help_flag "--no-extensions"
    check_help_flag "--no-skills"
    check_help_flag "--no-prompt-templates"
    check_help_flag "--no-themes"
    check_help_flag "--extension"
    check_help_flag "--tools"
    check_help_flag "--prompt-template"
    check_help_flag "--skill"
    check_help_flag "--session-dir"

    echo
    echo "Pinned control package specs:"
    while IFS= read -r spec; do
      case "$spec" in
        npm:*)
          pkg="''${spec#npm:}"
          printf '  %s\n' "$pkg"
          ;;
      esac
    done < <(${jq} -r '
      .packages[]
      | if type == "object" then .source else . end
    ' "${srcGlobalSettings}")

    echo
    echo "Installed package versions, if present:"
    while IFS= read -r spec; do
      case "$spec" in
        npm:*)
          pkg="''${spec#npm:}"
          name="$pkg"
          case "$pkg" in
            @*) name="''${pkg%@*}" ;;
            *@*) name="''${pkg%@*}" ;;
          esac
          pkg_json="${paths.piNpmDir}/node_modules/$name/package.json"
          if [ -f "$pkg_json" ]; then
            actual="$(${jq} -r '.version // "unknown"' "$pkg_json" 2>/dev/null || echo unknown)"
            expected="$pkg"
            expected="''${expected##*@}"
            if [ "$expected" = "$actual" ]; then
              ok "$name@$actual installed"
            else
              warn "$name installed version $actual does not match pinned spec $pkg"
            fi
            peer="$(${jq} -c '.peerDependencies // {}' "$pkg_json" 2>/dev/null || echo '{}')"
            if [ "$peer" != "{}" ]; then
              echo "    peerDependencies: $peer"
            fi
          else
            warn "$name is not installed under ${paths.piNpmDir}/node_modules; run a managed Pi profile once or run pi update --extensions before relying on wrappers that load this package"
          fi
          ;;
      esac
    done < <(${jq} -r '
      .packages[]
      | if type == "object" then .source else . end
    ' "${srcGlobalSettings}")

    echo
    echo "Optional online npm metadata check:"
    echo "  Run with PI_COMPAT_ONLINE=1 to query npm for pinned package metadata."
    if [ "''${PI_COMPAT_ONLINE:-0}" = "1" ]; then
      while IFS= read -r spec; do
        case "$spec" in
          npm:*)
            pkg="''${spec#npm:}"
            echo "--- npm view $pkg"
            tmp_meta="$(${mktemp})"
            if "${piNpm}/bin/pi-npm" view "$pkg" version peerDependencies --json > "$tmp_meta" 2>/dev/null; then
              ${head} -c 4000 "$tmp_meta"
              echo
            else
              warn "npm metadata query failed for $pkg"
            fi
            ${rm} -f "$tmp_meta"
            ;;
        esac
      done < <(${jq} -r '
        .packages[]
        | if type == "object" then .source else . end
      ' "${srcGlobalSettings}")
    fi

    echo
    if [ "$status" -eq 0 ]; then
      echo "Compatibility check completed without warnings."
    else
      echo "Compatibility check completed with warnings. Review before relying on this setup."
    fi
    exit "$status"
  '';

  piDoctor = pkgs.writeShellScriptBin "pi-doctor" ''
    set -euo pipefail
    echo "Pi doctor"
    echo
    echo "Pi version:"
    ${piWrapped}/bin/pi --version 2>/dev/null || true
    echo
    echo "Commands:"
    doctor_status=0
    hermes_status=0
    missing_commands=0
    for cmd in \
      pi pi-raw pi-admin \
      pi-readonly pi-cautious pi-safe \
      pi-nixos pi-study pi-study-tutor pi-work pi-research pi-trusted \
      pi-bootstrap pi-study-init pi-study-tutor-init pi-work-init \
      pi-doctor pi-hermes-doctor pi-drift-check pi-compat-check pi-source-check pi-npm \
    ; do
      printf '%-24s ' "$cmd"
      if command_path="$(command -v "$cmd" 2>/dev/null)"; then
        echo "$command_path"
      else
        echo "MISSING"
        doctor_status=1
        missing_commands=$((missing_commands + 1))
      fi
    done
    echo
    echo "Policy files:"
    ${find} "${paths.piPoliciesDir}" -maxdepth 3 -type f -name 'pi-permissions.jsonc' 2>/dev/null | ${sort} || true
    echo
    echo "Global settings managed keys:"
    ${jq} '{defaultProvider,defaultModel,defaultThinkingLevel,packages,theme,powerline,workingVibe,compaction}' "${paths.piAgentDir}/settings.json" 2>/dev/null || true
    echo
    echo "DeepSeek provider models:"
    ${jq} -r '.providers.deepseek.models[].id?' "${paths.piAgentDir}/models.json" 2>/dev/null || true
    echo
    echo "Package cache sizes:"
    ${du} -sh "${paths.piNpmDir}" "${paths.learningDir}/.pi/npm" "''${PI_WORK_DIR:-${paths.workDir}}/.pi/npm" 2>/dev/null || true
    echo
    if [ -d "${paths.learningDir}/.pi/npm/node_modules" ]; then
      echo "Warning: ${paths.learningDir}/.pi/npm exists. Wrappers no longer force a shared package dir; this may be a stale project npm cache."
    fi
    if [ -n "''${PI_WORK_DIR:-}" ] && [ -d "$PI_WORK_DIR/.pi/npm/node_modules" ]; then
      echo "Warning: $PI_WORK_DIR/.pi/npm exists. Wrappers no longer force a shared package dir; this may be a stale project npm cache."
    fi
    if [ -e "${paths.nixosRepo}/.pi/settings.json" ] || [ -e "${paths.nixosRepo}/.pi/prompts" ] || [ -e "${paths.nixosRepo}/.pi/skills" ]; then
      echo "Warning: ${paths.nixosRepo}/.pi contains project resources. pi-work should not manage the NixOS repo; use pi-nixos."
    fi
    echo
    echo "Study settings resource paths:"
    ${jq} '{prompts,skills,packages}' "${paths.learningDir}/.pi/settings.json" 2>/dev/null || true
    echo
    echo "Trust note: first run of pi-study/pi-work should be interactive. If Pi asks, use /trust and restart the wrapper before relying on -p/non-interactive mode."
    echo "Cautious note: pi-cautious is the preferred command for policy-backed cautious mode. pi-readonly/pi-safe remain compatibility aliases. Cautious mode launches in an empty workspace and is still not an OS/network sandbox."
    echo "Source-management note: use plain pi for daily work and pi-admin for maintenance. Do not use pi install/remove/config for durable setup changes. Edit modules/programs/cli/pi source and resync with pi-admin sync. Run pi-admin compat after package/version changes."
    echo
    if [ "$missing_commands" -gt 0 ]; then
      echo "Doctor failed: $missing_commands expected command(s) missing."
      exit "$doctor_status"
    fi

    echo
    echo "=== Hermes Memory ==="
    pi-hermes-doctor 2>&1 | sed 's/^/  /' || hermes_status=$?

    echo
    echo "=== Engram Memory ==="
    engram_bin="''${ENGRAM_BIN:-${engramPackage}/bin/engram}"
    engram_data_dir="''${ENGRAM_DATA_DIR:-$HOME/.engram}"
    echo "  ENGRAM_BIN: $engram_bin"
    if [ -x "$engram_bin" ] || [ -f "$engram_bin" ]; then
      echo "  ENGRAM_BIN exists: yes"
      echo "  engram version:"
      "$engram_bin" version 2>&1 | sed 's/^/    /' || echo "    (version command failed)"
    else
      echo "  ENGRAM_BIN exists: no"
    fi
    echo "  ENGRAM_DATA_DIR: $engram_data_dir"

    echo
    for pkg in gentle-engram pi-mcp-adapter; do
      echo "  $pkg in source settings:"
      ${jq} -r '(.packages[] | select(type == "string" and contains("'"$pkg"'"))) // "not found"' "${srcGlobalSettings}" 2>/dev/null | sed 's/^/    /' || echo "    (could not read settings)"
    done

    for pkg in gentle-engram pi-mcp-adapter; do
      echo "  $pkg installed:"
      if [ -f "${paths.piNpmDir}/node_modules/$pkg/package.json" ]; then
        ${jq} -r '"    " + .name + "@" + .version' "${paths.piNpmDir}/node_modules/$pkg/package.json" 2>/dev/null || echo "    (could not read)"
      else
        echo "    not installed"
      fi
    done

    echo "  Source MCP configs contain engram:"
    for mcpf in "${paths.piSourceDir}/mcp/global.json" "${paths.piSourceDir}/mcp/nixos.json"; do
      if [ -f "$mcpf" ]; then
        if ${jq} -e '.mcpServers.engram' "$mcpf" >/dev/null 2>&1; then
          echo "    $(basename "$mcpf"): yes"
        else
          echo "    $(basename "$mcpf"): no"
        fi
      else
        echo "    $(basename "$mcpf"): file missing"
      fi
    done

    if [ -d "$PWD/.engram" ]; then
      if [ -f "$PWD/.engram/config.json" ]; then
        proj_name="$(${jq} -r '.project_name // "(unknown)"' "$PWD/.engram/config.json" 2>/dev/null || echo "(parse error)")"
        echo "  .engram/config.json: present (project: $proj_name)"
      else
        echo "  .engram/config.json: missing (directory exists but no config)"
      fi
    else
      echo "  .engram/config.json: missing"
    fi

    if [ -f "$HOME/.engram/engram.db" ]; then
      echo "  ~/.engram/engram.db: present"
    else
      echo "  ~/.engram/engram.db: not yet created (normal before first use)"
    fi

    if [ "$hermes_status" -gt 0 ]; then
      echo "Doctor completed with Hermes issues."
      exit "$hermes_status"
    fi

    echo "Doctor complete."
  '';

  piDriftCheck = pkgs.writeShellScriptBin "pi-drift-check" ''
    set -euo pipefail
    status=0

    fail() { echo "DRIFT: $1"; status=1; }
    ok() { echo "OK: $1"; }

    compare_file() {
      local label="$1" src="$2" dst="$3"
      if [ ! -f "$dst" ]; then fail "$label missing: $dst"; return; fi
      if ${cmp} -s "$src" "$dst"; then ok "$label"; else fail "$label differs"; fi
    }

    compare_settings_managed_keys() {
      local label="$1" src="$2" dst="$3"
      local filter='{
        defaultProvider, defaultModel, defaultThinkingLevel, thinkingBudgets, hideThinkingBlock,
        enableInstallTelemetry, quietStartup, treeFilterMode, npmCommand, compaction,
        branchSummary, retry, steeringMode, followUpMode, enabledModels, packages,
        workingVibe, powerline, theme, prompts, skills, enableSkillCommands, profileName
      } | with_entries(select(.value != null))'
      if [ ! -f "$dst" ]; then fail "$label missing: $dst"; return; fi
      a="$(${mktemp})"; b="$(${mktemp})"
      ${jq} "$filter" "$src" > "$a"
      ${jq} "$filter" "$dst" > "$b"
      if ${cmp} -s "$a" "$b"; then ok "$label managed keys"; else fail "$label managed keys differ"; fi
      ${rm} -f "$a" "$b"
    }

    compare_deepseek() {
      local src="${srcDeepseekProvider}" dst="${paths.piAgentDir}/models.json"
      if [ ! -f "$dst" ]; then fail "models.json missing"; return; fi
      a="$(${mktemp})"; b="$(${mktemp})"
      ${jq} '.' "$src" > "$a"
      ${jq} '.providers.deepseek' "$dst" > "$b"
      if ${cmp} -s "$a" "$b"; then ok "DeepSeek provider subtree"; else fail "DeepSeek provider subtree differs"; fi
      ${rm} -f "$a" "$b"
    }

    compose_expected_settings() {
      local overlay="$1" out="$2"
      ${jq} -s '${composeSettingsJq}' "${srcGlobalSettings}" "$overlay" > "$out"
    }

    compare_managed_tree() {
      local label="$1" src="$2" dst="$3" manifest="$4"
      local source_manifest tree_status
      tree_status=0
      tree_fail() { fail "$1"; tree_status=1; }
      source_manifest="$(${mktemp})"
      (cd "$src" && ${find} . -type f | ${sort} | ${sed} 's#^./##') > "$source_manifest"

      while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        if [ ! -f "$dst/$rel" ]; then tree_fail "$label missing runtime file: $rel"; continue; fi
        if ! ${cmp} -s "$src/$rel" "$dst/$rel"; then tree_fail "$label differs: $rel"; fi
      done < "$source_manifest"

      if [ -f "$manifest" ]; then
        while IFS= read -r rel; do
          [ -n "$rel" ] || continue
          if ! ${grep} -Fxq "$rel" "$source_manifest"; then
            tree_fail "$label stale managed file listed in runtime manifest: $rel"
          fi
        done < "$manifest"
      else
        tree_fail "$label manifest missing: $manifest"
      fi

      if [ -d "$dst/.pi/managed-stale" ] && [ -n "$(${find} "$dst/.pi/managed-stale" -type f -print -quit 2>/dev/null || true)" ]; then
        tree_fail "$label has stale managed files under $dst/.pi/managed-stale"
      fi

      ${rm} -f "$source_manifest"
      if [ "$tree_status" -eq 0 ]; then
        ok "$label managed tree checked"
      else
        echo "DRIFT: $label managed tree has issues"
      fi
    }

    compare_settings_managed_keys "global settings" "${srcGlobalSettings}" "${paths.piAgentDir}/settings.json"
    compare_file "global MCP" "${srcMcp}" "${paths.piAgentDir}/mcp.json"

    # Verify profile-specific MCP configs
    for pf in global nixos study work research; do
      src_mcp="${paths.piSourceDir}/mcp/$pf.json"
      dst_mcp="${paths.piAgentDir}/mcp/$pf.json"
      if [ -f "$src_mcp" ]; then
        compare_file "profile MCP ($pf)" "$src_mcp" "$dst_mcp"
      elif [ -f "$dst_mcp" ]; then
        echo "DRIFT: profile MCP ($pf) source missing but runtime file exists at $dst_mcp"
      fi
    done

    compare_file "global AGENTS" "${srcGlobalAgents}" "${paths.piAgentDir}/AGENTS.md"
    compare_file "global simplify conventions" "${srcSimplifyConventions}" "${paths.piAgentDir}/simplify-conventions.md"
    compare_file "permission extension config" "${srcPermissionExtensionConfig}" "${paths.piAgentDir}/extensions/pi-permission-system/config.json"
    compare_file "lean-ctx extension config" "${srcLeanCtxExtensionConfig}" "${paths.piAgentDir}/extensions/pi-lean-ctx/config.json"
    compare_file "Hermes config" "${srcHermesConfig}" "${paths.piAgentDir}/hermes-memory-config.json"

    for profile in safe nixos study work research trusted; do
      compare_file "policy $profile" "${srcPolicies}/$profile.jsonc" "${paths.piPoliciesDir}/$profile/pi-permissions.jsonc"
    done
    compare_deepseek

    if [ -f "${paths.learningDir}/.pi/settings.json" ]; then
      profile="$(${jq} -r '.profileName // "study"' "${paths.learningDir}/.pi/settings.json" 2>/dev/null || echo study)"
      tmp="$(${mktemp})"
      case "$profile" in
        study-tutor)
          compose_expected_settings "${srcStudyTutorOverlay}" "$tmp"
          compare_settings_managed_keys "study-tutor settings" "$tmp" "${paths.learningDir}/.pi/settings.json"
          ;;
        study|*)
          compose_expected_settings "${srcStudyOverlay}" "$tmp"
          compare_settings_managed_keys "study settings" "$tmp" "${paths.learningDir}/.pi/settings.json"
          ;;
      esac
      ${rm} -f "$tmp"
      compare_managed_tree "study resources" "${srcStudyManaged}" "${paths.learningDir}" "${paths.learningDir}/.pi/managed-files.txt"
    else
      echo "SKIP: study settings not initialized"
    fi

    work="''${PI_WORK_DIR:-}"
    if [ -z "$work" ]; then
      echo "SKIP: work settings not checked because PI_WORK_DIR is not set"
    elif [ -f "$work/.pi/settings.json" ]; then
      tmp="$(${mktemp})"
      compose_expected_settings "${srcWorkOverlay}" "$tmp"
      compare_settings_managed_keys "work settings" "$tmp" "$work/.pi/settings.json"
      ${rm} -f "$tmp"
      compare_managed_tree "work resources" "${srcWorkManaged}" "$work" "$work/.pi/managed-files.txt"
    else
      echo "SKIP: work settings not initialized at $work"
    fi

    exit "$status"
  '';

  piSourceCheck = pkgs.writeShellScriptBin "pi-source-check" ''
        set -uo pipefail

        src="''${PI_SOURCE_ROOT:-${paths.piSourceDir}}"
        checks=0
        failures=0
        wrapper_profiles=""
        bootstrap_profiles=""

        ok() { echo "OK: $1"; checks=$((checks + 1)); }
        fail() { echo "FAIL: $1"; checks=$((checks + 1)); failures=$((failures + 1)); }
        warn() { echo "WARN: $1"; }

        parse_npm_spec() {
          local spec="$1"
          local rest name version

          case "$spec" in
            npm:*) ;;
            *) return 1 ;;
          esac

          rest="''${spec#npm:}"

          case "$rest" in
            @*/*@*)
              name="''${rest%@*}"
              version="''${rest##*@}"
              ;;
            *@*)
              name="''${rest%@*}"
              version="''${rest##*@}"
              case "$name" in
                @*) return 1 ;;
              esac
              ;;
            *)
              return 1
              ;;
          esac

          [ -n "$name" ] || return 1
          [ -n "$version" ] || return 1

          case "$name" in
            @*/*)
              case "$name" in
                *@*@*) return 1 ;;
              esac
              ;;
            @*) return 1 ;;
            *)
              case "$name" in
                */*) return 1 ;;
              esac
              ;;
          esac

          case "$name" in
            *[[:space:]]*) return 1 ;;
          esac

          case "$version" in
            *[[:space:]]*) return 1 ;;
            *@*) return 1 ;;
          esac

          return 0
        }

        if [ ! -d "$src" ]; then
          echo "FAIL: source root not found: $src"
          echo "Source check failed: 1 check, 1 failure."
          exit 1
        fi

        # ── 1. Validate settings/*.json ──────────────────────────
        settings_dir="$src/settings"
        shopt -s nullglob
        json_files=("$settings_dir"/*.json)
        shopt -u nullglob
        if [ ''${#json_files[@]} -eq 0 ]; then
          fail "no settings/*.json files found under $settings_dir"
        else
          for f in "$settings_dir"/*.json; do
            if ${jq} -e . "$f" >/dev/null 2>&1; then
              ok "$(basename "$f") is valid JSON"
            else
              fail "$(basename "$f") is invalid JSON"
            fi
          done
        fi

        # ── 2. Validate all MCP JSON configs ─────────────────────
        shopt -s nullglob
        mcp_files=("$src/mcp/"*.json)
        shopt -u nullglob
        if [ ''${#mcp_files[@]} -eq 0 ]; then
          fail "no MCP JSON configs found under $src/mcp/"
        else
          for mcp_file in "''${mcp_files[@]}"; do
            base="$(basename "$mcp_file")"
            if ${jq} -e . "$mcp_file" >/dev/null 2>&1; then
              ok "mcp/$base is valid JSON"
            else
              fail "mcp/$base is invalid JSON"
            fi
          done
        fi

        # ── 3. Validate docs/LOOKUP.json ──────────────────────────
        lookup="$src/docs/LOOKUP.json"
        if [ -f "$lookup" ]; then
          if ${jq} -e . "$lookup" >/dev/null 2>&1; then
            ok "docs/LOOKUP.json is valid JSON"
          else
            fail "docs/LOOKUP.json is invalid JSON"
          fi
          while IFS= read -r rel; do
            case "$rel" in
              /*)
                fail "LOOKUP.json contains absolute path: $rel"
                continue
                ;;
              *..*)
                fail "LOOKUP.json contains parent traversal: $rel"
                continue
                ;;
            esac
            if [ -e "$src/$rel" ] || [ -d "$src/$rel" ]; then
              ok "LOOKUP path exists: $rel"
            else
              fail "LOOKUP path missing: $rel"
            fi
          done < <(${jq} -r '.. | strings' "$lookup" 2>/dev/null || true)
        else
          fail "LOOKUP config missing: docs/LOOKUP.json"
        fi

        # ── 4. Validate policies/*.jsonc ──────────────────────────
        policies_dir="$src/policies"
        if [ -d "$policies_dir" ]; then
          shopt -s nullglob
          policy_files=("$policies_dir"/*.jsonc)
          shopt -u nullglob
          if [ ''${#policy_files[@]} -eq 0 ]; then
            fail "no policies/*.jsonc files found under $policies_dir"
          else
            for pf in "$policies_dir"/*.jsonc; do
              if ${python3} ${jsoncStrip} < "$pf" 2>/dev/null; then
                ok "$(basename "$pf") parses after comment stripping"
              else
                fail "policy JSONC does not parse after comment stripping: $(basename "$pf")"
              fi
            done
          fi
        else
          fail "policies directory missing: policies/"
        fi

        # ── 5. Check every wrapper policy profile has a source file ──
        scripts_file="$src/scripts.nix"
        wrappers_file="$src/wrappers.nix"
        if [ -f "$wrappers_file" ]; then
          wrapper_profiles="$(${grep} -Eo 'wrapperPrelude "[^"]+"' "$wrappers_file" | ${sed} -E 's/.*"([^"]+)".*/\1/' | ${sort} -u)"
          if [ -z "$wrapper_profiles" ]; then
            fail "could not detect any wrapperPrelude policy profiles in wrappers.nix"
          else
            while IFS= read -r profile; do
              if [ -f "$policies_dir/$profile.jsonc" ]; then
                ok "wrapper profile $profile has source: policies/$profile.jsonc"
              else
                fail "wrapper policy profile missing source file: policies/$profile.jsonc"
              fi
            done <<< "$wrapper_profiles"
          fi
        else
          fail "wrappers.nix not found in source tree"
        fi

        # ── 6. Check every wrapper profile is synced by pi-bootstrap ──
        if [ -z "$wrapper_profiles" ]; then
          : # skip bootstrap comparison when no wrapper profiles detected
        elif [ -f "$scripts_file" ]; then
          bootstrap_block="$(
            ${sed} -n '/piBootstrap = pkgs.writeShellScriptBin "pi-bootstrap"/,/piStudyInit = pkgs.writeShellScriptBin "pi-study-init"/p' "$scripts_file" 2>/dev/null || true
          )"
          if [ -n "$bootstrap_block" ]; then
            bootstrap_profiles="$(
              printf '%s\n' "$bootstrap_block" \
                | ${sed} -nE 's/^[[:space:]]*for profile in ([^;]+); do[[:space:]]*$/\1/p' \
                | ${tr} ' ' '\n' \
                | ${sort} -u
            )"
            if [ -z "$bootstrap_profiles" ]; then
              fail "could not detect pi-bootstrap policy sync loop in scripts.nix"
            else
              while IFS= read -r profile; do
                if printf '%s\n' "$bootstrap_profiles" | ${grep} -Fxq "$profile"; then
                  ok "wrapper profile $profile is synced by pi-bootstrap"
                else
                  fail "wrapper policy profile is not synced by pi-bootstrap: $profile"
                fi
              done <<< "$wrapper_profiles"
            fi
          else
            fail "could not detect pi-bootstrap block in scripts.nix"
          fi
        fi

        # ── 7. Check required resources exist ─────────────────────
        required_files="
    resources/global/AGENTS.md
    resources/nixos/AGENTS.md
    resources/nixos/prompts/pi-change.md
    resources/nixos/prompts/security.md
    resources/nixos/prompts/setup.md
    resources/nixos/prompts/status.md
    resources/nixos/skills/pi-nix-self-maintenance/SKILL.md
    extensions/pi-permission-system/config.json
    "
        for rel in $required_files; do
          if [ -f "$src/$rel" ]; then
            ok "resource file exists: $rel"
          else
            fail "resource file missing: $rel"
          fi
        done

        required_dirs="
    resources/nixos/prompts
    resources/nixos/skills/pi-nix-self-maintenance
    resources/study/managed
    resources/study/seed
    resources/work/managed
    resources/work/seed
    "
        for rel in $required_dirs; do
          if [ -d "$src/$rel" ]; then
            ok "resource directory exists: $rel"
          else
            fail "resource directory missing: $rel"
          fi
        done

        # Check skill directories contain SKILL.md
        for skill_parent in "$src/resources/study/managed/.pi/skills/"* "$src/resources/work/managed/.pi/skills/"* "$src/resources/nixos/skills/"*; do
          [ -d "$skill_parent" ] || continue
          skill_name="$(basename "$skill_parent")"
          if [ -f "$skill_parent/SKILL.md" ]; then
            ok "skill $skill_name has SKILL.md"
          else
            fail "skill missing SKILL.md: $(echo "$skill_parent" | ${sed} "s|^$src/||")"
          fi
        done

        # ── 8. Validate package specs in settings/global.json ─────
        gs="$src/settings/global.json"
        if [ -f "$gs" ]; then
          if ! ${jq} -e '.packages and (.packages | type == "array")' "$gs" >/dev/null 2>&1; then
            fail "settings/global.json must contain packages array"
          else
            pkg_count="$(${jq} '.packages | length' "$gs")"
            i=0
            while [ "$i" -lt "$pkg_count" ]; do
              ptype="$(${jq} -r --argjson i "$i" '.packages[$i] | type' "$gs" 2>/dev/null || echo null)"
              if [ "$ptype" = "object" ]; then
                spec="$(${jq} -r --argjson i "$i" '.packages[$i].source // empty' "$gs" 2>/dev/null || true)"
                if [ -z "$spec" ]; then
                  fail "settings/global.json packages[$i] is missing source/spec"
                  i=$((i + 1))
                  continue
                fi
              elif [ "$ptype" = "string" ]; then
                spec="$(${jq} -r --argjson i "$i" '.packages[$i]' "$gs" 2>/dev/null || true)"
              else
                fail "settings/global.json packages[$i] is missing source/spec"
                i=$((i + 1))
                continue
              fi
              if parse_npm_spec "$spec"; then
                ok "package spec parseable: $spec"
              else
                case "$spec" in
                  npm:*)
                    fail "package spec is not parseable as npm:name@version or npm:@scope/name@version: $spec"
                    ;;
                  *)
                    fail "unsupported package spec in settings/global.json packages[$i]: $spec"
                    ;;
                esac
              fi
              i=$((i + 1))
            done
          fi
        else
          fail "settings/global.json not found"
        fi

        echo
        if [ "$failures" -eq 0 ]; then
          echo "Source check passed: $checks checks, 0 failures."
          exit 0
        else
          echo "Source check failed: $checks checks, $failures failures."
          exit 1
        fi
  '';

  ankiSafeWriter = (import ./anki-safe-writer { inherit pkgs lib; }).ankiSafeWriter;

  piTestAnkiSafeWriter = pkgs.writeShellScriptBin "pi-test-anki-safe-writer" ''
    set -euo pipefail
    src="${paths.piSourceDir}"
    test_file="$src/anki-safe-writer/test_anki_safe_writer.py"
    src_file="$src/anki-safe-writer/anki_safe_writer.py"
    if [ ! -f "$test_file" ]; then
      echo "FAIL: test file not found at $test_file" >&2
      echo "Run from the NixOS repository root." >&2
      exit 1
    fi
    if [ ! -f "$src_file" ]; then
      echo "FAIL: source file not found at $src_file" >&2
      echo "Run from the NixOS repository root." >&2
      exit 1
    fi
    exec ${pkgs.python3}/bin/python3 "$test_file"
  '';

  # ── Hermes Memory Doctor ────────────────────────────────────────
  # Detect Pi's bundled Node by reading the .pi-wrapped wrapper
  piWrappedFile = "${piWrapped}/bin/.pi-wrapped";
  piWrappedContent =
    if builtins.pathExists piWrappedFile then builtins.readFile piWrappedFile else "";
  piNodeMatch = builtins.match ''.*exec "([^"]+)" .*'' piWrappedContent;
  piNode = if piNodeMatch != null then builtins.head piNodeMatch else "${pkgs.nodejs_24}/bin/node";

  piHermesDoctor = pkgs.writeShellScriptBin "pi-hermes-doctor" ''
    set -euo pipefail

    node="${pkgs.nodejs_24}/bin/node"
    pi_node="${piNode}"
    sqlite3="${pkgs.sqlite}/bin/sqlite3"

    hermes_dir="${paths.piAgentDir}/pi-hermes-memory"
    db="$hermes_dir/sessions.db"
    npm_dir="${paths.piNpmDir}"
    backup_dir="${paths.piAgentDir}/../backups"

    status=0
    fail() { echo "HERMES FAIL: $1"; status=1; }
    ok()   { echo "HERMES OK: $1"; }
    warn() { echo "HERMES WARN: $1"; }

    echo "=== Hermes Memory Doctor ==="
    echo

    # 0. Preflight: backup database
    if [ -f "$db" ]; then
      ts=$(${pkgs.coreutils}/bin/date -u +%Y%m%dT%H%M%SZ)
      backup_path="$backup_dir/pi-hermes-memory-$ts"
      ${pkgs.coreutils}/bin/mkdir -p "$backup_path"
      ${pkgs.coreutils}/bin/cp "$db" "$backup_path/sessions.db"
      ${pkgs.coreutils}/bin/cp "$hermes_dir/MEMORY.md" "$backup_path/" 2>/dev/null || true
      ${pkgs.coreutils}/bin/cp "$hermes_dir/USER.md" "$backup_path/" 2>/dev/null || true
      ${pkgs.coreutils}/bin/cp "$hermes_dir/failures.md" "$backup_path/" 2>/dev/null || true
      echo "  Backup: pi-hermes-memory-$ts"

      # Retention: keep last 7 backups
      ${pkgs.findutils}/bin/find "$backup_dir" -maxdepth 1 -type d -name 'pi-hermes-memory-*' \
        | ${pkgs.coreutils}/bin/sort \
        | ${pkgs.coreutils}/bin/head -n -7 \
        | while IFS= read -r old; do ${pkgs.coreutils}/bin/rm -rf "$old"; done 2>/dev/null || true
    else
      warn "No database to back up (yet)"
    fi
    echo

    # 1. Hermes directory
    if [ -d "$hermes_dir" ]; then
      ok "Hermes directory exists at $hermes_dir"
    else
      fail "Hermes directory missing at $hermes_dir"
      echo "ABORT: Hermes directory not found."
      exit 1
    fi

    # 2. Database
    if [ -f "$db" ]; then
      sz=$(${pkgs.coreutils}/bin/stat --format=%s "$db" 2>/dev/null || echo 0)
      echo "  DB size: $sz bytes"
      integrity=$("$sqlite3" "$db" "PRAGMA integrity_check;" 2>/dev/null || echo "error")
      if [ "$integrity" = "ok" ]; then
        ok "Database integrity check passed"
      else
        fail "Database integrity check: $integrity"
      fi

      echo "  Tables:"
      "$sqlite3" "$db" ".tables" 2>/dev/null | ${pkgs.coreutils}/bin/fold -s

      # Data counts
      "$sqlite3" "$db" "
        SELECT 'memories', count(*) FROM memories
        UNION ALL SELECT 'sessions', count(*) FROM sessions
        UNION ALL SELECT 'messages', count(*) FROM messages;
      " 2>/dev/null | while IFS='|' read -r tbl cnt; do
        echo "  $tbl: $cnt"
      done || warn "Could not query table counts"
    else
      fail "Database file missing: $db"
    fi

    # 3. Markdown files
    for f in MEMORY.md USER.md failures.md; do
      if [ -f "$hermes_dir/$f" ]; then
        sz=$(${pkgs.coreutils}/bin/wc -c < "$hermes_dir/$f" 2>/dev/null || echo 0)
        ok "$f exists ($sz bytes)"
      else
        fail "$f missing"
      fi
    done

    # 4. Native addon: better-sqlite3
    bsql3="$npm_dir/node_modules/better-sqlite3"
    if [ -d "$bsql3" ]; then
      ok "better-sqlite3 package directory exists"
      native_node=$(${pkgs.findutils}/bin/find "$bsql3/build/Release" -name 'better_sqlite3.node' -type f 2>/dev/null | ${pkgs.coreutils}/bin/head -1)
      if [ -n "$native_node" ]; then
        sz=$(${pkgs.coreutils}/bin/stat --format=%s "$native_node" 2>/dev/null || echo 0)
        ok "Native .node file exists: $native_node ($sz bytes)"
      else
        fail "No native .node file found under $bsql3/build/Release"
      fi

      # Direct load test with Pi's bundled Node 24
      load_result=$("$pi_node" -e "
        try {
          const Database = require('$bsql3');
          console.log('LOAD_OK:' + (typeof Database));
        } catch(e) {
          console.log('LOAD_FAIL:' + e.message.replace(/\n/g, ' '));
        }
      " 2>/dev/null || echo "NODE_ERROR: node binary not usable")

      echo "  Pi Node version: $($pi_node -e 'console.log(process.version)' 2>/dev/null || echo unknown)"
      case "$load_result" in
        LOAD_OK:*)
          type="''${load_result#LOAD_OK:}"
          ok "better-sqlite3 loads from Pi's Node ($pi_node): $type"
          ;;
        LOAD_FAIL:*)
          err="''${load_result#LOAD_FAIL:}"
          fail "better-sqlite3 load from Pi's Node: $err"
          ;;
        *)
          fail "better-sqlite3 load test: $load_result"
          ;;
      esac

      # Secondary test with system Node (detects ABI drift)
      sys_load=$("$node" -e "
        try {
          const Database = require('$bsql3');
          console.log('SYS_OK');
        } catch(e) {
          console.log('SYS_FAIL:' + e.message.replace(/\n/g, ' '));
        }
      " 2>/dev/null || echo "SYS_NODE_ERROR")

      case "$sys_load" in
        SYS_OK)
          ok "better-sqlite3 also loads from system Node ($node)"
          ;;
        SYS_FAIL:*)
          err="''${sys_load#SYS_FAIL:}"
          warn "better-sqlite3 rejected by system Node $($node -e 'console.log(process.version)' 2>/dev/null || true): $err"
          ;;
        *)
          warn "System Node load test skipped ($sys_load)"
          ;;
      esac
    else
      fail "better-sqlite3 package missing at $bsql3"
    fi

    # 5. Database read test (via Pi's Node 24)
    read_test=$("$pi_node" -e "
      try {
        const Database = require('$bsql3');
        const db = new Database('$db', { readonly: true });
        const row = db.prepare('SELECT COUNT(*) as cnt FROM memories').get();
        console.log('DB_READ_OK: ' + row.cnt + ' memories');
        db.close();
      } catch(e) {
        console.log('DB_READ_FAIL: ' + e.message.replace(/\n/g, ' '));
      }
    " 2>/dev/null || echo "DB_READ_NODE_ERROR")

    case "$read_test" in
      DB_READ_OK:*)
        count="''${read_test#DB_READ_OK:}"
        ok "Database readable via Pi's Node: $count"
        ;;
      *)
        fail "Database read via Pi's Node: $read_test"
        ;;
    esac

    # 6. Pi extension load status (best-effort via existing compat check)
    echo
    echo "  Pi extension status (from compat check):"
    hermes_version=$(${pkgs.jq}/bin/jq -r '
      [.packages[]
       | select(type == "string" and contains("pi-hermes-memory"))
      ][0] // "not-found"
    ' "${paths.piAgentDir}/settings.json" 2>/dev/null || echo "not-found")

    if [ -f "$npm_dir/node_modules/pi-hermes-memory/package.json" ]; then
      installed_ver=$(${pkgs.jq}/bin/jq -r '.version // "unknown"' "$npm_dir/node_modules/pi-hermes-memory/package.json" 2>/dev/null || echo unknown)
      if [ "$hermes_version" != "not-found" ]; then
        expected="''${hermes_version#npm:pi-hermes-memory@}"
        if [ "$expected" = "$installed_ver" ]; then
          ok "pi-hermes-memory@$installed_ver installed (matches pinned version)"
        else
          warn "pi-hermes-memory pinned $expected but installed $installed_ver"
        fi
      else
        ok "pi-hermes-memory@$installed_ver installed"
      fi
    else
      fail "pi-hermes-memory package not installed in npm prefix"
    fi

    # 7. Find most recent backup
    echo
    if [ -d "$backup_dir" ]; then
      latest_backup=$(${pkgs.findutils}/bin/find "$backup_dir" -maxdepth 2 -type d -name 'pi-hermes-memory-*' 2>/dev/null | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/tail -1 || true)
      if [ -n "$latest_backup" ]; then
        echo "  Latest backup: $latest_backup"
        ${pkgs.coreutils}/bin/ls -la "$latest_backup" 2>/dev/null | ${pkgs.coreutils}/bin/head -5
      else
        warn "No Hermes backups found in $backup_dir"
      fi
    else
      warn "No backup directory at $backup_dir"
    fi

    # 8. Check for project memories
    proj_mem="${paths.piAgentDir}/projects-memory"
    if [ -d "$proj_mem" ]; then
      proj_count=$(${pkgs.findutils}/bin/find "$proj_mem" -name 'MEMORY.md' -type f 2>/dev/null | ${pkgs.coreutils}/bin/wc -l)
      ok "Project memories present: $proj_count project(s)"
    fi

    echo
    if [ "$status" -eq 0 ]; then
      echo "Hermes memory doctor: all checks passed."
    else
      echo "Hermes memory doctor: $status check(s) failed."
      echo "Data files and backup are safe. Extension may be in degraded state."
    fi
    exit "$status"
  '';

in
{
  inherit
    piBootstrap
    piStudyInit
    piStudyTutorInit
    piWorkInit
    piCompatCheck
    piDoctor
    piDriftCheck
    piSourceCheck
    ankiSafeWriter
    piTestAnkiSafeWriter
    piHermesDoctor
    ;
}
