"""Shared intervention event helpers.

Intervention events are append-only audit records. They are for learning,
review, and future outcome analysis.

This module is pure: it builds JSON-safe event objects but does not read or
write the vault, create phone nudges, create action files, launch apps, call
LLMs, or mutate recovery state.
"""

from __future__ import annotations

from typing import Any


def _safe_text(value: Any, *, default: str = "", max_len: int = 500) -> str:
    text = str(value if value is not None else default).strip()
    text = " ".join(text.split())
    return text[:max_len]


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_string_list(value: Any, *, max_items: int = 24, max_len: int = 120) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value[:max_items]:
        text = _safe_text(item, max_len=max_len)
        if text:
            out.append(text)
    return out


def _slug(value: Any, *, fallback: str = "item") -> str:
    text = _safe_text(value, default=fallback, max_len=80).lower()
    out: list[str] = []
    dash = False

    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            out.append(char)
            dash = False
        elif not dash:
            out.append("-")
            dash = True

    return "".join(out).strip("-") or fallback


def intervention_id_for(kind: str, source: str, target_id: str, timestamp_epoch: int) -> str:
    return "i-{source}-{kind}-{target}-{epoch}".format(
        source=_slug(source, fallback="source"),
        kind=_slug(kind, fallback="intervention"),
        target=_slug(target_id, fallback="target"),
        epoch=max(0, _safe_int(timestamp_epoch)),
    )


def _date_from_iso(value: Any) -> str:
    text = _safe_text(value, max_len=80)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return ""


def _time_from_iso(value: Any) -> str:
    text = _safe_text(value, max_len=80)
    if "T" in text:
        return text.split("T", 1)[1][:8]
    return ""


def _base_event(decision: dict[str, Any], event_name: str, *, wrote_nudge: bool = False) -> dict[str, Any]:
    decision = _safe_dict(decision)
    intervention = _safe_dict(decision.get("intervention"))
    proposal = _safe_dict(decision.get("proposal"))
    validation = _safe_dict(decision.get("validation_result"))

    timestamp = _safe_text(decision.get("evaluated_at"), max_len=80)
    timestamp_epoch = _safe_int(decision.get("timestamp_epoch"))

    intervention_id = _safe_text(intervention.get("intervention_id"), max_len=120)
    if not intervention_id:
        intervention_id = intervention_id_for(
            "recovery_nudge",
            _safe_text(decision.get("source"), default="unknown", max_len=80),
            _safe_text(decision.get("target_id"), default="unknown", max_len=80),
            timestamp_epoch,
        )

    return {
        "schema_version": "event.v1",
        "event": event_name,
        "event_type": event_name,
        "source": "recovery-trigger",
        "device": "local",
        "timestamp": timestamp,
        "timestamp_epoch": timestamp_epoch,
        "date": _date_from_iso(timestamp),
        "time": _time_from_iso(timestamp),
        "processed_at": timestamp,
        "intervention_id": intervention_id,
        "intervention_kind": _safe_text(intervention.get("kind"), default="recovery_nudge", max_len=80),
        "target_id": _safe_text(decision.get("target_id"), max_len=80),
        "target_name": _safe_text(decision.get("target_name"), max_len=120),
        "nudge_id": _safe_text(proposal.get("nudge_id"), max_len=160),
        "decision": _safe_text(decision.get("decision"), max_len=80),
        "confidence": decision.get("confidence", 0),
        "reason_codes": _safe_string_list(decision.get("reason_codes")),
        "blocked_reasons": _safe_string_list(decision.get("blocked_reasons")),
        "gate_ok": bool(validation.get("ok")),
        "gate_status": _safe_text(validation.get("status"), max_len=80),
        "gate_reason": _safe_text(validation.get("reason"), max_len=160),
        "wrote_nudge": bool(wrote_nudge),
    }


def build_recovery_trigger_intervention_events(
    decision: dict[str, Any],
    *,
    wrote_nudge: bool = False,
) -> list[dict[str, Any]]:
    """Build append-only intervention audit events for recovery-trigger.

    The records intentionally store summaries, not executable phone actions.
    Executable details remain owned by proposal_gate.py and the trusted target
    registry.
    """

    decision = _safe_dict(decision)
    if not decision:
        return []

    proposal = _safe_dict(decision.get("proposal"))
    validation = _safe_dict(decision.get("validation_result"))

    proposed = _base_event(decision, "intervention_proposed", wrote_nudge=wrote_nudge)
    proposed["proposal_schema_version"] = _safe_text(proposal.get("schema_version"), max_len=80)
    proposed["proposal_message"] = _safe_text(proposal.get("message"), max_len=500)
    proposed["proposal_recommended_next_action"] = _safe_text(proposal.get("recommended_next_action"), max_len=500)
    proposed["proposal_allowed_actions"] = _safe_string_list(proposal.get("actions"))

    gated = _base_event(decision, "intervention_gated", wrote_nudge=wrote_nudge)
    gated["validation_schema_version"] = _safe_text(validation.get("schema_version"), max_len=80)
    gated["normalized_decision"] = _safe_text(_safe_dict(validation.get("normalized")).get("decision"), max_len=80)

    events = [proposed, gated]

    if wrote_nudge:
        written = _base_event(decision, "intervention_nudge_written", wrote_nudge=True)
        written["nudge_status"] = "active"
        events.append(written)

    return events
