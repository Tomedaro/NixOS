"""Pure intervention outcome summarizers.

This module groups append-only intervention/action/recovery events by
intervention_id and classifies conservative outcomes for review and future
learning.

Authority boundary:

    events are evidence
    this module summarizes evidence
    this module does not execute, propose, write files, call LLMs, launch apps,
    mutate recovery state, or change policy
"""

from __future__ import annotations

from typing import Any


TERMINAL_RECOVERY_OUTCOMES = {
    "recovery_possible_success": "possible_success",
    "recovery_possible_abort": "possible_abort",
    "recovery_expired": "expired",
    "recovery_cancelled": "cancelled",
    "recovery_completed": "completed",
}

START_EVENTS = {"recovery_started", "start_recovery_target", "start_recovery", "recovery_start"}
SNOOZE_EVENTS = {"snooze_nudge", "nudge_snoozed", "defer_nudge"}
ACK_EVENTS = {"ack_nudge", "nudge_acknowledged"}


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


def _safe_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    text = _safe_text(value, max_len=20).lower()
    if text in {"1", "true", "yes", "ok", "accepted"}:
        return True
    if text in {"0", "false", "no", "rejected", "blocked"}:
        return False
    return None


def _event_name(event: dict[str, Any]) -> str:
    event = _safe_dict(event)
    return _safe_text(
        event.get("event") or event.get("event_type") or event.get("action"),
        max_len=120,
    )


def _event_epoch(event: dict[str, Any]) -> int:
    event = _safe_dict(event)
    return _safe_int(event.get("timestamp_epoch") or event.get("processed_epoch"))


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [_safe_dict(event) for event in events if isinstance(event, dict)],
        key=lambda event: (_event_epoch(event), _event_name(event)),
    )


def _events_for_id(events: list[dict[str, Any]] | None, intervention_id: str) -> list[dict[str, Any]]:
    if not intervention_id:
        return []

    out = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if _safe_text(event.get("intervention_id"), max_len=160) == intervention_id:
            out.append(event)

    return _sorted_events(out)


def _last_event_named(events: list[dict[str, Any]], names: set[str]) -> dict[str, Any]:
    for event in reversed(_sorted_events(events)):
        if _event_name(event) in names:
            return event
    return {}


def _first_text(events: list[dict[str, Any]], *keys: str) -> str:
    for event in _sorted_events(events):
        for key in keys:
            text = _safe_text(event.get(key), max_len=500)
            if text:
                return text
    return ""


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    event = _safe_dict(event)
    if not event:
        return {}

    return {
        "event": _event_name(event),
        "timestamp_epoch": _event_epoch(event),
        "timestamp": _safe_text(event.get("timestamp"), max_len=80),
        "processed_at": _safe_text(event.get("processed_at"), max_len=80),
        "source": _safe_text(event.get("source"), max_len=80),
        "device": _safe_text(event.get("device"), max_len=80),
        "reason": _safe_text(event.get("reason"), max_len=160),
        "status": _safe_text(event.get("status"), max_len=80),
    }


