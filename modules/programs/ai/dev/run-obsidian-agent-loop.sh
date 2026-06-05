#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PYTHON_LIB="$REPO_ROOT/modules/programs/ai/python"

AI_DIR="${AI_DIR:-/home/daniil/Sync/Perseverance.Gu/AI}"
WRITE_CONTEXT=0
WRITE_PROPOSAL=0
BRIDGE_APPROVED_PROPOSAL=0
WRITE_TASK_DRAFT=0
VALIDATE_TASK_DRAFT=0
VERBOSE=0

export PYTHONPATH="$PYTHON_LIB${PYTHONPATH:+:$PYTHONPATH}"
export NO_COLOR=1
export PAGER=cat

usage() {
  cat <<'USAGE'
Usage: modules/programs/ai/dev/run-obsidian-agent-loop.sh [options]

Inspect-first Obsidian agent operator loop.

Default mode is non-mutating:
  - build agent context dry-run
  - run Obsidian intent planner dry-run
  - print current proposal/task-draft locations

Options:
  --write-context      Write state/agent/context.json and status.md.
  --write-proposal     Write outbox/to-obsidian/current-proposal.* from latest pending intent.
  --bridge-approved-proposal
                       Consume explicit approval and write reviewed Obsidian artifact.
  --write-task-draft   From explicit approval, write reviewable TaskNotes draft.
  --validate-task-draft
                       Dry-run validate current task draft for future TaskNotes apply.
  --verbose, -v        Print fuller JSON output.
  --help, -h           Show help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --write-context) WRITE_CONTEXT=1 ;;
    --write-proposal) WRITE_PROPOSAL=1 ;;
    --bridge-approved-proposal) BRIDGE_APPROVED_PROPOSAL=1 ;;
    --write-task-draft) WRITE_TASK_DRAFT=1; BRIDGE_APPROVED_PROPOSAL=1 ;;
    --validate-task-draft) VALIDATE_TASK_DRAFT=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

run_python() {
  if command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  else
    nix shell nixpkgs#python3 -c python3 "$@"
  fi
}

section() {
  echo
  echo "===== $* ====="
}

json_summary() {
  local label="$1"
  local file="$2"

  echo "$label: $file"
  if [ ! -f "$file" ]; then
    echo "missing"
    return 0
  fi

  if command -v jq >/dev/null 2>&1; then
    jq -r '
      "schema_version=\(.schema_version // "unknown")",
      "status=\(.status // .decision // "unknown")",
      "id=\(.proposal_id // .intent_id // .task_id // .action_id // "unknown")",
      "updated_at=\(.updated_at // .created_at // .timestamp // "unknown")",
      "summary=\(.summary // .title // .message // .user_message_preview // "")"
    ' "$file" 2>/dev/null || true
  else
    echo "present; install jq for compact summary"
  fi
}

latest_json_in() {
  local dir="$1"
  if [ -d "$dir" ]; then
    find "$dir" -maxdepth 1 -type f -name '*.json' -printf '%T@ %p\n' \
      | sort -nr \
      | sed -n '1p' \
      | cut -d' ' -f2-
  fi
}

section "repo"
echo "$REPO_ROOT"
git -C "$REPO_ROOT" status --short || true

section "Obsidian agent loop policy"
echo "AI_DIR=$AI_DIR"
echo "write_context=$WRITE_CONTEXT"
echo "write_proposal=$WRITE_PROPOSAL"
echo "bridge_approved_proposal=$BRIDGE_APPROVED_PROPOSAL"
echo "write_task_draft=$WRITE_TASK_DRAFT"
echo "validate_task_draft=$VALIDATE_TASK_DRAFT"
echo "writes_live_action_queue=false"
echo "edits_obsidian_now=false"
echo "auto_approval=false"

section "Obsidian inbox/outbox"
latest_intent="$(latest_json_in "$AI_DIR/inbox/obsidian/messages" || true)"
latest_action="$(latest_json_in "$AI_DIR/inbox/obsidian/actions" || true)"

json_summary "latest intent" "${latest_intent:-$AI_DIR/inbox/obsidian/messages/<none>}"
json_summary "latest proposal action" "${latest_action:-$AI_DIR/inbox/obsidian/actions/<none>}"
json_summary "current proposal" "$AI_DIR/outbox/to-obsidian/current-proposal.json"
json_summary "current approved proposal" "$AI_DIR/outbox/to-obsidian/current-approved-proposal.json"
json_summary "current task draft" "$AI_DIR/outbox/to-obsidian/current-task-draft.json"

section "agent context"
if [ "$WRITE_CONTEXT" -eq 1 ]; then
  run_python -m ai_system.agent_context --ai-dir "$AI_DIR" --write --dry-run
else
  if [ "$VERBOSE" -eq 1 ]; then
    run_python -m ai_system.agent_context --ai-dir "$AI_DIR" --dry-run
  else
    run_python -m ai_system.agent_context --ai-dir "$AI_DIR" --dry-run \
      | run_python -c '
