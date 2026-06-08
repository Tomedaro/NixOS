{ pkgs, lib, paths, piWrapped, piNpm }:

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

  srcGlobalSettings = ./settings/global.json;
  srcDeepseekProvider = ./settings/deepseek-provider.json;
  srcStudyOverlay = ./settings/study.overlay.json;
  srcStudyTutorOverlay = ./settings/study-tutor.overlay.json;
  srcWorkOverlay = ./settings/work.overlay.json;
  srcMcp = ./mcp/global.json;
  srcGlobalAgents = ./resources/global/AGENTS.md;
  srcPolicies = ./policies;
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
    install_managed_file "${srcGlobalAgents}" "$agent_dir/AGENTS.md" 0644

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

    version="$(${piWrapped}/bin/pi --version 2>/dev/null || true)"
    if [ -n "$version" ]; then
      echo "Pi version: $version"
    else
      warn "pi --version did not return a version"
    fi

    help="$(${piWrapped}/bin/pi --help 2>/dev/null || true)"
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
    for cmd in pi pi-raw pi-admin pi-readonly pi-safe pi-nixos pi-study pi-study-tutor pi-work pi-research pi-trusted pi-bootstrap pi-study-init pi-study-tutor-init pi-work-init pi-doctor pi-drift-check pi-compat-check pi-npm; do
      printf '%-24s ' "$cmd"
      command -v "$cmd" || true
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
    echo "Cautious note: pi-readonly/pi-safe are deprecated compatibility aliases for policy-backed cautious mode. Cautious mode launches in an empty workspace and is still not an OS/network sandbox."
    echo "Source-management note: use plain pi for daily work and pi-admin for maintenance. Do not use pi install/remove/config for durable setup changes. Edit modules/programs/cli/pi source and resync with pi-admin sync. Run pi-admin compat after package/version changes."
    echo
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
    compare_file "global AGENTS" "${srcGlobalAgents}" "${paths.piAgentDir}/AGENTS.md"
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
in
{
  inherit piBootstrap piStudyInit piStudyTutorInit piWorkInit piCompatCheck piDoctor piDriftCheck;
}
