#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.context_providers import obsidian_intent_provider
from ai_system.obsidian_approval_bridge import latest_action_file
from ai_system.obsidian_intent_planner import (
    latest_pending_intent,
    pending_intent_files,
)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_planner_ignores_dotfiles_temp_and_non_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ai_dir = Path(tmp) / "AI"
        inbox = ai_dir / "inbox/obsidian/messages"

        valid = inbox / "100_valid.json"
        write_json(
            valid,
            {
                "schema_version": "obsidian_intent.v1",
                "intent_id": "valid-intent",
                "kind": "message",
                "status": "pending",
                "message": "valid",
            },
        )

        write_json(
            inbox / ".999_hidden.json",
            {
                "schema_version": "obsidian_intent.v1",
                "intent_id": "hidden-intent",
                "kind": "message",
                "status": "pending",
                "message": "hidden",
            },
        )
        (inbox / "998_partial.json.tmp").write_text("{not complete", encoding="utf-8")
        (inbox / "README.md").write_text("not a queue item", encoding="utf-8")

        files = pending_intent_files(ai_dir)
        assert files == [valid]

        path, intent = latest_pending_intent(ai_dir)
        assert path == valid
        assert intent["intent_id"] == "valid-intent"


def test_context_provider_ignores_dotfiles_temp_and_non_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ai_dir = Path(tmp) / "AI"
        inbox = ai_dir / "inbox/obsidian/messages"

        valid = inbox / "100_valid.json"
        write_json(
            valid,
            {
                "schema_version": "obsidian_intent.v1",
                "intent_id": "valid-intent",
                "kind": "message",
                "status": "pending",
                "message_preview": "valid",
            },
        )

        write_json(
            inbox / ".999_hidden.json",
            {
                "schema_version": "obsidian_intent.v1",
                "intent_id": "hidden-intent",
                "kind": "message",
                "status": "pending",
                "message_preview": "hidden",
            },
        )
        (inbox / "998_partial.json.tmp").write_text("{not complete", encoding="utf-8")
        (inbox / "README.md").write_text("not a queue item", encoding="utf-8")

        result = obsidian_intent_provider(ai_dir)
        assert result["available"] is True
        facts = result["facts"]
        assert facts["latest"]["intent_id"] == "valid-intent"
        assert [item["intent_id"] for item in facts["recent"]] == ["valid-intent"]


def test_approval_bridge_ignores_dotfiles_temp_and_non_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ai_dir = Path(tmp) / "AI"
        inbox = ai_dir / "inbox/obsidian/actions"

        valid = inbox / "100_approve.json"
        write_json(
            valid,
            {
                "schema_version": "obsidian_proposal_action.v1",
                "decision": "approve_proposal",
                "proposal_id": "valid-proposal",
                "approved": True,
            },
        )

        write_json(
            inbox / ".999_hidden.json",
            {
                "schema_version": "obsidian_proposal_action.v1",
                "decision": "approve_proposal",
                "proposal_id": "hidden-proposal",
                "approved": True,
            },
        )
        (inbox / "998_partial.json.tmp").write_text("{not complete", encoding="utf-8")
        (inbox / "README.md").write_text("not a queue item", encoding="utf-8")

        assert latest_action_file(ai_dir) == valid


def main() -> None:
    tests = [
        test_planner_ignores_dotfiles_temp_and_non_json,
        test_context_provider_ignores_dotfiles_temp_and_non_json,
        test_approval_bridge_ignores_dotfiles_temp_and_non_json,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    main()
