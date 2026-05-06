#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path

from ai_system.agent_context import build_agent_context, write_agent_context


NOW = 1777914000


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def test_empty_context() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-empty-") as tmp:
        ai_dir = Path(tmp) / "AI"
        context = build_agent_context(ai_dir, now_epoch=NOW)

        assert context["schema_version"] == "agent_context.v1"
        assert context["derived_facts"]["has_active_session"] is False
        assert context["derived_facts"]["has_active_nudge"] is False
        assert context["derived_facts"]["has_active_question"] is False
        assert context["derived_facts"]["has_active_recovery"] is False
        assert context["derived_facts"]["anki_due"] == 0
        assert context["recent_events"]["actions"] == []


def test_active_state_facts() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-active-") as tmp:
        ai_dir = Path(tmp) / "AI"

        write_json(ai_dir / "state/session/current.json", {
            "session_id": "s-active",
            "status": "active",
            "task": "Write tests",
        })
        write_json(ai_dir / "state/anki/status.json", {
            "due": 7,
        })
        write_json(ai_dir / "state/desktop/now.json", {
            "verdict": "distracted",
        })
        write_json(ai_dir / "state/recovery/current.json", {
            "recovery_id": "r-active",
            "status": "active",
        })
        write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
            "status": "active",
            "nudge_id": "n-active",
        })
        write_json(ai_dir / "outbox/to-phone/current-question.json", {
            "status": "active",
            "question_id": "q-active",
        })
        write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
            "active_nudge": {
                "status": "active",
                "nudge_id": "n-active",
            },
            "active_question": {
                "status": "active",
                "question_id": "q-active",
            },
        })

        context = build_agent_context(ai_dir, now_epoch=NOW)
        facts = context["derived_facts"]

        assert facts["has_active_session"] is True
        assert facts["has_active_nudge"] is True
        assert facts["has_active_question"] is True
        assert facts["has_active_recovery"] is True
        assert facts["anki_due"] == 7
        assert facts["desktop_verdict"] == "distracted"



def test_anki_totals_due_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-anki-totals-") as tmp:
        ai_dir = Path(tmp) / "AI"

        write_json(ai_dir / "state/anki/status.json", {
            "available": True,
            "totals": {
                "due": 6,
                "review_due": 6,
            },
        })

        context = build_agent_context(ai_dir, now_epoch=NOW)
        facts = context["derived_facts"]

        assert facts["anki_due"] == 6


def test_recent_snooze_and_terminal_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-recent-") as tmp:
        ai_dir = Path(tmp) / "AI"
        date = "2026-05-04"

        append_jsonl(ai_dir / f"events/actions/{date}.jsonl", [
            {
                "event": "snooze_nudge",
                "timestamp_epoch": NOW - 60,
                "snooze_minutes": 15,
                "nudge_id": "n-snooze",
            }
        ])

        write_json(ai_dir / "state/recovery/current.json", {
            "recovery_id": "r-terminal",
            "status": "possible_success",
            "updated_at": "2026-05-05T09:38:00+02:00",
            "last_lifecycle_event": {
                "event": "recovery_possible_success",
                "timestamp_epoch": NOW - 120,
            },
        })

        context = build_agent_context(ai_dir, now_epoch=NOW, recent_days=1)
        facts = context["derived_facts"]

        assert facts["recent_snooze"] is True
        assert facts["recent_snooze_age_seconds"] == 60
        assert facts["latest_snooze"]["event"] == "snooze_nudge"
        assert facts["recent_terminal_recovery"] is True
        assert facts["recent_terminal_recovery_age_seconds"] == 120


def test_event_tails_are_bounded_and_sorted() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-events-") as tmp:
        ai_dir = Path(tmp) / "AI"
        date = "2026-05-04"

        append_jsonl(ai_dir / f"events/phone/{date}.jsonl", [
            {
                "event": f"phone_event_{index}",
                "timestamp_epoch": NOW - (30 - index),
            }
            for index in range(30)
        ])

        context = build_agent_context(ai_dir, now_epoch=NOW, event_limit=5, recent_days=1)
        events = context["recent_events"]["phone"]

        assert len(events) == 5
        assert [item["event"] for item in events] == [
            "phone_event_25",
            "phone_event_26",
            "phone_event_27",
            "phone_event_28",
            "phone_event_29",
        ]



def test_legacy_anki_status_fallback() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-legacy-anki-") as tmp:
        ai_dir = Path(tmp) / "AI"

        write_json(ai_dir / "anki/status.json", {
            "available": True,
            "totals": {
                "due": 862,
                "review_due": 862,
                "learning": 70,
                "new": 259785,
            },
        })

        context = build_agent_context(ai_dir)
        facts = context["derived_facts"]

        assert facts["anki_due"] == 862

def test_write_agent_context() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-agent-context-write-") as tmp:
        ai_dir = Path(tmp) / "AI"
        context = write_agent_context(ai_dir, now_epoch=NOW)

        assert context["schema_version"] == "agent_context.v1"
        assert (ai_dir / "state/agent/context.json").exists()
        assert (ai_dir / "state/agent/status.md").exists()



def test_stale_active_nudge_is_not_blocking() -> None:
   with tempfile.TemporaryDirectory(prefix="ai-agent-context-stale-nudge-") as tmp:
       ai_dir = Path(tmp) / "AI"

       write_json(ai_dir / "outbox/to-phone/current-nudge.json", {
           "schema_version": "phone_interaction.v1",
           "kind": "nudge",
           "status": "active",
           "nudge_id": "n-stale",
           "created_at": "2026-05-05T19:00:00+02:00",
           "updated_at": "2026-05-05T21:10:00+02:00",
           "source": "llm-planner",
           "planner_mode": "help-now",
           "message": "old",
       })

       write_json(ai_dir / "outbox/to-phone/interaction-state.json", {
           "schema_version": "phone_interaction_state.v1",
           "updated_at": "2026-05-05T21:10:00+02:00",
           "source": "llm-planner",
           "planner_mode": "help-now",
           "active_nudge": {
               "nudge_id": "n-stale",
               "status": "active",
               "source": "llm-planner",
               "planner_mode": "help-now",
           },
           "active_question": None,
       })

       context = build_agent_context(ai_dir=ai_dir, now_epoch=1778008200)
       facts = context["derived_facts"]

       assert facts["has_active_nudge"] is False
       assert facts.get("active_nudge_clear_reason") == "expired_help-now_nudge"


def main() -> None:
    tests = [
        test_empty_context,
        test_active_state_facts,
        test_anki_totals_due_shape,
        test_recent_snooze_and_terminal_recovery,
        test_event_tails_are_bounded_and_sorted,
        test_legacy_anki_status_fallback,
        test_stale_active_nudge_is_not_blocking,
        test_write_agent_context,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")



if __name__ == "__main__":
    main()
