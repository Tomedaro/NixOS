"""Pure active interaction lifecycle helpers.

This module intentionally has no filesystem or systemd side effects. Runtime
bridges/planners can use it to decide when an active phone interaction should
continue to block new work, when it should be cleared, and why.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

DEFAULT_NUDGE_TTL_SECONDS = 60 * 60

ACTION_CLEARING_NUDGE = frozenset(
    {
        "ack_nudge",
        "snooze_nudge",
        "start_recovery_target",
    }
)

RECOVERY_TERMINAL_STATUSES = frozenset(
    {
        "possible_success",
        "success",
        "completed",
        "failed",
        "expired",
        "aborted",
        "rapid_abort",
        "no_launch",
        "interrupted",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_timestamp_epoch(value: Any) -> int | None:
    """Return epoch seconds for int/float/ISO-8601 timestamp-like values."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        if stripped.isdigit():
            return int(stripped)

        normalized = stripped
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return int(parsed.timestamp())

    return None


def current_epoch(now: Any | None = None) -> int:
    """Return epoch seconds for now, accepting int/float/datetime/ISO strings."""

    if now is None:
        return int(datetime.now(timezone.utc).timestamp())

    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return int(now.timestamp())

    parsed = parse_timestamp_epoch(now)
    if parsed is None:
        raise ValueError(f"cannot parse now as timestamp: {now!r}")
    return parsed


def nudge_timestamp_epoch(nudge: dict[str, Any]) -> int | None:
    """Return the creation timestamp that should drive nudge expiry."""

    for key in ("created_at", "timestamp", "timestamp_epoch", "updated_at"):
        parsed = parse_timestamp_epoch(nudge.get(key))
        if parsed is not None:
            return parsed
    return None


def nudge_age_seconds(nudge: dict[str, Any], now: Any | None = None) -> int | None:
    created = nudge_timestamp_epoch(nudge)
    if created is None:
        return None
    return max(0, current_epoch(now) - created)


def is_active_nudge(nudge: Any) -> bool:
    nudge = _as_dict(nudge)
    return nudge.get("kind") == "nudge" and nudge.get("status") == "active"


def nudge_is_expired(
    nudge: dict[str, Any],
    now: Any | None = None,
    ttl_seconds: int = DEFAULT_NUDGE_TTL_SECONDS,
) -> bool:
    age = nudge_age_seconds(nudge, now)
    if age is None:
        return False
    return age >= ttl_seconds


def action_clears_active_nudge(action_event: Any) -> bool:
    event = _as_dict(action_event)
    action = event.get("action") or event.get("event") or event.get("event_type")
    return action in ACTION_CLEARING_NUDGE


def recovery_is_terminal(recovery_state: Any) -> bool:
    recovery = _as_dict(recovery_state)
    return recovery.get("status") in RECOVERY_TERMINAL_STATUSES


def _candidate_nudge_ids_from_recovery(recovery_state: dict[str, Any]) -> set[str]:
    ids: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and value:
            ids.add(value)

    add(recovery_state.get("nudge_id"))

    intervention = _as_dict(recovery_state.get("intervention"))
    add(intervention.get("nudge_id"))

    for key in ("last_event", "last_lifecycle_event"):
        event = _as_dict(recovery_state.get(key))
        add(event.get("nudge_id"))
        add(event.get("interaction_id"))

    return ids


def nudge_matches_recovery(nudge: Any, recovery_state: Any) -> bool:
    nudge = _as_dict(nudge)
    recovery = _as_dict(recovery_state)

    nudge_id = nudge.get("nudge_id")
    if isinstance(nudge_id, str) and nudge_id:
        if nudge_id in _candidate_nudge_ids_from_recovery(recovery):
            return True

    nudge_target = nudge.get("target_id")
    recovery_target = _as_dict(recovery.get("target")).get("target_id")
    if not recovery_target:
        recovery_target = _as_dict(recovery.get("lifecycle")).get("target_id")

    if nudge_target and recovery_target and nudge_target == recovery_target:
        return True

    if nudge.get("planner_mode") == "recovery":
        return True

    return False


def clear_reason_for_active_nudge(
    interaction_state: Any,
    *,
    recovery_state: Any | None = None,
    action_event: Any | None = None,
    now: Any | None = None,
    ttl_seconds: int = DEFAULT_NUDGE_TTL_SECONDS,
) -> str | None:
    state = _as_dict(interaction_state)
    nudge = _as_dict(state.get("active_nudge"))

    if not is_active_nudge(nudge):
        return None

    if action_event is not None and action_clears_active_nudge(action_event):
        action = _as_dict(action_event).get("action") or _as_dict(action_event).get("event")
        return f"user_action_{action}"

    if recovery_state is not None:
        recovery = _as_dict(recovery_state)
        if recovery_is_terminal(recovery) and nudge_matches_recovery(nudge, recovery):
            return f"recovery_{recovery.get('status')}"

    if nudge_is_expired(nudge, now, ttl_seconds):
        planner_mode = nudge.get("planner_mode") or "unknown"
        return f"expired_{planner_mode}_nudge"

    return None


def prune_interaction_state(
    interaction_state: dict[str, Any],
    *,
    recovery_state: Any | None = None,
    action_event: Any | None = None,
    now: Any | None = None,
    ttl_seconds: int = DEFAULT_NUDGE_TTL_SECONDS,
) -> tuple[dict[str, Any], str | None]:
    """Return a copied state and a clear reason if active_nudge should clear."""

    next_state = deepcopy(interaction_state)
    reason = clear_reason_for_active_nudge(
        next_state,
        recovery_state=recovery_state,
        action_event=action_event,
        now=now,
        ttl_seconds=ttl_seconds,
    )

    if reason is None:
        return next_state, None

    next_state["active_nudge"] = None
    next_state["last_cleared_nudge"] = {
        "reason": reason,
        "cleared_at_epoch": current_epoch(now),
    }
    return next_state, reason
