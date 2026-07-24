"""Neutral module for private types and constants shared by store and kernel.

Owns: error classes, InteractionPolicy, policy serialization helpers,
private key-set constants, canonical encoding helpers, and the
ValidatedBundle type.

Imports only from contracts.  Store and kernel import through this module
(via re-exports from store), not directly.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, NamedTuple

from ai_system import task_initiation_contracts as c

# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class KernelNotFoundError(Exception):
    """Requested resource (interaction, Card, etc.) is absent."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class KernelRefusalError(Exception):
    """Deterministic non-persisted refusal (expired, conflict, invalid)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class KernelCorruptionError(Exception):
    """Persistence is malformed, incompatible, or cross-row inconsistent."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class KernelBusyError(Exception):
    """Database locked after the configured timeout."""

    pass


class KernelStorageError(Exception):
    """Permission, I/O, or commit failure."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


# ---------------------------------------------------------------------------
# Canonical encoding helpers
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _canonical_json(data: Mapping[str, Any]) -> bytes:
    return c._canonical_json(data)


def _payload_sha256(data: Mapping[str, Any]) -> str:
    return c._payload_sha256(data)


def _strict_json_loads(raw: str | bytes) -> Any:
    return c._strict_json_loads(raw)


# ---------------------------------------------------------------------------
# Private key set constants
# ---------------------------------------------------------------------------


_AGGREGATE_KEYS_V1 = frozenset({
    "interaction_id", "event_id", "phase", "terminal_status",
    "resolution_reason", "resolved_task", "task_fingerprint",
    "current_revision", "revisions", "accepted_responses",
    "request_occurred_at_epoch", "request_received_at_epoch",
    "request_expires_at_epoch", "has_published_card",
    "actionable_surface_proven_by_epoch",
    "first_response_at_epoch", "first_response_received_at_epoch",
    "start_at_epoch", "start_received_at_epoch",
    "observation_due_at_epoch", "terminal_at_epoch",
    "evidence_issues", "state_version", "latest_error",
    "message_reservations",
})

_REVISION_KEYS_V1 = frozenset({
    "revision", "context_id", "card_id", "proposal_sha256",
    "response_payload_sha256", "card_issued_at_epoch", "card_expires_at_epoch",
    "context", "proposal", "card", "response",
    "card_posted_at_epoch", "delivery_evidence", "delivery_occurred_at_epoch",
    "evidence_issues", "receipt", "receipt_payload_sha256", "task_fingerprint",
})

_RESPONSE_PRIVATE_KEYS_V1 = frozenset({
    "response_id", "card_id", "action", "detail", "occurred_at_epoch",
    "received_at_epoch", "schema_version", "occurred_at_epoch_usable",
})

_ACCEPTED_RESPONSE_KEYS_V1 = frozenset({
    "response_id", "card_id", "revision", "user_action", "detail",
})

_RESOLVED_TASK_VARIANTS = {
    "explicit_task_ref": frozenset({"source", "label", "task_ref", "source_revision"}),
    "active_session": frozenset({"source", "label", "session_id"}),
    "fallback_description": frozenset({"source", "label"}),
}

_VALID_RESOLUTION_REASONS = frozenset({
    "deferred", "dismissed", "shrink_limit_reached", "blocked_unresolved",
    "task_changed", "card_expired_without_response", "delivery_ambiguous",
    "card_not_posted_before_expiry", "observation_completed",
    "start_observation_elapsed", "request_expired",
})

# ---------------------------------------------------------------------------
# InteractionPolicy
# ---------------------------------------------------------------------------


class InteractionPolicy:
    """Immutable per-interaction lifecycle policy snapshot.

    Created from KernelPolicy at Stuck acceptance and persisted atomically
    with the interaction.  Governs all subsequent lifecycle decisions for
    that interaction regardless of later runtime policy changes.
    """

    def __init__(
        self,
        *,
        policy_version: str = "task_initiation_interaction_policy.v1",
        stuck_ttl_seconds: int = 7200,
        max_future_skew_seconds: int = 300,
        max_card_revisions: int = 3,
        tiny_start_minutes_cap: int = 10,
        start_countdown_seconds_cap: int = 600,
        observation_seconds: int = 600,
        context_ttl_seconds: int = 300,
        card_ttl_seconds: int = 900,
    ) -> None:
        if policy_version != "task_initiation_interaction_policy.v1":
            raise ValueError(f"unsupported interaction policy version: {policy_version}")
        for name, value, min_val in [
            ("stuck_ttl_seconds", stuck_ttl_seconds, 1),
            ("max_future_skew_seconds", max_future_skew_seconds, 0),
            ("max_card_revisions", max_card_revisions, 1),
            ("tiny_start_minutes_cap", tiny_start_minutes_cap, 1),
            ("start_countdown_seconds_cap", start_countdown_seconds_cap, 1),
            ("observation_seconds", observation_seconds, 1),
            ("context_ttl_seconds", context_ttl_seconds, 1),
            ("card_ttl_seconds", card_ttl_seconds, 1),
        ]:
            if isinstance(value, bool) or not isinstance(value, int) or value < min_val:
                raise ValueError(f"InteractionPolicy.{name} must be int >= {min_val}, got {value!r}")
        self.policy_version = policy_version
        self.stuck_ttl_seconds = stuck_ttl_seconds
        self.max_future_skew_seconds = max_future_skew_seconds
        self.max_card_revisions = max_card_revisions
        self.tiny_start_minutes_cap = tiny_start_minutes_cap
        self.start_countdown_seconds_cap = start_countdown_seconds_cap
        self.observation_seconds = observation_seconds
        self.context_ttl_seconds = context_ttl_seconds
        self.card_ttl_seconds = card_ttl_seconds

    def to_canonical_json(self) -> str:
        return json.dumps({
            "policy_version": self.policy_version,
            "stuck_ttl_seconds": self.stuck_ttl_seconds,
            "max_future_skew_seconds": self.max_future_skew_seconds,
            "max_card_revisions": self.max_card_revisions,
            "tiny_start_minutes_cap": self.tiny_start_minutes_cap,
            "start_countdown_seconds_cap": self.start_countdown_seconds_cap,
            "observation_seconds": self.observation_seconds,
            "context_ttl_seconds": self.context_ttl_seconds,
            "card_ttl_seconds": self.card_ttl_seconds,
        }, sort_keys=True, separators=(",", ":"))

    def reducer_policy(self) -> dict[str, int]:
        return {
            "max_card_revisions": self.max_card_revisions,
            "start_countdown_seconds_cap": self.start_countdown_seconds_cap,
            "observation_seconds": self.observation_seconds,
            "context_ttl_seconds": self.context_ttl_seconds,
            "card_ttl_seconds": self.card_ttl_seconds,
            "stuck_ttl_seconds": self.stuck_ttl_seconds,
            "max_future_skew_seconds": self.max_future_skew_seconds,
            "tiny_start_minutes_cap": self.tiny_start_minutes_cap,
        }


# ---------------------------------------------------------------------------
# Policy serialization helpers
# ---------------------------------------------------------------------------


def _interaction_policy_to_json(
    *,
    stuck_ttl_seconds: int,
    max_future_skew_seconds: int,
    max_card_revisions: int,
    tiny_start_minutes_cap: int,
    start_countdown_seconds_cap: int,
    observation_seconds: int,
    context_ttl_seconds: int,
    card_ttl_seconds: int,
) -> str:
    """Produce canonical JSON snapshot of lifecycle policy fields via InteractionPolicy."""
    ip = InteractionPolicy(
        stuck_ttl_seconds=stuck_ttl_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
        max_card_revisions=max_card_revisions,
        tiny_start_minutes_cap=tiny_start_minutes_cap,
        start_countdown_seconds_cap=start_countdown_seconds_cap,
        observation_seconds=observation_seconds,
        context_ttl_seconds=context_ttl_seconds,
        card_ttl_seconds=card_ttl_seconds,
    )
    return ip.to_canonical_json()


def _interaction_policy_from_json(raw: str) -> InteractionPolicy:
    """Decode and validate a persisted interaction policy snapshot.

    Returns a typed InteractionPolicy.  Raises KernelCorruptionError on
    malformed JSON, wrong version, missing/extra keys, or invalid values.
    """
    try:
        data = _strict_json_loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise KernelCorruptionError(f"interaction policy: invalid JSON: {exc}")
    if not isinstance(data, dict):
        raise KernelCorruptionError("interaction policy: not a JSON object")
    if data.get("policy_version") != "task_initiation_interaction_policy.v1":
        raise KernelCorruptionError("interaction policy: unsupported version")
    expected_keys = frozenset({
        "policy_version", "stuck_ttl_seconds", "max_future_skew_seconds",
        "max_card_revisions", "tiny_start_minutes_cap",
        "start_countdown_seconds_cap", "observation_seconds",
        "context_ttl_seconds", "card_ttl_seconds",
    })
    if set(data.keys()) != expected_keys:
        raise KernelCorruptionError("interaction policy: key mismatch")
    for key in data:
        if key == "policy_version":
            continue
        if isinstance(data[key], bool) or not isinstance(data[key], int):
            raise KernelCorruptionError(f"interaction policy.{key}: must be int, got {type(data[key]).__name__}")
    for key, min_val in [
        ("stuck_ttl_seconds", 1), ("max_future_skew_seconds", 0),
        ("max_card_revisions", 1), ("tiny_start_minutes_cap", 1),
        ("start_countdown_seconds_cap", 1), ("observation_seconds", 1),
        ("context_ttl_seconds", 1), ("card_ttl_seconds", 1),
    ]:
        if data[key] < min_val:
            raise KernelCorruptionError(f"interaction policy.{key}: must be >= {min_val}, got {data[key]}")
    result = InteractionPolicy(
        stuck_ttl_seconds=data["stuck_ttl_seconds"],
        max_future_skew_seconds=data["max_future_skew_seconds"],
        max_card_revisions=data["max_card_revisions"],
        tiny_start_minutes_cap=data["tiny_start_minutes_cap"],
        start_countdown_seconds_cap=data["start_countdown_seconds_cap"],
        observation_seconds=data["observation_seconds"],
        context_ttl_seconds=data["context_ttl_seconds"],
        card_ttl_seconds=data["card_ttl_seconds"],
    )
    # Require canonical encoding round-trip
    if raw != result.to_canonical_json():
        raise KernelCorruptionError("interaction policy: not canonical")
    return result


# ---------------------------------------------------------------------------
# ValidatedBundle
# ---------------------------------------------------------------------------


class ValidatedBundle(NamedTuple):
    """A fully loaded and validated interaction bundle.

    Contains the interaction SQL row, the decoded aggregate dict,
    and an optional validated message payload (for replay surfaces).
    """
    int_row: Any  # sqlite3.Row
    aggregate: dict[str, Any]
    validated_payload: dict[str, Any] | None = None
    validated_result: dict[str, Any] | None = None
