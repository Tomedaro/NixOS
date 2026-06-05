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


def test_recovery_provider_uses_compact_facts_without_raw() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-recovery-") as tmp:
        ai_dir = Path(tmp) / "AI"

        write_json(
            ai_dir / "state/recovery/current.json",
            {
                "schema_version": "recovery_session.v1",
                "recovery_id": "recovery-anki-test",
                "status": "possible_success",
                "started_at": "2026-05-06T12:00:00+00:00",
                "updated_at": "2026-05-06T12:05:24+00:00",
                "target": {
                    "target_id": "anki",
                    "name": "Anki",
                },
                "classification": {
                    "status": "possible_success",
                    "reason": "observed_target_dwell_reached_success_threshold",
                },
                "lifecycle": {
                    "target_id": "anki",
                    "event_count": 1,
                    "flapping_count": 0,
                    "evidence_quality": "normal",
                    "rapid_exit_detected": False,
                    "total_observed_dwell_seconds": 324,
                    "longest_observed_dwell_seconds": 324,
                },
                "last_lifecycle_event": {
                    "event": "recovery_possible_success",
                    "timestamp": "2026-05-06T12:05:24+00:00",
                    "target_id": "anki",
                },
                "large_raw_payload_that_should_not_leak": {
                    "intervals": [{"x": "y"} for _ in range(50)],
                },
            },
        )

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        recovery = context["context_hub"]["facts"]["recovery"]

        assert recovery["schema_version"] == "recovery_context.v1"
        assert recovery["status"] == "possible_success"
        assert recovery["target_id"] == "anki"
        assert recovery["target_name"] == "Anki"
        assert recovery["total_observed_dwell_seconds"] == 324
        assert recovery["last_event"] == "recovery_possible_success"
        assert "raw" not in recovery
        assert "large_raw_payload_that_should_not_leak" not in recovery



def test_context_hub_includes_tasknotes_read_context_metadata() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-tasknotes-") as tmp:
        root = Path(tmp)
        ai_dir = root / "AI"
        tasks_root = root / "TaskNotes" / "Tasks"
        ai_dir.mkdir()
        tasks_root.mkdir(parents=True)

        for index in range(14):
            body = f"Task {index}\n" + ("x" * (5000 if index == 0 else 100))
            (tasks_root / f"{index:02d}.md").write_text(body, encoding="utf-8")

        before = {
            path.relative_to(tasks_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(tasks_root.rglob("*"))
            if path.is_file()
        }

        context = build_agent_context(ai_dir, now_epoch=1778072400)

        after = {
            path.relative_to(tasks_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(tasks_root.rglob("*"))
            if path.is_file()
        }

        assert before == after

        hub = context["context_hub"]
        providers = {provider["name"]: provider for provider in hub["providers"]}
        assert "tasknotes.read_context" in providers

        provider = providers["tasknotes.read_context"]
        facts = provider["facts"]

        assert provider["available"] is True
        assert facts["module"] == "tasknotes.read_context"
        assert facts["status"] == "ok"
        assert facts["available"] is True
        assert facts["generated_at_epoch"] == 1778072400
        assert facts["limits"]["file_limit"] == 12
        assert facts["limits"]["bytes_per_file"] == 4096
        assert facts["item_count"] == 12
        assert facts["omitted"]["over_limit"] == 2
        assert facts["truncated"] is True
        assert facts["source"]["kind"] == "TaskNotes/Tasks"
        assert facts["source"]["tasks_root"] == str(tasks_root)
        assert all(path.startswith("Tasks/") for path in facts["provenance"]["item_paths"])
        assert facts["may_mutate_tasknotes"] is False
        assert facts["required_action_capabilities"] == []

        serialized_provider = json.dumps(provider, sort_keys=True)
        forbidden = [
            "content",
            "action_payload",
            "promote_task_proposal",
            "tasknotes.promote",
            "apply_tasknotes",
            "AI/inbox/actions",
        ]
        assert all(value not in serialized_provider for value in forbidden)


def test_context_hub_tasknotes_missing_is_nonfatal() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-context-hub-tasknotes-missing-") as tmp:
        ai_dir = Path(tmp) / "AI"

        context = build_agent_context(ai_dir, now_epoch=1778072400)
        hub = context["context_hub"]

        providers = {provider["name"]: provider for provider in hub["providers"]}
        provider = providers["tasknotes.read_context"]
        facts = provider["facts"]

        assert provider["available"] is False
        assert facts["status"] == "missing"
        assert facts["available"] is False
        assert facts["item_count"] == 0
        assert facts["may_mutate_tasknotes"] is False
        assert facts["required_action_capabilities"] == []
        assert hub["schema_version"] == "context_hub.v1"

def run_all() -> None:
    tests = [
        test_context_hub_attaches_provider_snapshot,
        test_obsidian_provider_accepts_future_context_file,
        test_context_hub_is_nonfatal_without_provider_files,
        test_recovery_provider_uses_compact_facts_without_raw,
        test_context_hub_includes_tasknotes_read_context_metadata,
        test_context_hub_tasknotes_missing_is_nonfatal,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
