"""Deterministic validation gate for future AI/LLM proposals.

This module is intentionally pure: it does not read or write the vault.
Callers pass a proposal and already-collected facts/context. The gate
returns a JSON-safe validation result and a normalized proposal when safe.
"""

from __future__ import annotations

from typing import Any

from ai_system.recovery_targets import RECOVERY_TARGETS, get_recovery_target, recovery_target_action


ALLOWED_DECISIONS = {"skip", "write_nudge"}
ALLOWED_RECOVERY_ACTIONS = {"start_recovery_target", "snooze_nudge"}
BLOCKING_FACTS = {
    "has_active_session": "active_session",
    "has_active_nudge": "active_nudge",
    "has_active_question": "active_question",
    "has_active_recovery": "active_recovery",
    "recent_snooze": "recent_snooze",
    "recent_terminal_recovery": "recent_terminal_recovery",
}
DIRECT_EXECUTION_FIELDS = {
    "action",
    "command",
    "android_package",
    "launch_task",
    "raw_action",
    "action_file",
    "path",
}


def _safe_text(value: Any, *, default: str = "", max_len: int = 500) -> str:
    text = str(value if value is not None else default).strip()
    text = " ".join(text.split())
    return text[:max_len]


def _safe_string_list(value: Any, *, max_items: int = 12, max_len: int = 80) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value[:max_items]:
        text = _safe_text(item, max_len=max_len)
        if text:
            out.append(text)
    return out


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = default

    if number < 0:
        return 0.0

    if number > 1:
        return 1.0

    return number


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _bool_fact(facts: dict[str, Any], key: str) -> bool:
    return bool(facts.get(key))


def _reject(reason: str, *, proposal: dict[str, Any] | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "proposal_validation_result.v1",
        "ok": False,
        "status": "rejected",
        "reason": reason,
        "details": details or {},
        "normalized": None,
    }


def _accept(normalized: dict[str, Any], *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "proposal_validation_result.v1",
        "ok": True,
        "status": "accepted",
        "reason": "validated",
        "details": details or {},
        "normalized": normalized,
    }


def _proposal_has_direct_execution_fields(proposal: dict[str, Any]) -> list[str]:
    present = []

    for field in DIRECT_EXECUTION_FIELDS:
        if field in proposal:
            present.append(field)

    return sorted(present)


def _proposal_allowed_actions(proposal: dict[str, Any]) -> list[str]:
    raw = proposal.get("allowed_actions")
    if raw is None:
        raw = proposal.get("actions")

    if raw is None:
        return []

    if not isinstance(raw, list):
        return ["invalid_actions_shape"]

    actions = []
    for item in raw:
        if isinstance(item, str):
            actions.append(item.strip())
        elif isinstance(item, dict):
            actions.append(str(item.get("action") or "").strip())
        else:
            actions.append("invalid_action_item")

    return [item for item in actions if item]


def _facts_blockers(facts: dict[str, Any], target_id: str) -> list[str]:
    blockers = []

    for fact_key, blocker in BLOCKING_FACTS.items():
        if _bool_fact(facts, fact_key):
            blockers.append(blocker)

    if target_id == "anki":
        anki_due = _safe_int(facts.get("anki_due"), default=0)
        if anki_due <= 0:
            blockers.append("anki_not_due")

    return blockers


def validate_recovery_proposal(proposal: dict[str, Any], facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and normalize a recovery proposal.

    The gate is conservative:
    - only known recovery targets are allowed;
    - direct execution fields are rejected;
    - write_nudge is blocked by active state/cooldown facts;
    - executable phone actions are regenerated from the shared target registry.
    """

    if not isinstance(proposal, dict):
        return _reject("proposal_not_object")

    facts = facts if isinstance(facts, dict) else {}

    direct_fields = _proposal_has_direct_execution_fields(proposal)
    if direct_fields:
        return _reject(
            "proposal_contains_direct_execution_fields",
            details={"fields": direct_fields},
        )

    decision = _safe_text(proposal.get("decision"), default="skip", max_len=40)
    if decision not in ALLOWED_DECISIONS:
        return _reject(
            "unsupported_decision",
            details={"decision": decision, "allowed": sorted(ALLOWED_DECISIONS)},
        )

    target_id = _safe_text(proposal.get("target_id"), default="anki", max_len=80).lower() or "anki"
    if target_id not in RECOVERY_TARGETS:
        return _reject("unknown_recovery_target", details={"target_id": target_id})

    target = get_recovery_target(target_id)
    confidence = _safe_float(proposal.get("confidence"), default=0.0)
    reason_codes = _safe_string_list(proposal.get("reason_codes"))
    proposal_blocked = _safe_string_list(proposal.get("blocked_reasons"))

    allowed_actions = _proposal_allowed_actions(proposal)
    if allowed_actions:
        unsupported = sorted({action for action in allowed_actions if action not in ALLOWED_RECOVERY_ACTIONS})
        if unsupported:
            return _reject(
                "proposal_contains_unsupported_actions",
                details={"unsupported_actions": unsupported},
            )

    if decision == "skip":
        normalized = {
            "schema_version": "validated_recovery_proposal.v1",
            "decision": "skip",
            "target_id": target["target_id"],
            "target_name": target["display_name"],
            "confidence": confidence,
            "reason_codes": reason_codes,
            "blocked_reasons": proposal_blocked,
            "message": _safe_text(proposal.get("message"), default="", max_len=500),
        }
        return _accept(normalized)

    fact_blockers = _facts_blockers(facts, target_id)
    blocked_reasons = sorted(set(proposal_blocked + fact_blockers))

    if blocked_reasons:
        return _reject(
            "write_nudge_blocked",
            details={
                "blocked_reasons": blocked_reasons,
                "proposal_blocked_reasons": proposal_blocked,
                "fact_blockers": fact_blockers,
            },
        )

    message = _safe_text(
        proposal.get("message"),
        default=target["nudge_message"],
        max_len=500,
    ) or target["nudge_message"]

    recommended_next_action = _safe_text(
        proposal.get("recommended_next_action"),
        default=target["recommended_next_action"],
        max_len=500,
    ) or target["recommended_next_action"]

    normalized = {
        "schema_version": "validated_recovery_proposal.v1",
        "decision": "write_nudge",
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "confidence": confidence,
        "reason_codes": reason_codes,
        "blocked_reasons": [],
        "cooldown_seconds": max(0, _safe_int(proposal.get("cooldown_seconds"), default=1800)),
        "message": message,
        "recommended_next_action": recommended_next_action,
        "phone_nudge": {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "active",
            "source": "proposal-gate",
            "planner_mode": "recovery",
            "urgency": _safe_text(proposal.get("urgency"), default="normal", max_len=40) or "normal",
            "message": message,
            "recommended_next_action": recommended_next_action,
            "actions": [
                recovery_target_action(target_id),
                {
                    "action": "snooze_nudge",
                    "label": "Not now",
                    "snooze_minutes": 15,
                },
            ],
        },
    }

    return _accept(normalized)
