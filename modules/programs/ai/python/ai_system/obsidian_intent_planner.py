"""Plan safe Obsidian responses from pending Obsidian intents.

This is a proposal layer. It may write reviewable outbox proposals when explicitly
asked with --write, but it must not edit notes, create tasks, launch apps, or run
commands directly.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_system.agent_context import build_agent_context
from ai_system.io_utils import atomic_write_json, atomic_write_text
from ai_system.queue import list_stable_json_queue_files
from ai_system.obsidian_contracts import (
    DEFAULT_AI_DIR,
    PROPOSAL_EXECUTION_POLICY,
    bounded_text as contract_bounded_text,
    read_json_object,
    utc_now,
)


def clip_text(value: Any, limit: int) -> str:
    return contract_bounded_text(value, max_len=limit)


def read_json(path: Path) -> dict[str, Any]:
    return read_json_object(path, missing_ok=True, default={})


def pending_intent_files(ai_dir: Path) -> list[Path]:
    inbox = ai_dir / "inbox" / "obsidian" / "messages"
    if not inbox.exists():
        return []

    ready, _unstable, _ignored = list_stable_json_queue_files(inbox, 0)

    return sorted(
        ready,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def latest_pending_intent(ai_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    for path in pending_intent_files(ai_dir):
        data = read_json(path)
        if data.get("status") == "pending":
            return path, data

    return None, {}


def compact_context_for_proposal(context: dict[str, Any]) -> dict[str, Any]:
    hub = (
        context.get("context_hub")
        if isinstance(context.get("context_hub"), dict)
        else {}
    )
    facts = hub.get("facts") if isinstance(hub.get("facts"), dict) else {}

    return {
        "schema_version": "planner_context_refs.v1",
        "generated_at": context.get("generated_at", ""),
        "interaction": facts.get("interaction", {}),
        "obsidian": facts.get("obsidian", {}),
        "obsidian_intent": facts.get("obsidian_intent", {}),
        "activitywatch_available": bool(facts.get("activitywatch")),
        "anki_available": bool(facts.get("anki")),
        "recovery": facts.get("recovery", {}),
    }


def infer_proposal_kind(intent: dict[str, Any], context_refs: dict[str, Any]) -> str:
    if intent.get("kind") == "action_request" or intent.get("requested_action"):
        return "review_action_request"

    if intent.get("goal_ids"):
        return "next_goal_step"

    obsidian = (
        context_refs.get("obsidian")
        if isinstance(context_refs.get("obsidian"), dict)
        else {}
    )
    if obsidian.get("open_tasks"):
        return "next_task_step"

    return "clarify_or_plan"


def candidate_obsidian_tasks(
    context_refs: dict[str, Any],
    goal_ids: list[Any],
) -> list[dict[str, Any]]:
    obsidian = (
        context_refs.get("obsidian")
        if isinstance(context_refs.get("obsidian"), dict)
        else {}
    )
    tasks = obsidian.get("open_tasks")
    if not isinstance(tasks, list):
        return []

    wanted_goals = {str(goal) for goal in goal_ids if str(goal)}
    candidates: list[dict[str, Any]] = []

    for task in tasks:
        if not isinstance(task, dict):
            continue

        status = str(task.get("status") or "").lower()
        if status in {"done", "cancelled", "canceled"}:
            continue

        task_goal = str(task.get("goal_id") or "")
        if wanted_goals and task_goal and task_goal not in wanted_goals:
            continue

        candidates.append(task)

    priority_rank = {"high": 0, "medium": 1, "normal": 2, "low": 3}

    def rank(task: dict[str, Any]) -> tuple[int, str]:
        priority = str(task.get("priority") or "normal").lower()
        return (priority_rank.get(priority, 2), str(task.get("text") or ""))

    return sorted(candidates, key=rank)


def first_task_text(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return ""

    return clip_text(tasks[0].get("text") or tasks[0].get("title") or "", 180)


def build_markdown(proposal: dict[str, Any]) -> str:
    actions = proposal.get("suggested_actions") or []

    lines = [
        "# AI Proposal",
        "",
        f"Status: `{proposal.get('status', 'proposed')}`",
        f"Kind: `{proposal.get('proposal_kind', 'unknown')}`",
        f"Intent: `{proposal.get('intent_id', '')}`",
        "",
        "## Message",
        "",
        str(proposal.get("message_markdown") or ""),
        "",
        "## Suggested actions",
        "",
    ]

    if actions:
        for action in actions:
            label = action.get("label", "Action")
            action_type = action.get("type", "unknown")
            lines.append(f"- `{action_type}` — {label}")
    else:
        lines.append("- No direct action suggested.")

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This is a proposal only.",
            "- No note, task, app, shell command, or live state was mutated by the planner.",
            "- A later approval/action bridge must handle execution explicitly.",
            "",
        ]
    )

    return "\n".join(lines)


def build_proposal(
    intent: dict[str, Any],
    context: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    context_refs = compact_context_for_proposal(context)

    intent_id = str(intent.get("intent_id") or "unknown-intent")
    proposal_kind = infer_proposal_kind(intent, context_refs)

    message = clip_text(
        intent.get("message") or intent.get("message_preview") or "", 500
    )
    requested_action = str(intent.get("requested_action") or "")
    note_path = str(intent.get("note_path") or "")
    goal_ids = (
        intent.get("goal_ids") if isinstance(intent.get("goal_ids"), list) else []
    )

    if proposal_kind == "review_action_request":
        summary = f"Review requested Obsidian action: {requested_action}"
        message_markdown = (
            f"You requested `{requested_action}` from Obsidian.\n\n"
            "I can turn this into a safe, explicit action proposal, but execution should "
            "stay behind approval."
        )
        suggested_actions = [
            {
                "type": "draft_action_proposal",
                "label": f"Draft approval proposal for `{requested_action}`",
                "requires_approval": True,
            },
            {
                "type": "ask_clarifying_question",
                "label": "Ask what constraints should apply before executing",
                "requires_approval": False,
            },
        ]
    elif proposal_kind == "next_goal_step":
        goal_text = ", ".join(str(goal) for goal in goal_ids) or "current goal"
        task_candidates = candidate_obsidian_tasks(context_refs, goal_ids)
        chosen_task = first_task_text(task_candidates)

        if chosen_task:
            summary = chosen_task
            message_markdown = (
                f"Your next useful action for `{goal_text}` is:\n\n"
                f"**{chosen_task}**\n\n"
                "This was selected from the current Obsidian task context, not invented."
            )
            suggested_actions = [
                {
                    "type": "suggest_next_step",
                    "label": chosen_task,
                    "requires_approval": False,
                },
                {
                    "type": "draft_task",
                    "label": chosen_task,
                    "requires_approval": True,
                    "title": chosen_task,
                    "goal_id": str(goal_ids[0]) if goal_ids else "",
                    "priority": str(task_candidates[0].get("priority") or "normal"),
                    "estimated_minutes": task_candidates[0].get("estimated_minutes")
                    or 15,
                },
            ]
        else:
            summary = f"Pick a small next step for {goal_text}"
            message_markdown = (
                f"Based on your Obsidian intent, the useful next move is a tiny step tied to "
                f"`{goal_text}`.\n\n"
                f"Message: {message or 'No message body provided.'}"
            )
            suggested_actions = [
                {
                    "type": "suggest_next_step",
                    "label": "Choose one 5-15 minute next action",
                    "requires_approval": False,
                },
                {
                    "type": "draft_task",
                    "label": "Draft an Obsidian task, do not write it yet",
                    "requires_approval": True,
                },
            ]
    elif proposal_kind == "next_task_step":
        summary = "Pick a next task from Obsidian context"
        message_markdown = (
            "Obsidian context already has open tasks. The planner should choose one "
            "small, low-friction next step instead of inventing a new system."
        )
        suggested_actions = [
            {
                "type": "select_existing_task",
                "label": "Select one existing task as next action",
                "requires_approval": False,
            }
        ]
    else:
        summary = "Clarify or make a small plan"
        message_markdown = (
            "I need either a goal, a task, or a desired mode to choose the best next step.\n\n"
            f"Message: {message or 'No message body provided.'}"
        )
        suggested_actions = [
            {
                "type": "ask_clarifying_question",
                "label": "Ask for goal/category and desired strictness",
                "requires_approval": False,
            }
        ]

    proposal = {
        "schema_version": "obsidian_proposal.v1",
        "proposal_id": f"proposal-{intent_id}",
        "intent_id": intent_id,
        "status": "proposed",
        "source": "obsidian-intent-planner",
        "surface": "obsidian",
        "created_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "proposal_kind": proposal_kind,
        "summary": summary,
        "message_markdown": message_markdown,
        "note_path": note_path,
        "goal_ids": goal_ids,
        "task_ids": (
            intent.get("task_ids") if isinstance(intent.get("task_ids"), list) else []
        ),
        "suggested_actions": suggested_actions,
        "execution_policy": PROPOSAL_EXECUTION_POLICY,
        "context_refs": context_refs,
    }
    proposal["markdown"] = build_markdown(proposal)
    return proposal


def write_proposal(ai_dir: Path, proposal: dict[str, Any]) -> dict[str, Path]:
    outbox = ai_dir / "outbox" / "to-obsidian"
    proposal_id = str(proposal.get("proposal_id") or "proposal")

    json_path = outbox / "proposals" / f"{proposal_id}.json"
    md_path = outbox / "proposals" / f"{proposal_id}.md"
    current_json_path = outbox / "current-proposal.json"
    current_md_path = outbox / "current-proposal.md"

    atomic_write_json(json_path, proposal)
    atomic_write_text(md_path, str(proposal.get("markdown") or ""))
    atomic_write_json(current_json_path, proposal)
    atomic_write_text(current_md_path, str(proposal.get("markdown") or ""))

    return {
        "json": json_path,
        "markdown": md_path,
        "current_json": current_json_path,
        "current_markdown": current_md_path,
    }


def run_planner(ai_dir: str | Path, *, write: bool = False) -> dict[str, Any]:
    root = Path(ai_dir).expanduser()
    intent_path, intent = latest_pending_intent(root)

    if not intent:
        return {
            "schema_version": "obsidian_planner_result.v1",
            "status": "no_pending_intent",
            "message": "No pending Obsidian intent found.",
        }

    context = build_agent_context(root)
    proposal = build_proposal(intent, context)

    result: dict[str, Any] = {
        "schema_version": "obsidian_planner_result.v1",
        "status": "proposal_built",
        "intent_path": str(intent_path) if intent_path else "",
        "proposal": proposal,
    }

    if write:
        paths = write_proposal(root, proposal)
        result["written_paths"] = {key: str(value) for key, value in paths.items()}

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build safe Obsidian proposal from pending intent"
    )
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument(
        "--write", action="store_true", help="Write proposal to outbox/to-obsidian"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planner result without writing"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_planner(args.ai_dir, write=args.write and not args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
