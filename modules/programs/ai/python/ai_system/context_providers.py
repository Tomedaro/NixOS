"""Read-only context providers for the local AI context hub.

Providers normalize local state into facts for planners/LLMs. They must not write
files, clear interactions, enqueue actions, or classify lifecycle outcomes.
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


def status_from_compact(value: Any) -> str:
    if not isinstance(value, dict):
        return "none"

    return str(value.get("status") or "present")


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
        facts=data,
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

    facts = {
        "status": data.get("status", ""),
        "target_id": (
            data.get("target_id")
            or (data.get("target") if isinstance(data.get("target"), str) else "")
            or (
                data.get("target", {}).get("target_id")
                if isinstance(data.get("target"), dict)
                else ""
            )
        ),
        "updated_at": data.get("updated_at", ""),
        "raw": data,
    }

    return provider_result(
        "recovery",
        available=True,
        facts=facts,
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
        facts=data,
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
        activitywatch_provider(root),
    ]

    return context_hub_snapshot(providers, now_epoch=now_epoch)