def summarize_intervention(
    intervention_id: str,
    intervention_events: list[dict[str, Any]] | None = None,
    action_events: list[dict[str, Any]] | None = None,
    recovery_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize one intervention by id.

    Outcomes are conservative and evidence-based. They are not policy changes.
    """

    intervention_id = _safe_text(intervention_id, max_len=160)
    intervention_events = _events_for_id(intervention_events, intervention_id)
    action_events = _events_for_id(action_events, intervention_id)
    recovery_events = _events_for_id(recovery_events, intervention_id)

    all_events = _sorted_events(intervention_events + action_events + recovery_events)
    if not intervention_id:
        return {
            "schema_version": "intervention_outcome.v1",
            "intervention_id": "",
            "outcome": "unknown",
            "reason": "missing_intervention_id",
            "event_count": 0,
        }

    proposed = _last_event_named(intervention_events, {"intervention_proposed"})
    gated = _last_event_named(intervention_events, {"intervention_gated"})
    written = _last_event_named(intervention_events, {"intervention_nudge_written"})

    gate_ok = _safe_bool_or_none(gated.get("gate_ok")) if gated else None
    nudge_written = bool(written) or any(bool(event.get("wrote_nudge")) for event in intervention_events)

    terminal_recovery_event = _last_event_named(recovery_events, set(TERMINAL_RECOVERY_OUTCOMES))
    started_event = _last_event_named(action_events + recovery_events, START_EVENTS)
    snooze_event = _last_event_named(action_events, SNOOZE_EVENTS)
    ack_event = _last_event_named(action_events, ACK_EVENTS)

    outcome_event: dict[str, Any] = {}
    reason = ""

    if terminal_recovery_event:
        outcome = TERMINAL_RECOVERY_OUTCOMES[_event_name(terminal_recovery_event)]
        outcome_event = terminal_recovery_event
        reason = f"recovery_manager_classified_{outcome}"
    elif started_event:
        outcome = "started"
        outcome_event = started_event
        reason = "user_started_recovery"
    elif snooze_event:
        outcome = "snoozed"
        outcome_event = snooze_event
        reason = "user_snoozed_nudge"
    elif ack_event:
        outcome = "acknowledged"
        outcome_event = ack_event
        reason = "user_acknowledged_nudge"
    elif nudge_written:
        outcome = "shown_no_response"
        outcome_event = written
        reason = "nudge_written_no_user_response_yet"
    elif gated and gate_ok is False:
        outcome = "not_shown"
        outcome_event = gated
        reason = "proposal_rejected_by_gate"
    elif proposed:
        outcome = "not_shown"
        outcome_event = proposed
        reason = "proposal_did_not_write_nudge"
    else:
        outcome = "unknown"
        reason = "no_matching_evidence"

    first_epoch = _event_epoch(all_events[0]) if all_events else 0
    last_epoch = _event_epoch(all_events[-1]) if all_events else 0

    return {
        "schema_version": "intervention_outcome.v1",
        "intervention_id": intervention_id,
        "intervention_kind": _first_text(all_events, "intervention_kind", "kind"),
        "target_id": _first_text(all_events, "target_id"),
        "target_name": _first_text(all_events, "target_name"),
        "nudge_id": _first_text(all_events, "nudge_id"),
        "outcome": outcome,
        "reason": reason,
        "gate_ok": gate_ok,
        "nudge_written": nudge_written,
        "user_acted": bool(ack_event or snooze_event or started_event),
        "recovery_started": bool(started_event),
        "terminal_recovery": bool(terminal_recovery_event),
        "first_event_epoch": first_epoch,
        "last_event_epoch": last_epoch,
        "event_count": len(all_events),
        "event_counts": {
            "interventions": len(intervention_events),
            "actions": len(action_events),
            "recovery": len(recovery_events),
        },
        "evidence": {
            "proposed": _compact_event(proposed),
            "gated": _compact_event(gated),
            "nudge_written": _compact_event(written),
            "ack": _compact_event(ack_event),
            "snooze": _compact_event(snooze_event),
            "started": _compact_event(started_event),
            "terminal_recovery": _compact_event(terminal_recovery_event),
            "outcome_event": _compact_event(outcome_event),
        },
    }


def summarize_interventions(
    intervention_events: list[dict[str, Any]] | None = None,
    action_events: list[dict[str, Any]] | None = None,
    recovery_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ids: set[str] = set()

    for collection in [intervention_events or [], action_events or [], recovery_events or []]:
        for event in collection:
            if not isinstance(event, dict):
                continue
            intervention_id = _safe_text(event.get("intervention_id"), max_len=160)
            if intervention_id:
                ids.add(intervention_id)

    summaries = [
        summarize_intervention(
            intervention_id,
            intervention_events=intervention_events,
            action_events=action_events,
            recovery_events=recovery_events,
        )
        for intervention_id in sorted(ids)
    ]

    summaries.sort(key=lambda item: (item.get("last_event_epoch", 0), item.get("intervention_id", "")))
    return summaries


def build_outcome_stats(summaries: list[dict[str, Any]] | None) -> dict[str, Any]:
    summaries = [_safe_dict(item) for item in summaries or [] if isinstance(item, dict)]

    by_outcome: dict[str, int] = {}
    for summary in summaries:
        outcome = _safe_text(summary.get("outcome"), default="unknown", max_len=80)
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

    shown_count = sum(1 for item in summaries if bool(item.get("nudge_written")))
    acted_count = sum(1 for item in summaries if bool(item.get("user_acted")))
    started_count = sum(1 for item in summaries if bool(item.get("recovery_started")))
    terminal_count = sum(1 for item in summaries if bool(item.get("terminal_recovery")))
    success_count = by_outcome.get("possible_success", 0) + by_outcome.get("completed", 0)

    return {
        "schema_version": "intervention_outcome_stats.v1",
        "total": len(summaries),
        "by_outcome": by_outcome,
        "shown_count": shown_count,
        "acted_count": acted_count,
        "started_count": started_count,
        "terminal_count": terminal_count,
        "success_count": success_count,
        "action_rate": acted_count / shown_count if shown_count else 0.0,
        "start_rate": started_count / shown_count if shown_count else 0.0,
        "terminal_success_rate": success_count / terminal_count if terminal_count else 0.0,
    }
