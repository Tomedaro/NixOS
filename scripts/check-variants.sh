set -euo pipefail

if [[ -z "${WORKSTATION_VARIANTS_FILE:-}" || ! -r "$WORKSTATION_VARIANTS_FILE" ]]; then
  echo "WORKSTATION_VARIANTS_FILE is missing or unreadable" >&2
  exit 1
fi

mapfile -t all_variants < "$WORKSTATION_VARIANTS_FILE"
flake_ref=""
list_only=0
requested=()

usage() {
  cat <<'USAGE'
Usage: check-variants [--flake REF] [--list] [VARIANT ...]

Evaluate supported non-default workstation variants one at a time.
Each variant runs in a fresh, uncached Nix evaluator process with Import From
Derivation disabled, so evaluator memory is released between configurations and
variant validity does not depend on pre-existing derivation outputs.

  --flake REF  Flake reference to evaluate. Defaults to the current Git repo.
  --list       Print supported non-default variant names and exit.
  -h, --help   Show this help.
USAGE
}

while (($# > 0)); do
  case "$1" in
    --flake)
      shift
      if (($# == 0)); then
        echo "--flake requires a flake reference" >&2
        exit 2
      fi
      flake_ref="$1"
      ;;
    --list)
      list_only=1
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --)
      shift
      requested+=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      requested+=("$1")
      ;;
  esac
  shift
done

if [[ -z "$flake_ref" ]]; then
  if repo=$(git rev-parse --show-toplevel 2>/dev/null) && [[ -f "$repo/flake.nix" ]]; then
    flake_ref="$repo"
  elif [[ -f ./flake.nix ]]; then
    flake_ref="$PWD"
  else
    echo "Could not locate a flake. Run inside the repository or pass --flake REF." >&2
    exit 1
  fi
fi

if ((list_only)); then
  printf '%s\n' "${all_variants[@]}"
  exit 0
fi

if ((${#requested[@]} == 0)); then
  selected=("${all_variants[@]}")
else
  selected=("${requested[@]}")
fi

contains_variant() {
  local wanted="$1"
  local candidate
  for candidate in "${all_variants[@]}"; do
    [[ "$candidate" == "$wanted" ]] && return 0
  done
  return 1
}

local_count=${#selected[@]}
index=0
for name in "${selected[@]}"; do
  if ! contains_variant "$name"; then
    echo "Unknown or unsupported variant: $name" >&2
    echo "Use --list to see valid names." >&2
    exit 2
  fi

  index=$((index + 1))
  printf '[%d/%d] %s\n' "$index" "$local_count" "$name"
  nix eval \
    --no-eval-cache \
    --option allow-import-from-derivation false \
    --no-update-lock-file \
    --no-write-lock-file \
    --raw "$flake_ref#lib.workstation.variantDrvPaths.$name" \
    >/dev/null
done

printf 'All %d selected variant(s) evaluated successfully.\n' "$local_count"
