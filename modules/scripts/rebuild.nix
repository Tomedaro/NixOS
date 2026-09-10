{
  nixosConfigurationName,
  pkgs,
  ...
}:
pkgs.writeShellScriptBin "rebuild" ''
    set -euo pipefail

    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BOLD='\033[1m'
    NC='\033[0m'

    full=0
    use_path_source=0
    test_only=0

    usage() {
      cat <<'USAGE'
  Usage: rebuild [--full] [--path] [--test-only]

  Safely validate and activate the current NixOS configuration without modifying
  repository source files or the Git index.

    --full       Build all flake checks, not only the active system closure.
    --path       Explicitly evaluate the complete working directory with path:.
                 Use this only when intentionally testing untracked Nix sources.
    --test-only  Stop after temporary activation and smoke checks.
    -h, --help   Show this help.

  By default the command uses Git flake source semantics. If untracked *.nix
  files exist, it refuses to continue rather than silently excluding them.
  USAGE
    }

    while (($# > 0)); do
      case "$1" in
        --full)
          full=1
          ;;
        --path)
          use_path_source=1
          ;;
        --test-only)
          test_only=1
          ;;
        -h|--help)
          usage
          exit 0
          ;;
        *)
          printf '%bUnknown argument:%b %s\n' "$RED" "$NC" "$1" >&2
          usage >&2
          exit 2
          ;;
      esac
      shift
    done

    if [[ ''${EUID} -eq 0 ]]; then
      printf '%bRefusing to run as root.%b Run rebuild as your normal user; only activation uses sudo.\n' "$RED" "$NC" >&2
      exit 1
    fi

    resolve_repo() {
      local candidate=""

      if candidate="$(${pkgs.git}/bin/git -C "$PWD" rev-parse --show-toplevel 2>/dev/null)" \
        && [[ -f "$candidate/flake.nix" ]]; then
        printf '%s\n' "$candidate"
        return 0
      fi

      if [[ -f "$HOME/NixOS/flake.nix" ]]; then
        printf '%s\n' "$HOME/NixOS"
        return 0
      fi

      return 1
    }

    if ! repo="$(resolve_repo)"; then
      printf '%bCould not find the NixOS repository.%b Run from the repository or keep it at $HOME/NixOS.\n' "$RED" "$NC" >&2
      exit 1
    fi

    cd "$repo"

    printf '%bRepository:%b %s\n' "$GREEN" "$NC" "$repo"
    printf '%bConfiguration:%b ${nixosConfigurationName}\n' "$GREEN" "$NC"

    if [[ "$use_path_source" -eq 0 ]]; then
      mapfile -t untracked_nix < <(${pkgs.git}/bin/git ls-files --others --exclude-standard -- '*.nix')
      if ((''${#untracked_nix[@]} > 0)); then
        printf '%bUntracked Nix sources exist.%b A Git flake would omit them:\n' "$RED" "$NC" >&2
        printf '  %s\n' "''${untracked_nix[@]}" >&2
        printf '\nTrack the intended files, or explicitly use %brebuild --path%b for a development build.\n' "$BOLD" "$NC" >&2
        exit 1
      fi
      flake_ref="$repo"
      source_description="Git working tree (tracked source only)"
    else
      flake_ref="path:$repo"
      source_description="explicit path: working tree (includes untracked source)"
      printf '%bWarning:%b --path includes the complete checkout in the flake source.\n' "$YELLOW" "$NC"
    fi

    printf '%bSource:%b %s\n' "$GREEN" "$NC" "$source_description"

    printf '\n%b[1/6] Formatting check%b\n' "$BOLD" "$NC"
    if [[ "$use_path_source" -eq 0 ]]; then
      ${pkgs.git}/bin/git ls-files -z -- '*.nix' \
        | ${pkgs.findutils}/bin/xargs -0 -r ${pkgs.alejandra}/bin/alejandra --check
    else
      ${pkgs.findutils}/bin/find . \
        -path './.git' -prune -o \
        -type f -name '*.nix' -print0 \
        | ${pkgs.findutils}/bin/xargs -0 -r ${pkgs.alejandra}/bin/alejandra --check
    fi

    printf '\n%b[2/6] Flake evaluation%b\n' "$BOLD" "$NC"
    ${pkgs.nix}/bin/nix flake check --no-build "$flake_ref"

    printf '\n%b[3/6] Build gate%b\n' "$BOLD" "$NC"
    if [[ "$full" -eq 1 ]]; then
      ${pkgs.nix}/bin/nix flake check "$flake_ref"
      printf '\n%bSupported variant matrix%b\n' "$BOLD" "$NC"
      ${pkgs.nix}/bin/nix run "$flake_ref#check-variants" -- --flake "$flake_ref"
    fi

    system_path="$(${pkgs.nix}/bin/nix build --no-link --print-out-paths \
      "$flake_ref#nixosConfigurations.${nixosConfigurationName}.config.system.build.toplevel")"

    if [[ -z "$system_path" || ! -x "$system_path/bin/switch-to-configuration" ]]; then
      printf '%bCould not resolve the built NixOS system closure.%b\n' "$RED" "$NC" >&2
      exit 1
    fi

    printf '%bBuilt system:%b %s\n' "$GREEN" "$NC" "$system_path"

    printf '\n%b[4/6] Activation preview%b\n' "$BOLD" "$NC"
    sudo "$system_path/bin/switch-to-configuration" dry-activate

    printf '\n%b[5/6] Temporary activation%b\n' "$BOLD" "$NC"
    # Activate the exact closure built above. In particular, do not hand a path:
    # flake back to nixos-rebuild-ng: it can canonicalize a local repository back
    # to Git-flake semantics and thereby omit intentional untracked development
    # sources.
    sudo "$system_path/bin/switch-to-configuration" test

    printf '\n%b[6/6] Smoke checks%b\n' "$BOLD" "$NC"
    if systemctl --failed --quiet; then
      printf '%bNo failed system units.%b\n' "$GREEN" "$NC"
    else
      printf '%bWarning: failed system units are present after test activation:%b\n' "$YELLOW" "$NC"
      systemctl --failed --no-pager || true
    fi

    if systemctl --user --failed --quiet 2>/dev/null; then
      printf '%bNo failed user units.%b\n' "$GREEN" "$NC"
    else
      printf '%bWarning: failed user units are present:%b\n' "$YELLOW" "$NC"
      systemctl --user --failed --no-pager 2>/dev/null || true
    fi

    if [[ "$test_only" -eq 1 ]]; then
      printf '\n%bTest activation complete; switch was not requested.%b\n' "$GREEN" "$NC"
      exit 0
    fi

    if [[ ! -t 0 ]]; then
      printf '\n%bNot switching from a non-interactive shell.%b Re-run interactively after checking the test generation.\n' "$YELLOW" "$NC" >&2
      exit 1
    fi

    printf '\nManual checks before switching:\n'
    printf '  - graphical session and key applications still behave normally\n'
    printf '  - networking/DNS behave as expected for the current tranche\n'
    printf '  - sudo still works\n'
    printf '  - any tranche-specific checks have passed\n\n'

    read -r -p "Type 'switch' to activate this generation permanently: " answer
    if [[ "$answer" != "switch" ]]; then
      printf '%bSwitch cancelled; the test generation remains temporary.%b\n' "$YELLOW" "$NC"
      exit 0
    fi

    # switch-to-configuration does not itself advance the persistent system
    # profile. Do that explicitly first so GRUB generations and rollback semantics
    # remain equivalent to nixos-rebuild switch.
    sudo ${pkgs.nix}/bin/nix-env -p /nix/var/nix/profiles/system --set "$system_path"
    sudo env NIXOS_INSTALL_BOOTLOADER=1 "$system_path/bin/switch-to-configuration" switch
    printf '%bSystem switched successfully.%b\n' "$GREEN" "$NC"
''
