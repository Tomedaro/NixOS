#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.agent_context import build_agent_context
from ai_system.obsidian_context import (
    normalize_obsidian_context,
    write_obsidian_context,
)


def test_normalize_bounds_large_fields() -> None:
    context = normalize_obsidian_context(
        {
            "active_note_path": "Goals/Today.md",
            "tags": [f"tag-{i}" for i in range(100)],
            "selected_text": "x" * 3000,
            "open_tasks": [{"text": f"task {i}"} for i in range(100)],
            "recent_notes": [f"Note {i}.md" for i in range(100)],
            "latest_user_message": "y" * 2000,
        }
    )

    assert context["schema_version"] == "obsidian_context.v1"
    assert context["active_note_path"] == "Goals/Today.md"
    assert len(context["active_note_tags"]) == 32
    assert len(context["selected_text_preview"]) <= 1200
    assert len(context["open_tasks"]) == 25
    assert len(context["recent_notes"]) == 25
    assert len(context["latest_user_message_preview"]) <= 600


def test_write_context_outputs_json_markdown_and_feeds_hub() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-context-") as tmp:
        ai_dir = Path(tmp) / "AI"

        written = write_obsidian_context(
            ai_dir,
            {
                "mode": "mentor",
                "active_note_path": "Goals/Today.md",
                "active_note_title": "Today",
                "tags": ["study", "planning"],
                "open_tasks": [
                    {
                        "text": "Review linear algebra notes",
                        "status": "todo",
                        "goal_id": "stem-study",
                    }
                ],
                "current_goal_ids": ["stem-study"],
                "latest_user_message": "Help me pick the next action.",
            },
        )

        assert written["mode"] == "mentor"

        context_path = ai_dir / "state/obsidian/context.json"
        latest_path = ai_dir / "state/obsidian/latest.json"
        status_path = ai_dir / "state/obsidian/status.md"

        assert context_path.exists()
        assert latest_path.exists()
        assert status_path.exists()

        stored = json.loads(context_path.read_text(encoding="utf-8"))
        assert stored["active_note_path"] == "Goals/Today.md"
        assert stored["open_tasks"][0]["goal_id"] == "stem-study"

        agent_context = build_agent_context(ai_dir, now_epoch=1778072400)
        obsidian = agent_context["context_hub"]["facts"]["obsidian"]

        assert obsidian["active_note_path"] == "Goals/Today.md"
        assert obsidian["mode"] == "mentor"
        assert obsidian["current_goal_ids"] == ["stem-study"]


def run_all() -> None:
    tests = [
        test_normalize_bounds_large_fields,
        test_write_context_outputs_json_markdown_and_feeds_hub,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
