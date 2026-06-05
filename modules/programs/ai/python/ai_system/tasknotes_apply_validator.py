"""Non-writing deterministic TaskNotes apply/promote validator.

This is not the TaskNotes apply gate. It only validates whether a reviewed
Obsidian task draft is eligible for a future deterministic apply/promote step.

The validator never writes TaskNotes, live action files, journals, or events.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_system.obsidian_contracts import contains_direct_execution


RESULT_SCHEMA_VERSION = "tasknotes_apply_validation_result.v1"
DRAFT_SCHEMA_VERSION = "obsidian_task_draft.v1"
REVIEWED_PROPOSAL_SCHEMA_VERSION = "obsidian_reviewed_proposal.v1"

# These top-level draft fields are required safety assertions, not direct
# execution requests when set to their safe values. They are checked explicitly
# before the generic direct-execution scan.
TOP_LEVEL_DRAFT_SAFETY_FIELDS = {
    "requires_templater_apply",
    "executes_now",
    "writes_live_action_queue",
    "edits_obsidian_now",
}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def default_approval_paths(ai_dir: str | Path) -> list[Path]:
    root = Path(ai_dir)
    return [
        root / "state" / "obsidian" / "current-approved-proposal.json",
        root / "outbox" / "to-obsidian" / "current-approved-proposal.json",
        root / "current-approved-proposal.json",
    ]


def load_current_approved_proposal(
    *,
    ai_dir: str | Path | None = None,
    approval_path: str | Path | None = None,
) -> tuple[dict[str, Any], str]:
    if approval_path is not None:
        path = Path(approval_path)
        return read_json_object(path), str(path)

    if ai_dir is None:
        return {}, ""

    for path in default_approval_paths(ai_dir):
        data = read_json_object(path)
        if data:
            return data, str(path)

    return {}, ""


def task_id_is_safe(task_id: str) -> bool:
    if not task_id:
        return False

    if task_id in {".", ".."}:
        return False

    if task_id.startswith("."):
        return False

    if "/" in task_id or "\\" in task_id:
        return False

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return all(char in allowed for char in task_id)


def tasks_root_from_tasknotes_dir(tasknotes_dir: str | Path | None) -> Path | None:
    if tasknotes_dir is None:
        return None

    root = Path(tasknotes_dir)
    return root if root.name == "Tasks" else root / "Tasks"


def target_candidate_for(
    *,
    task_id: str,
    tasknotes_dir: str | Path | None,
) -> tuple[str, bool, bool]:
    if not task_id_is_safe(task_id):
        return "", False, False

    relative_path = f"Tasks/{task_id}.md"
    tasks_root = tasks_root_from_tasknotes_dir(tasknotes_dir)
    if tasks_root is None:
        return relative_path, False, False

    candidate = tasks_root / f"{task_id}.md"
    return str(candidate), True, candidate.exists()


def idempotency_key_for(
    *,
    task_id: str,
    source_proposal_id: str,
    source_intent_id: str,
) -> str:
    payload = {
        "source_intent_id": source_intent_id,
        "source_proposal_id": source_proposal_id,
        "task_id": task_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "tasknotes_apply:" + hashlib.sha256(encoded).hexdigest()


def draft_for_direct_execution_scan(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in draft.items()
        if key not in TOP_LEVEL_DRAFT_SAFETY_FIELDS
    }


def direct_execution_present(value: Any) -> bool:
    result = contains_direct_execution(value)
    if isinstance(result, bool):
        return result
    return bool(result)


def validation_result(
    *,
    status: str,
    reasons: list[str],
    warnings: list[str],
    task_id: str,
    source_proposal_id: str,
    source_intent_id: str,
    input_draft_path: str,
    approval_path: str,
    target_tasknotes_path_candidate: str,
    collision_checked: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": status,
        "writes_tasknotes": False,
        "task_id": task_id,
        "source_proposal_id": source_proposal_id,
        "source_intent_id": source_intent_id,
        "input_draft_path": input_draft_path,
        "approval_path": approval_path,
        "target_tasknotes_path_candidate": target_tasknotes_path_candidate,
        "collision_checked": collision_checked,
        "reasons": reasons,
        "warnings": warnings,
    }

    if task_id and source_proposal_id and source_intent_id:
        result["idempotency_key"] = idempotency_key_for(
            task_id=task_id,
            source_proposal_id=source_proposal_id,
            source_intent_id=source_intent_id,
        )

    return result


def validate_tasknotes_apply_candidate(
    draft: dict[str, Any],
    *,
    approval: dict[str, Any] | None = None,
    ai_dir: str | Path | None = None,
    approval_path: str | Path | None = None,
    tasknotes_dir: str | Path | None = None,
    input_draft_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate an `obsidian_task_draft.v1` for future TaskNotes apply.

    This function only reads supplied objects and optional approval JSON. It never
    writes TaskNotes, action files, journals, or events.
    """

    if not isinstance(draft, dict):
        return validation_result(
            status="refused",
            reasons=["draft_not_object"],
            warnings=[],
            task_id="",
            source_proposal_id="",
            source_intent_id="",
            input_draft_path=str(input_draft_path or ""),
            approval_path=str(approval_path or ""),
            target_tasknotes_path_candidate="",
            collision_checked=False,
        )

    if approval is None:
        approval, loaded_approval_path = load_current_approved_proposal(
            ai_dir=ai_dir,
            approval_path=approval_path,
        )
    else:
        loaded_approval_path = str(approval_path or "")

    approval = as_dict(approval)

    reasons: list[str] = []
    warnings: list[str] = []

    task_id = as_str(draft.get("task_id"))
    source_proposal_id = as_str(draft.get("source_proposal_id"))
    source_intent_id = as_str(draft.get("source_intent_id"))

    target_candidate, collision_checked, target_exists = target_candidate_for(
        task_id=task_id,
        tasknotes_dir=tasknotes_dir,
    )

    if tasknotes_dir is None:
        warnings.append("target_collision_not_checked_missing_tasknotes_dir")

    if draft.get("schema_version") != DRAFT_SCHEMA_VERSION:
        reasons.append("wrong_schema_version")

    required_fields = [
        "task_id",
        "title",
        "markdown",
        "tasknote_frontmatter",
        "source_proposal_id",
        "source_intent_id",
        "requires_templater_apply",
        "executes_now",
        "writes_live_action_queue",
        "edits_obsidian_now",
    ]

    for field in required_fields:
        if field not in draft:
            reasons.append(f"missing_{field}")

    for field in ["task_id", "title", "markdown", "source_proposal_id", "source_intent_id"]:
        if field in draft and not as_str(draft.get(field)):
            reasons.append(f"empty_{field}")

    if "tasknote_frontmatter" in draft and not isinstance(
        draft.get("tasknote_frontmatter"), dict
    ):
        reasons.append("invalid_tasknote_frontmatter")

    if draft.get("requires_templater_apply") is not True:
        reasons.append("requires_templater_apply_not_true")

    if draft.get("executes_now") is not False:
        reasons.append("executes_now_not_false")

    if draft.get("writes_live_action_queue") is not False:
        reasons.append("writes_live_action_queue_not_false")

    if draft.get("edits_obsidian_now") is not False:
        reasons.append("edits_obsidian_now_not_false")

    if task_id and not task_id_is_safe(task_id):
        reasons.append("unsafe_task_id")

    if direct_execution_present(draft_for_direct_execution_scan(draft)):
        reasons.append("direct_execution_fields_present")

    if not approval:
        reasons.append("missing_approval")
    else:
        if approval.get("schema_version") != REVIEWED_PROPOSAL_SCHEMA_VERSION:
            reasons.append("approval_wrong_schema_version")

        if approval.get("status") != "review_ready":
            reasons.append("approval_status_not_review_ready")

        if approval.get("proposal_id") != source_proposal_id:
            reasons.append("approval_proposal_mismatch")

        if approval.get("intent_id") != source_intent_id:
            reasons.append("approval_intent_mismatch")

        if approval.get("executes_now") is not False:
            reasons.append("approval_executes_now_not_false")

        if approval.get("writes_live_action_queue") is not False:
            reasons.append("approval_writes_live_action_queue_not_false")

        if approval.get("requires_capability_bridge") is not True:
            reasons.append("approval_requires_capability_bridge_not_true")

    if reasons:
        return validation_result(
            status="refused",
            reasons=reasons,
            warnings=warnings,
            task_id=task_id,
            source_proposal_id=source_proposal_id,
            source_intent_id=source_intent_id,
            input_draft_path=str(input_draft_path or ""),
            approval_path=loaded_approval_path,
            target_tasknotes_path_candidate=target_candidate,
            collision_checked=collision_checked,
        )

    if target_exists:
        return validation_result(
            status="manual_review_required",
            reasons=["target_tasknotes_file_exists"],
            warnings=warnings,
            task_id=task_id,
            source_proposal_id=source_proposal_id,
            source_intent_id=source_intent_id,
            input_draft_path=str(input_draft_path or ""),
            approval_path=loaded_approval_path,
            target_tasknotes_path_candidate=target_candidate,
            collision_checked=collision_checked,
        )

    return validation_result(
        status="accepted",
        reasons=[],
        warnings=warnings,
        task_id=task_id,
        source_proposal_id=source_proposal_id,
        source_intent_id=source_intent_id,
        input_draft_path=str(input_draft_path or ""),
        approval_path=loaded_approval_path,
        target_tasknotes_path_candidate=target_candidate,
        collision_checked=collision_checked,
    )
