"""Shared recovery target registry.

This module keeps target metadata in one place so action handling,
recovery lifecycle classification, and recovery nudge generation do not
drift apart.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RECOVERY_TARGETS: dict[str, dict[str, Any]] = {
    "anki": {
        "target_id": "anki",
        "display_name": "Anki",
        "kind": "app",
        "android_package": "com.ichi2.anki",
        "default_goal": "5 minutes in AnkiDroid",
        "default_stop_condition": "Stay in AnkiDroid for 5 minutes, then stop.",
        "launch_task": "AI PI Launch AnkiDroid",
        "phone_open_events": ["opened_ankidroid"],
        "phone_close_events": ["closed_ankidroid"],
        "nudge_message": "Anki recovery: start a tiny 5-minute block.",
        "recommended_next_action": "Tap Start Anki. Stay in AnkiDroid for 5 minutes, then stop.",
    }
}


def get_recovery_target(target_id: str | None) -> dict[str, Any]:
    key = str(target_id or "anki").strip().lower() or "anki"

    if key in RECOVERY_TARGETS:
        return deepcopy(RECOVERY_TARGETS[key])

    return {
        "target_id": key,
        "display_name": str(target_id or "Recovery target"),
        "kind": "unknown",
        "android_package": "",
        "default_goal": "5 minutes",
        "default_stop_condition": "Stop after 5 minutes.",
        "launch_task": "",
        "phone_open_events": [],
        "phone_close_events": [],
        "nudge_message": "Recovery: start a tiny 5-minute block.",
        "recommended_next_action": "Start the target and stay with it for 5 minutes.",
    }


def recovery_target_action(target_id: str | None = "anki") -> dict[str, Any]:
    target = get_recovery_target(target_id)

    action = {
        "action": "start_recovery_target",
        "label": f"Start {target['display_name']}",
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "goal_text": target["default_goal"],
        "stop_condition": target["default_stop_condition"],
    }

    if target.get("android_package"):
        action["android_package"] = target["android_package"]

    if target.get("launch_task"):
        action["launch_task"] = target["launch_task"]

    return action
