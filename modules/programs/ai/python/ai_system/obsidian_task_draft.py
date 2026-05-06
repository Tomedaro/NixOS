"""Create reviewable TaskNotes-compatible task drafts from approved proposals.

This is an Obsidian/TaskNotes draft bridge. It turns an explicitly approved
proposal into bounded task draft artifacts for Obsidian to review/apply later.

It must not:
- write to AI/inbox/actions
- edit Obsidian notes directly
- execute shell/app commands
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text
from ai_system.obsidian_contracts import (
    DEFAULT_AI_DIR,
    as_dict,
    bounded_line as contract_bounded_line,
    bounded_list as contract_bounded_list,
    bounded_text,
    contains_direct_execution as contract_contains_direct_execution,
    now_iso_and_epoch,
    read_json_object,
    slug as contract_slug,
)

MAX_ID = 160
MAX_TITLE = 180
MAX_BODY = 4000
MAX_TEXT = 2000
MAX_LIST_ITEMS = 16
MAX_ESTIMATED_MINUTES = 240

TASK_ACTION_TYPES = {
    "draft_task",
    "create_task_note",
    "suggest_next_step",
    "select_existing_task",
}

ALLOWED_STATUSES = {"todo", "doing", "waiting", "done", "cancelled"}
ALLOWED_PRIORITIES = {"low", "normal", "medium", "high"}
ALLOWED_ENERGIES = {"low", "medium", "high", "unknown"}


def bounded_line(value: Any, *, max_len: int = MAX_TITLE) -> str:
    return contract_bounded_line(value, max_len=max_len)


def bounded_list(values: Any, *, max_items: int = MAX_LIST_ITEMS) -> list[str]:
    return contract_bounded_list(values, max_items=max_items, max_len=MAX_ID)


def slug(value: Any) -> str:
    return contract_slug(value, max_len=MAX_ID, fallback="task")


def read_json(path: Path) -> dict[str, Any]:
    return read_json_object(path, object_error="input must be a JSON object")


def contains_direct_execution(value: Any) -> list[str]:
    return contract_contains_direct_execution(value, max_items=MAX_LIST_ITEMS)


def is_approved(payload: dict[str, Any]) -> bool:
    if payload.get("approved") is True:
        return True

    if payload.get("decision") == "approve_proposal":
        return True

    for key in ("proposal_action", "approval", "decision_record", "action"):
        nested = as_dict(payload.get(key))
        if nested.get("approved") is True:
            return True
        if nested.get("decision") == "approve_proposal":
            return True

    return str(payload.get("status") or "") in {"approved", "bridge_ready"}


def extract_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") == "obsidian_proposal.v1":
        return payload

    for key in (
        "proposal",
        "approved_proposal",
        "reviewed_proposal",
        "source_proposal",
    ):
        candidate = as_dict(payload.get(key))
        if candidate:
            return candidate

    artifact = as_dict(payload.get("artifact"))
    for key in ("proposal", "approved_proposal", "reviewed_proposal"):
        candidate = as_dict(artifact.get(key))
        if candidate:
            return candidate

    return {}


def extract_task_candidate(proposal: dict[str, Any]) -> dict[str, Any]:
    for key in ("task_draft", "task", "proposed_task"):
        candidate = as_dict(proposal.get(key))
        if candidate:
            return candidate

    actions = proposal.get("suggested_actions")
    if isinstance(actions, list):
        for action in actions:
            action = as_dict(action)
            if str(action.get("type") or "") in TASK_ACTION_TYPES:
                return {
                    "title": action.get("title") or action.get("label"),
                    "body": action.get("body") or action.get("description"),
                    "priority": action.get("priority"),
                    "energy": action.get("energy"),
                    "estimated_minutes": action.get("estimated_minutes"),
                    "goal_id": action.get("goal_id"),
                    "project_id": action.get("project_id"),
                    "area": action.get("area"),
                }

    return {}


def bounded_status(value: Any) -> str:
    status = bounded_line(value, max_len=40).lower()
    return status if status in ALLOWED_STATUSES else "todo"


def bounded_priority(value: Any) -> str:
    priority = bounded_line(value, max_len=40).lower()
    if priority == "medium":
        return "normal"
    return priority if priority in ALLOWED_PRIORITIES else "normal"


def bounded_energy(value: Any) -> str:
    energy = bounded_line(value, max_len=40).lower()
    return energy if energy in ALLOWED_ENERGIES else "unknown"


def bounded_minutes(value: Any) -> int:
    try:
        minutes = int(value)
    except Exception:
        minutes = 15

    return max(1, min(MAX_ESTIMATED_MINUTES, minutes))


def yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    return json.dumps(str(value), ensure_ascii=False)


def yaml_list(values: list[str]) -> list[str]:
    if not values:
        return ["[]"]

    return [f"  - {yaml_value(value)}" for value in values]


def task_markdown(draft: dict[str, Any]) -> str:
    frontmatter = draft["tasknote_frontmatter"]

    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(yaml_list(value))
        else:
            lines.append(f"{key}: {yaml_value(value)}")
    lines.extend(
        [
            "---",
            "",
            f"# {draft['title']}",
            "",
            draft.get("body") or "",
            "",
            "## Agent reason",
            "",
            draft.get("agent_reason") or "_none_",
            "",
            "## Review status",
            "",
            "- This is a draft only.",
            "- Obsidian/Templater must apply it explicitly.",
            "- No live action queue was written.",
            "",
        ]
    )

    return "\n".join(lines)


def normalize_task_draft(payload: dict[str, Any]) -> dict[str, Any]:
    if not is_approved(payload):
        raise ValueError(
            "approved proposal action is required before task draft creation"
        )

    proposal = extract_proposal(payload)
    if not proposal:
        raise ValueError("approved payload does not contain a proposal")

    direct_fields = contains_direct_execution(proposal)
    if direct_fields:
        raise ValueError(
            "task draft proposals must not contain direct execution fields: "
            + ", ".join(direct_fields[:8])
        )

    timestamp, epoch = now_iso_and_epoch()
    task = extract_task_candidate(proposal)

    proposal_id = bounded_line(
        proposal.get("proposal_id") or payload.get("proposal_id") or "unknown-proposal",
        max_len=MAX_ID,
    )

    goal_ids = bounded_list(
        task.get("goal_ids")
        or proposal.get("goal_ids")
        or as_dict(proposal.get("context_refs")).get("current_goal_ids")
    )
    goal_id = bounded_line(
        task.get("goal_id") or (goal_ids[0] if goal_ids else ""), max_len=MAX_ID
    )

    title = bounded_line(
        task.get("title")
        or task.get("text")
        or proposal.get("summary")
        or proposal.get("message_markdown")
        or "Next action",
        max_len=MAX_TITLE,
    )

    body = bounded_text(
        task.get("body")
        or task.get("description")
        or proposal.get("message_markdown")
        or proposal.get("summary")
        or "",
        max_len=MAX_BODY,
    )

    task_id = f"taskdraft-{epoch}-{slug(proposal_id or title)}"

    priority = bounded_priority(task.get("priority") or proposal.get("priority"))
    energy = bounded_energy(task.get("energy") or proposal.get("energy"))
    estimated_minutes = bounded_minutes(
        task.get("estimated_minutes") or proposal.get("estimated_minutes") or 15
    )

    area = bounded_line(
        task.get("area")
        or proposal.get("area")
        or (goal_id.split("-")[0] if goal_id else ""),
        max_len=MAX_ID,
    )

    project_id = bounded_line(
        task.get("project_id") or proposal.get("project_id") or "",
        max_len=MAX_ID,
    )

    tags = bounded_list(task.get("tags") or proposal.get("tags"))
    if "ai-task" not in tags:
        tags.insert(0, "ai-task")
    if "tasknotes" not in tags:
        tags.insert(1, "tasknotes")

    agent_reason = bounded_text(
        task.get("agent_reason")
        or proposal.get("summary")
        or "Created from an approved Obsidian AI proposal.",
        max_len=MAX_TEXT,
    )

    frontmatter = {
        "schema_version": "obsidian_task_draft.v1",
        "task_id": task_id,
        "status": bounded_status(task.get("status")),
        "priority": priority,
        "energy": energy,
        "estimated_minutes": estimated_minutes,
        "goal_id": goal_id,
        "project_id": project_id,
        "area": area,
        "source": "local-ai",
        "agent_created": True,
        "agent_reason": agent_reason,
        "source_proposal_id": proposal_id,
        "tags": tags,
    }

    draft = {
        "schema_version": "obsidian_task_draft.v1",
        "task_id": task_id,
        "created_at": timestamp,
        "timestamp_epoch": epoch,
        "source": "local-ai",
        "surface": "obsidian",
        "status": "draft",
        "title": title,
        "body": body,
        "goal_id": goal_id,
        "goal_ids": goal_ids,
        "project_id": project_id,
        "area": area,
        "priority": priority,
        "energy": energy,
        "estimated_minutes": estimated_minutes,
        "agent_created": True,
        "agent_reason": agent_reason,
        "source_proposal_id": proposal_id,
        "source_intent_id": bounded_line(proposal.get("intent_id"), max_len=MAX_ID),
        "requires_templater_apply": True,
        "executes_now": False,
        "writes_live_action_queue": False,
        "edits_obsidian_now": False,
        "tasknote_frontmatter": frontmatter,
    }
    draft["markdown"] = task_markdown(draft)
    return draft


def write_task_draft(
    payload: dict[str, Any],
    *,
    ai_dir: str | Path | None = None,
) -> dict[str, Any]:
    ai_root = Path(ai_dir or DEFAULT_AI_DIR).expanduser()
    draft = normalize_task_draft(payload)

    outbox = ai_root / "outbox" / "to-obsidian"
    draft_json = outbox / "task-drafts" / f"{draft['task_id']}.json"
    draft_md = outbox / "task-drafts" / f"{draft['task_id']}.md"
    current_json = outbox / "current-task-draft.json"
    current_md = outbox / "current-task-draft.md"
    latest_json = ai_root / "state" / "obsidian" / "latest-task-draft.json"
    latest_md = ai_root / "state" / "obsidian" / "latest-task-draft.md"

    atomic_write_json(draft_json, draft)
    atomic_write_text(draft_md, draft["markdown"])
    atomic_write_json(current_json, draft)
    atomic_write_text(current_md, draft["markdown"])
    atomic_write_json(latest_json, draft)
    atomic_write_text(latest_md, draft["markdown"])

    return {
        **draft,
        "written_paths": {
            "draft_json": str(draft_json),
            "draft_markdown": str(draft_md),
            "current_json": str(current_json),
            "current_markdown": str(current_md),
            "latest_json": str(latest_json),
            "latest_markdown": str(latest_md),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reviewable Obsidian/TaskNotes task draft from an approved proposal"
    )
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument("--input", required=True, help="Approved proposal JSON payload")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = read_json(Path(args.input))

    if args.write:
        result = write_task_draft(payload, ai_dir=args.ai_dir)
    else:
        result = normalize_task_draft(payload)

    if args.dry_run or not args.write:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
