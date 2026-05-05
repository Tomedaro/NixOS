"""Pure recovery proposal builders.

This module contains side-effect-free proposal construction shared by
deterministic producers and future LLM/agent proposal producers.

Authority boundary:

    agent_context.py reads facts
    recovery_proposals.py builds candidate proposals
    proposal_gate.py validates and normalizes
    action-bridge executes only validated/user-triggered actions

This module must not read or write the vault, write phone nudges, create
action files, launch apps, call an LLM, or mutate recovery state.
"""

from __future__ import annotations

from typing import Any

from ai_system.recovery_targets import get_recovery_target


GOOD_DESKTOP_VERDICTS = {"idle", "no_plan", "off_task", "distracted", "unknown"}


def safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(float(value if value is not None else default)))
    except Exception:
        return default


def safe_text(value: Any, *, default: str = "", max_len: int = 500) -> str:
    text = str(value if value is not None else default).strip()
    text = " ".join(text.split())
    return text[:max_len]


def safe_facts(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_recovery_reasoning(facts: dict[str, Any] | None, *, target_id: str = "anki") -> dict[str, Any]:
    """Build deterministic reason/blocker codes from derived facts."""

    facts = safe_facts(facts)
    target = get_recovery_target(target_id)

    due = safe_int(facts.get("anki_due"), default=0)
    verdict = safe_text(facts.get("desktop_verdict"), default="unknown", max_len=80).lower() or "unknown"

    blocked: list[str] = []
    reason_codes: list[str] = []

    if bool(facts.get("has_active_session")):
        blocked.append("active_session")
    else:
        reason_codes.append("no_active_session")

    if bool(facts.get("has_active_nudge")):
        blocked.append("active_nudge")
    else:
        reason_codes.append("no_active_nudge")

    if bool(facts.get("has_active_question")):
        blocked.append("active_question")
    else:
        reason_codes.append("no_active_question")

    if bool(facts.get("has_active_recovery")):
        blocked.append("active_recovery")
    else:
        reason_codes.append("no_active_recovery")

    if bool(facts.get("recent_terminal_recovery")):
        blocked.append("recent_terminal_recovery")
    else:
        reason_codes.append("no_recent_terminal_recovery")

    if bool(facts.get("recent_snooze")):
        blocked.append("recent_snooze")
    else:
        reason_codes.append("no_recent_snooze")

    if target["target_id"] == "anki":
        if due > 0:
            reason_codes.append("anki_due")
        else:
            blocked.append("anki_not_due")

    if verdict in GOOD_DESKTOP_VERDICTS:
        reason_codes.append(f"desktop_{verdict}")
    else:
        blocked.append(f"desktop_verdict_{verdict}")

    return {
        "schema_version": "recovery_reasoning.v1",
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "reason_codes": reason_codes,
        "blocked_reasons": blocked,
        "facts": facts,
    }


def build_deterministic_recovery_proposal(
    facts: dict[str, Any] | None,
    *,
    target_id: str = "anki",
    source: str = "deterministic-v0",
    cooldown_seconds: int = 1800,
) -> dict[str, Any]:
    """Build the deterministic recovery proposal shape consumed by the gate."""

    facts = safe_facts(facts)
    target = get_recovery_target(target_id)
    reasoning = build_recovery_reasoning(facts, target_id=target["target_id"])

    return {
        "schema_version": "agent_recovery_proposal.v1",
        "source": safe_text(source, default="deterministic-v0", max_len=80),
        "decision": "write_nudge",
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "confidence": 0.72,
        "reason_codes": reasoning["reason_codes"],
        "blocked_reasons": reasoning["blocked_reasons"],
        "message": target["nudge_message"],
        "recommended_next_action": target["recommended_next_action"],
        "allowed_actions": [
            "start_recovery_target",
            "snooze_nudge",
        ],
        "cooldown_seconds": safe_int(cooldown_seconds, default=1800),
    }
