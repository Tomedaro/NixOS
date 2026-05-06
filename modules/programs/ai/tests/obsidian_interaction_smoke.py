#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.obsidian_interaction import (  # noqa: E402
    inactive_interaction,
    interaction_from_phone_nudge,
    make_action_payload,
    make_message_payload,
    markdown_for_interaction,
    write_current_interaction,
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_nudge_interaction_outputs_json_and_markdown() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-interaction-") as tmp:
        ai_dir = Path(tmp) / "AI"
        nudge = {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "nudge_id": "n-test",
            "created_at": "2026-05-06T10:00:00+00:00",
            "updated_at": "2026-05-06T10:00:00+00:00",
            "source": "llm-planner",
            "planner_mode": "help-now",
            "urgency": "normal",
            "message": "Do 5 Anki cards.",
            "recommended_next_action": "Open Anki and stop after 5 cards.",
            "actions": [
                {"action": "ack_nudge", "label": "Done"},
                {"action": "snooze_nudge", "label": "Not now", "snooze_minutes": 15},
            ],
        }

        written = write_current_interaction(ai_dir, interaction_from_phone_nudge(nudge))
        outbox = ai_dir / "outbox/to-obsidian"

        assert written["schema_version"] == "obsidian_interaction.v1"
        assert written["interaction_id"] == "n-test"
        assert written["kind"] == "nudge"
        assert written["status"] == "active"

        data = read_json(outbox / "current-interaction.json")
        markdown = (outbox / "current-interaction.md").read_text(encoding="utf-8")

        assert data["interaction_id"] == "n-test"
        assert "Do 5 Anki cards." in markdown
        assert "`ack_nudge`" in markdown
        assert "`snooze_nudge`" in markdown
        assert "AI/inbox/from-obsidian/messages/*.json" in markdown


def test_inactive_interaction_is_renderable() -> None:
    payload = inactive_interaction(generated_at="2026-05-06T10:00:00+00:00")
    markdown = markdown_for_interaction(payload)

    assert payload["status"] == "inactive"
    assert payload["kind"] == "inactive"
    assert "Status: `inactive`" in markdown


def test_message_payload() -> None:
    payload = make_message_payload(
        "Plan my study session.",
        conversation_id="study",
        created_at="2026-05-06T10:00:00+00:00",
    )

    assert payload["schema_version"] == "obsidian_message.v1"
    assert payload["surface"] == "obsidian"
    assert payload["conversation_id"] == "study"
    assert payload["text"] == "Plan my study session."


def test_action_payload() -> None:
    payload = make_action_payload(
        "ack_nudge",
        interaction_id="n-test",
        created_at="2026-05-06T10:00:00+00:00",
        nudge_id="n-test",
    )

    assert payload["schema_version"] == "obsidian_action.v1"
    assert payload["surface"] == "obsidian"
    assert payload["interaction_id"] == "n-test"
    assert payload["action"] == "ack_nudge"
    assert payload["payload"]["nudge_id"] == "n-test"


def run_all() -> None:
    tests = [
        test_write_nudge_interaction_outputs_json_and_markdown,
        test_inactive_interaction_is_renderable,
        test_message_payload,
        test_action_payload,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