import json, sys
data = json.load(sys.stdin)
hub = data.get("context_hub", {})
print("schema_version=" + str(data.get("schema_version", "unknown")))
print("generated_at=" + str(data.get("generated_at", "unknown")))
print("context_hub=" + str(hub.get("schema_version", "missing")))
print("available_providers=" + ",".join(hub.get("available_providers", [])))
warnings = hub.get("warnings", [])
print("warnings=" + str(len(warnings)))
for item in warnings[:8]:
    print("- {provider}: {warning}".format(**item))
'
  fi
fi

section "intent planner"
if [ "$WRITE_PROPOSAL" -eq 1 ]; then
  run_python -m ai_system.obsidian_intent_planner --ai-dir "$AI_DIR" --write

  if [ ! -f "$AI_DIR/outbox/to-obsidian/current-proposal.json" ]; then
    echo "ERROR: --write-proposal did not create current-proposal.json" >&2
    echo "Check pending intent status under: $AI_DIR/inbox/obsidian/messages" >&2
    exit 1
  fi

  json_summary "written current proposal" "$AI_DIR/outbox/to-obsidian/current-proposal.json"
else
  run_python -m ai_system.obsidian_intent_planner --ai-dir "$AI_DIR" --dry-run
fi


section "approval bridge"
if [ "$BRIDGE_APPROVED_PROPOSAL" -eq 1 ]; then
  run_python -m ai_system.obsidian_approval_bridge --ai-dir "$AI_DIR" --write --dry-run
else
  echo "skipped; pass --bridge-approved-proposal after explicit approval"
fi

section "task draft"
if [ "$WRITE_TASK_DRAFT" -eq 1 ]; then
  run_python - "$AI_DIR" <<'PYTASK'
import json
import sys
from pathlib import Path

from ai_system.obsidian_approval_bridge import run_bridge
from ai_system.obsidian_task_draft import write_task_draft

root = Path(sys.argv[1]).expanduser()
bridge = run_bridge(root, write=True)

if bridge.get("status") in {"no_proposal_action", "proposal_not_found", "rejected"}:
    print(json.dumps(bridge, indent=2, ensure_ascii=False, sort_keys=True))
    raise SystemExit(1)

proposal = {}
reviewed = bridge.get("reviewed_proposal")
if isinstance(reviewed, dict):
    proposal_path = reviewed.get("proposal_path")
    if proposal_path:
        proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))

if not proposal:
    current = root / "outbox/to-obsidian/current-proposal.json"
    proposal = json.loads(current.read_text(encoding="utf-8"))

payload = {
    "schema_version": "obsidian_approval_bridge_result.v1",
    "approved": True,
    "decision": "approve_proposal",
    "proposal": proposal,
    "approval": {
        "approved": True,
        "decision": "approve_proposal",
    },
    "bridge_result": bridge,
}

result = write_task_draft(payload, ai_dir=root)
print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
PYTASK

  if [ ! -f "$AI_DIR/outbox/to-obsidian/current-task-draft.json" ]; then
    echo "ERROR: --write-task-draft did not create current-task-draft.json" >&2
    exit 1
  fi

  json_summary "written current task draft" "$AI_DIR/outbox/to-obsidian/current-task-draft.json"
else
  echo "skipped; pass --write-task-draft after explicit approval"
fi


section "task draft validation"
if [ "$VALIDATE_TASK_DRAFT" -eq 1 ]; then
  run_python - "$AI_DIR" <<'PYVALIDATE'
import json
import sys
from pathlib import Path

from ai_system.tasknotes_apply_validator import validate_tasknotes_apply_candidate

root = Path(sys.argv[1]).expanduser()
draft_path = root / "outbox/to-obsidian/current-task-draft.json"
approval_path = root / "outbox/to-obsidian/current-approved-proposal.json"
tasknotes_dir = root.parent / "TaskNotes"

if draft_path.exists():
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
else:
    draft = {}

result = validate_tasknotes_apply_candidate(
    draft,
    ai_dir=root,
    approval_path=approval_path if approval_path.exists() else None,
    tasknotes_dir=tasknotes_dir,
    input_draft_path=draft_path,
)

def format_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)

for key in [
    "schema_version",
    "status",
    "writes_tasknotes",
    "idempotency_key",
    "collision_checked",
    "reasons",
    "warnings",
]:
    print(f"{key}={format_value(result.get(key))}")
PYVALIDATE
else
  echo "skipped; pass --validate-task-draft after reviewable task draft exists"
fi

section "next explicit stages"
cat <<EOF
1. Review proposal:
   $AI_DIR/outbox/to-obsidian/current-proposal.md

2. Capture approve/reject/revise:
   ai_system.obsidian_proposal_action

3. Bridge approved proposal:
   ai_system.obsidian_approval_bridge

4. Create reviewable TaskNotes draft:
   ai_system.obsidian_task_draft

5. Dry-run validate the reviewed draft:
   modules/programs/ai/dev/run-obsidian-agent-loop.sh --validate-task-draft

6. Future deterministic TaskNotes apply/promote remains separate and explicit.
EOF

section "done"
echo "RESULT ok"
