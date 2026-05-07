"""Read-only context providers for the local AI context hub.

Providers normalize local state into bounded facts for planners/LLMs. They must
not write files, clear interactions, enqueue actions, or classify lifecycle
outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_system.context_schema import (
    context_hub_snapshot,
    provider_result,
    provider_unavailable,
)
from ai_system.interaction_lifecycle import clear_reason_for_active_nudge
from ai_system.queue import list_stable_json_queue_files


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def first_readable_json(paths: list[Path]) -> tuple[Path | None, dict[str, Any]]:
    for path in paths:
        data = read_json(path)
        if data:
            return path, data

    return None, {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    try:
        return int(value)
    except Exception:
        return None


def status_from_compact(value: Any) -> str:
    if not isinstance(value, dict):
        return "none"

    return str(value.get("status") or "present")


def compact_recovery_facts(data: dict[str, Any]) -> dict[str, Any]:
    target = as_dict(data.get("target"))
    lifecycle = as_dict(data.get("lifecycle"))
    classification = as_dict(data.get("classification"))
    last_lifecycle_event = as_dict(data.get("last_lifecycle_event"))
    last_event = last_lifecycle_event or as_dict(data.get("last_event"))

    target_id = (
        data.get("target_id")
        or target.get("target_id")
        or lifecycle.get("target_id")
        or last_event.get("target_id")
        or ""
    )

    return {
        "schema_version": "recovery_context.v1",
        "status": str(data.get("status") or ""),
        "recovery_id": str(data.get("recovery_id") or ""),
        "target_id": str(target_id),
        "target_name": str(target.get("name") or last_event.get("target_name") or ""),
        "started_at": str(data.get("started_at") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "classification_status": str(classification.get("status") or ""),
        "classification_reason": str(classification.get("reason") or ""),
        "evidence_quality": str(lifecycle.get("evidence_quality") or ""),
        "event_count": as_int(lifecycle.get("event_count")),
        "flapping_count": as_int(lifecycle.get("flapping_count")),
        "rapid_exit_detected": bool(lifecycle.get("rapid_exit_detected", False)),
        "total_observed_dwell_seconds": as_int(
            lifecycle.get("total_observed_dwell_seconds")
        ),
        "longest_observed_dwell_seconds": as_int(
            lifecycle.get("longest_observed_dwell_seconds")
        ),
        "last_event": str(
            last_event.get("event")
            or last_event.get("event_type")
            or last_event.get("action")
            or ""
        ),
        "last_event_at": str(
            last_event.get("timestamp")
            or last_event.get("processed_at")
            or data.get("updated_at")
            or ""
        ),
    }


def compact_intervention_facts(data: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "schema_version",
        "total",
        "shown_count",
        "acted_count",
        "started_count",
        "terminal_count",
        "success_count",
        "action_rate",
        "start_rate",
        "terminal_success_rate",
        "by_outcome",
    ]

    return {key: data[key] for key in keys if key in data}


def compact_anki_facts(data: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "updated_at",
        "due",
        "total_due",
        "new_count",
        "learning_count",
        "review_count",
        "deck_count",
        "deck",
        "decks",
        "status",
    ]

    facts = {key: data[key] for key in keys if key in data}

    if not facts and data:
        facts["available_keys"] = sorted(str(key) for key in data.keys())[:20]

    return facts


def interaction_provider(ai_dir: Path) -> dict[str, Any]:
    outbox = ai_dir / "outbox" / "to-phone"
    state_path = outbox / "interaction-state.json"
    nudge_path = outbox / "current-nudge.json"
    question_path = outbox / "current-question.json"

    state = read_json(state_path)
    nudge = read_json(nudge_path)
    question = read_json(question_path)

    if not state and not nudge and not question:
        return provider_unavailable(
            "interaction",
            "no phone interaction files found",
            source_paths=[str(state_path), str(nudge_path), str(question_path)],
        )

    active_nudge = (
        state.get("active_nudge") if isinstance(state.get("active_nudge"), dict) else {}
    )
    active_question = (
        state.get("active_question")
        if isinstance(state.get("active_question"), dict)
        else {}
    )

    current_nudge = dict(nudge)
    if current_nudge.get("status") == "active":
        current_nudge.setdefault("kind", "nudge")

    clear_reason = (
        clear_reason_for_active_nudge({"active_nudge": current_nudge}) or "none"
    )

    warnings: list[str] = []
    if clear_reason not in {"none", "unknown"}:
        warnings.append(f"active nudge should clear: {clear_reason}")

    state_nudge_id = str(active_nudge.get("nudge_id") or "")
    current_nudge_id = str(nudge.get("nudge_id") or "")
    if state_nudge_id and current_nudge_id and state_nudge_id != current_nudge_id:
        warnings.append("interaction-state active_nudge differs from current-nudge")

    facts = {
        "state_updated_at": state.get("updated_at", ""),
        "planner_mode": state.get("planner_mode") or nudge.get("planner_mode") or "",
        "active_nudge_status": status_from_compact(state.get("active_nudge")),
        "active_nudge_id": state_nudge_id,
        "current_nudge_status": str(
            nudge.get("status") or ("missing" if not nudge else "unknown")
        ),
        "current_nudge_id": current_nudge_id,
        "current_nudge_clear_reason": clear_reason,
        "active_question_status": status_from_compact(state.get("active_question")),
        "active_question_id": str(active_question.get("question_id") or ""),
        "current_question_status": str(
            question.get("status") or ("missing" if not question else "unknown")
        ),
        "current_question_id": str(question.get("question_id") or ""),
    }

    return provider_result(
        "interaction",
        available=True,
        facts=facts,
        warnings=warnings,
        freshness="current",
        source_paths=[str(state_path), str(nudge_path), str(question_path)],
    )


def anki_provider(ai_dir: Path) -> dict[str, Any]:
    paths = [
        ai_dir / "state" / "anki" / "latest.json",
        ai_dir / "state" / "anki" / "status.json",
        ai_dir / "state" / "anki" / "anki-status.json",
    ]
    path, data = first_readable_json(paths)

    if not data or path is None:
        return provider_unavailable(
            "anki",
            "no Anki state JSON found",
            source_paths=[str(path) for path in paths],
        )

    return provider_result(
        "anki",
        available=True,
        facts=compact_anki_facts(data),
        freshness="from_state",
        source_paths=[str(path)],
    )


def recovery_provider(ai_dir: Path) -> dict[str, Any]:
    paths = [
        ai_dir / "state" / "recovery" / "current.json",
        ai_dir / "state" / "recovery" / "state.json",
        ai_dir / "state" / "recovery" / "latest.json",
        ai_dir / "state" / "recovery" / "status.json",
        ai_dir / "state" / "recovery" / "recovery-state.json",
    ]
    path, data = first_readable_json(paths)

    if not data or path is None:
        return provider_unavailable(
            "recovery",
            "no recovery state JSON found",
            source_paths=[str(path) for path in paths],
        )

    return provider_result(
        "recovery",
        available=True,
        facts=compact_recovery_facts(data),
        freshness="from_state",
        source_paths=[str(path)],
    )


def intervention_provider(ai_dir: Path) -> dict[str, Any]:
    paths = [
        ai_dir / "state" / "interventions" / "latest.json",
        ai_dir / "state" / "interventions" / "stats.json",
        ai_dir / "state" / "interventions" / "status.json",
    ]
    path, data = first_readable_json(paths)

    if not data or path is None:
        return provider_unavailable(
            "interventions",
            "no intervention outcome JSON found",
            source_paths=[str(path) for path in paths],
        )

    return provider_result(
        "interventions",
        available=True,
        facts=compact_intervention_facts(data),
        freshness="from_state",
        source_paths=[str(path)],
    )


def obsidian_provider(ai_dir: Path) -> dict[str, Any]:
    paths = [
        ai_dir / "state" / "obsidian" / "context.json",
        ai_dir / "state" / "obsidian" / "latest.json",
    ]
    path, data = first_readable_json(paths)

    if not data or path is None:
        return provider_unavailable(
            "obsidian",
            "no Obsidian context JSON found yet",
            source_paths=[str(path) for path in paths],
        )

    return provider_result(
        "obsidian",
        available=True,
        facts=data,
        freshness="from_state",
        source_paths=[str(path)],
    )


def activitywatch_provider(ai_dir: Path) -> dict[str, Any]:
    paths = [
        ai_dir / "state" / "activitywatch" / "context.json",
        ai_dir / "state" / "activitywatch" / "latest.json",
    ]
    path, data = first_readable_json(paths)

    if not data or path is None:
        return provider_unavailable(
            "activitywatch",
            "no ActivityWatch context JSON found yet",
            source_paths=[str(path) for path in paths],
        )

    return provider_result(
        "activitywatch",
        available=True,
        facts=data,
        freshness="from_state",
        source_paths=[str(path)],
    )


def compact_obsidian_intent(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "obsidian_intent_context.v1",
        "intent_id": str(intent.get("intent_id") or ""),
        "kind": str(intent.get("kind") or ""),
        "status": str(intent.get("status") or ""),
        "created_at": str(intent.get("created_at") or ""),
        "timestamp_epoch": intent.get("timestamp_epoch"),
        "surface": str(intent.get("surface") or ""),
        "mode": str(intent.get("mode") or ""),
        "note_path": str(intent.get("note_path") or ""),
        "message_preview": str(intent.get("message_preview") or ""),
        "requested_action": str(intent.get("requested_action") or ""),
        "goal_ids": (
            intent.get("goal_ids") if isinstance(intent.get("goal_ids"), list) else []
        ),
        "task_ids": (
            intent.get("task_ids") if isinstance(intent.get("task_ids"), list) else []
        ),
        "execution_policy": str(intent.get("execution_policy") or ""),
    }


def obsidian_intent_provider(ai_dir: Path) -> dict[str, Any]:
    inbox = ai_dir / "inbox" / "obsidian" / "messages"

    if not inbox.exists():
        return provider_unavailable(
            "obsidian_intent",
            "no Obsidian intent inbox found yet",
            source_paths=[str(inbox)],
        )

    ready, _unstable, _ignored = list_stable_json_queue_files(inbox, 0)

    files = sorted(
        ready,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    recent: list[dict[str, Any]] = []
    source_paths: list[str] = []

    for path in files[:5]:
        data = read_json(path)
        if not data:
            continue

        recent.append(compact_obsidian_intent(data))
        source_paths.append(str(path))

    if not recent:
        return provider_unavailable(
            "obsidian_intent",
            "no pending Obsidian intents found",
            source_paths=[str(inbox)],
        )

    return provider_result(
        "obsidian_intent",
        available=True,
        facts={
            "schema_version": "obsidian_intent_provider.v1",
            "pending_count_seen": len(recent),
            "latest": recent[0],
            "recent": recent,
        },
        freshness="pending_queue",
        source_paths=source_paths,
    )


def build_context_provider_snapshot(
    ai_dir: str | Path,
    *,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    root = Path(ai_dir).expanduser()

    providers = [
        interaction_provider(root),
        anki_provider(root),
        recovery_provider(root),
        intervention_provider(root),
        obsidian_provider(root),
        obsidian_intent_provider(root),
        activitywatch_provider(root),
    ]

    return context_hub_snapshot(providers, now_epoch=now_epoch)
