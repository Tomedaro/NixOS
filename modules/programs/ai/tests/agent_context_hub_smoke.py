#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.agent_context import build_agent_context


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def test_context_hub_attaches_provider_snapshot() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-") as tmp:
        ai_dir = Path(tmp) / "AI"
        outbox = ai_dir / "outbox/to-phone"

        nudge = {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-context-hub",
            "created_at": "2026-05-06T12:00:00+00:00",
            "updated_at": "2026-05-06T12:00:00+00:00",
            "source": "llm-planner",
            "planner_mode": "help-now",
            "message": "Do one tiny step.",
            "recommended_next_action": "Open Anki.",
            "actions": [],
        }

        write_json(outbox / "current-nudge.json", nudge)
        write_json(
            outbox / "current-question.json",
            {
                "schema_version": "phone_interaction.v1",
                "kind": "question",
                "status": "inactive",
                "updated_at": "2026-05-06T12:00:00+00:00",
            },
        )
        write_json(
            outbox / "interaction-state.json",
            {
                "schema_version": "phone_interaction_state.v1",
                "updated_at": "2026-05-06T12:00:00+00:00",
                "source": "llm-planner",
                "planner_mode": "help-now",
                "active_nudge": nudge,
                "active_question": None,
            },
        )

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        hub = context["context_hub"]

        assert hub["schema_version"] == "context_hub.v1"
        assert hub["provider_count"] >= 6

        providers = {provider["name"]: provider for provider in hub["providers"]}
        assert providers["interaction"]["available"] is True
        assert providers["interaction"]["facts"]["active_nudge_id"] == "n-context-hub"
        assert "obsidian" in providers
        assert "activitywatch" in providers


def test_obsidian_provider_accepts_future_context_file() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-obsidian-") as tmp:
        ai_dir = Path(tmp) / "AI"

        write_json(
            ai_dir / "state/obsidian/context.json",
            {
                "active_note": "Goals/Today.md",
                "open_tasks": 3,
                "communication_mode": "mentor",
            },
        )
        write_json(
            ai_dir / "outbox/to-phone/interaction-state.json",
            {
                "schema_version": "phone_interaction_state.v1",
                "updated_at": "2026-05-06T12:00:00+00:00",
                "active_nudge": None,
                "active_question": None,
            },
        )

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        obsidian = context["context_hub"]["facts"]["obsidian"]

        assert obsidian["active_note"] == "Goals/Today.md"
        assert obsidian["communication_mode"] == "mentor"


def test_context_hub_is_nonfatal_without_provider_files() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-empty-") as tmp:
        ai_dir = Path(tmp) / "AI"

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        hub = context["context_hub"]

        assert hub["schema_version"] == "context_hub.v1"
        assert "warnings" in hub
        assert "activitywatch" in hub["facts"]


def run_all() -> None:
    tests = [
        test_context_hub_attaches_provider_snapshot,
        test_obsidian_provider_accepts_future_context_file,
        test_context_hub_is_nonfatal_without_provider_files,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
