"""Bridge approved Obsidian proposals into reviewed Obsidian outbox artifacts.

This is deliberately not a general executor. It consumes explicit Obsidian
proposal approvals and materializes review-ready artifacts. It must not write to
AI/inbox/actions, run commands, edit notes, launch apps, or mutate live state
outside its own Obsidian approval outbox.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text
from ai_system.queue import list_stable_json_queue_files
from ai_system.obsidian_contracts import (
    DEFAULT_AI_DIR,
    bounded_text as contract_bounded_text,
    read_json_object,
    utc_now,
)

MAX_TEXT = 4000
MAX_ACTIONS = 8


def clip_text(value: Any, limit: int = MAX_TEXT) -> str:
    return contract_bounded_text(value, max_len=limit)


def read_json(path: Path) -> dict[str, Any]:
    return read_json_object(path, missing_ok=True, default={})


def latest_action_file(ai_dir: Path) -> Path | None:
    inbox = ai_dir / "inbox" / "obsidian" / "actions"
    if not inbox.exists():
        return None

    ready, _unstable, _ignored = list_stable_json_queue_files(inbox, 0)

    files = sorted(
        ready,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def proposal_paths(ai_dir: Path, proposal_id: str) -> list[Path]:
    outbox = ai_dir / "outbox" / "to-obsidian"
    return [
        outbox / "proposals" / f"{proposal_id}.json",
        outbox / "current-proposal.json",
    ]


def find_proposal(ai_dir: Path, proposal_id: str) -> tuple[Path | None, dict[str, Any]]:
    for path in proposal_paths(ai_dir, proposal_id):
        data = read_json(path)
        if data.get("proposal_id") == proposal_id:
            return path, data

    return None, {}


def compact_suggested_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    actions: list[dict[str, Any]] = []
    for item in value[:MAX_ACTIONS]:
        if not isinstance(item, dict):
            continue

        actions.append(
            {
                "type": clip_text(item.get("type"), 120),
                "label": clip_text(item.get("label"), 500),
                "requires_approval": bool(item.get("requires_approval")),
            }
        )

    return actions


def markdown_for_reviewed(reviewed: dict[str, Any]) -> str:
    actions = reviewed.get("suggested_actions") or []

    lines = [
        "# Approved Obsidian Proposal",
        "",
        f"Status: `{reviewed.get('status', '')}`",
        f"Proposal: `{reviewed.get('proposal_id', '')}`",
        f"Kind: `{reviewed.get('proposal_kind', '')}`",
        f"Approved at: `{reviewed.get('approved_at', '')}`",
        "",
        "## Summary",
        "",
        reviewed.get("summary") or "_none_",
        "",
        "## Message",
        "",
        reviewed.get("message_markdown") or "_none_",
        "",
        "## Suggested actions",
        "",
    ]

    if actions:
        for action in actions:
            lines.append(
                f"- `{action.get('type', 'unknown')}` — {action.get('label', '')}"
            )
    else:
        lines.append("- No suggested actions.")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This file is review-ready, not executed.",
            "- The approval bridge did not write to `AI/inbox/actions`.",
            "- A later capability-specific bridge must perform any real mutation.",
            "",
        ]
    )

    return "\n".join(lines)


def validate_approval(
    action: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[bool, str]:
    if action.get("schema_version") != "obsidian_proposal_action.v1":
        return False, "unsupported_action_schema"

    if action.get("decision") != "approve_proposal" or not action.get("approved"):
        return False, "decision_not_approved"

    if proposal.get("schema_version") != "obsidian_proposal.v1":
        return False, "unsupported_proposal_schema"

    if action.get("proposal_id") != proposal.get("proposal_id"):
        return False, "proposal_id_mismatch"

    action_kind = str(action.get("proposal_kind") or "")
    proposal_kind = str(proposal.get("proposal_kind") or "")
    if action_kind not in {"", "unknown", proposal_kind}:
        return False, "proposal_kind_mismatch"

    if proposal.get("status") != "proposed":
        return False, "proposal_not_proposed"

    if proposal.get("execution_policy") != "proposal_only_no_direct_execution":
        return False, "unsafe_execution_policy"

    return True, "ok"


def build_reviewed_proposal(
    action: dict[str, Any],
    proposal: dict[str, Any],
    *,
    action_path: Path,
    proposal_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()

    reviewed = {
        "schema_version": "obsidian_reviewed_proposal.v1",
        "status": "review_ready",
        "source": "obsidian-approval-bridge",
        "surface": "obsidian",
        "created_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "approved_at": action.get("timestamp", ""),
        "proposal_id": str(proposal.get("proposal_id") or ""),
        "proposal_kind": str(proposal.get("proposal_kind") or "unknown"),
        "intent_id": str(proposal.get("intent_id") or ""),
        "summary": clip_text(proposal.get("summary"), 1000),
        "message_markdown": clip_text(proposal.get("message_markdown")),
        "note_path": clip_text(proposal.get("note_path"), 500),
        "goal_ids": (
            proposal.get("goal_ids")
            if isinstance(proposal.get("goal_ids"), list)
            else []
        ),
        "task_ids": (
            proposal.get("task_ids")
            if isinstance(proposal.get("task_ids"), list)
            else []
        ),
        "suggested_actions": compact_suggested_actions(
            proposal.get("suggested_actions")
        ),
        "action_path": str(action_path),
        "proposal_path": str(proposal_path),
        "executes_now": False,
        "writes_live_action_queue": False,
        "requires_capability_bridge": True,
    }
    reviewed["markdown"] = markdown_for_reviewed(reviewed)
    return reviewed


def run_bridge(
    ai_dir: str | Path | None = None,
    *,
    write: bool = False,
    action_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(ai_dir or DEFAULT_AI_DIR).expanduser()

    selected_action_path = (
        Path(action_path).expanduser() if action_path else latest_action_file(root)
    )
    if selected_action_path is None:
        return {
            "schema_version": "obsidian_approval_bridge_result.v1",
            "status": "no_proposal_action",
            "message": "No Obsidian proposal action found.",
        }

    action = read_json(selected_action_path)
    proposal_id = str(action.get("proposal_id") or "")
    proposal_path, proposal = find_proposal(root, proposal_id)

    if not proposal_path or not proposal:
        return {
            "schema_version": "obsidian_approval_bridge_result.v1",
            "status": "proposal_not_found",
            "proposal_id": proposal_id,
            "action_path": str(selected_action_path),
        }

    ok, reason = validate_approval(action, proposal)
    if not ok:
        return {
            "schema_version": "obsidian_approval_bridge_result.v1",
            "status": "rejected",
            "reason": reason,
            "proposal_id": proposal_id,
            "action_path": str(selected_action_path),
            "proposal_path": str(proposal_path),
            "writes_live_action_queue": False,
        }

    reviewed = build_reviewed_proposal(
        action,
        proposal,
        action_path=selected_action_path,
        proposal_path=proposal_path,
    )

    result: dict[str, Any] = {
        "schema_version": "obsidian_approval_bridge_result.v1",
        "status": "review_ready",
        "proposal_id": proposal_id,
        "reviewed_proposal": reviewed,
        "writes_live_action_queue": False,
    }

    if write:
        outbox = root / "outbox" / "to-obsidian" / "approved-proposals"
        json_path = outbox / f"{proposal_id}.json"
        md_path = outbox / f"{proposal_id}.md"
        current_json = (
            root / "outbox" / "to-obsidian" / "current-approved-proposal.json"
        )
        current_md = root / "outbox" / "to-obsidian" / "current-approved-proposal.md"

        atomic_write_json(json_path, reviewed)
        atomic_write_text(md_path, reviewed["markdown"])
        atomic_write_json(current_json, reviewed)
        atomic_write_text(current_md, reviewed["markdown"])

        result["written_paths"] = {
            "json": str(json_path),
            "markdown": str(md_path),
            "current_json": str(current_json),
            "current_markdown": str(current_md),
        }

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge approved Obsidian proposals into reviewed artifacts"
    )
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument("--action-path", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_bridge(
        args.ai_dir,
        write=args.write,
        action_path=args.action_path or None,
    )

    if args.dry_run or not args.write:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
