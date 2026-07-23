"""Pure contract candidates for the task-initiation first loop.

This module defines exactly five stable boundary validators, one provisional
Receipt validator (absent from the frozen set), and a private pure aggregate
reducer. No I/O, service, database, transport, or kernel runtime lives here.

The public validators enforce wire/model structure. Trial limits such as clock
skew, countdown duration, proposal duration, context collection bounds, request
TTL, and revision ceilings are enforced by private policy gates/reducer helpers
and remain overrideable runtime policy rather than schema identity.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Literal, Mapping

from ai_system.obsidian_contracts import (
    DIRECT_EXECUTION_FIELDS,
    contains_direct_execution,
)

# ---------------------------------------------------------------------------
# Private trial-policy defaults (not schema identity)
# ---------------------------------------------------------------------------

_STUCK_TTL_SECONDS = 7200
_MAX_FUTURE_CLOCK_SKEW_SECONDS = 300
_MAX_CARD_REVISIONS = 3
_START_COUNTDOWN_SECONDS_CAP = 600
_TINY_START_MINUTES_CAP = 10
_OBSERVATION_SECONDS = 600

_DEFAULT_CONTEXT_POLICY: dict[str, int] = {
    "max_recent_interactions": 8,
    "max_helper_material": 8,
    "max_provenance": 16,
    "max_omissions": 16,
    "max_helper_excerpt_chars": 1000,
}

# ---------------------------------------------------------------------------
# Enums / constant sets (public)
# ---------------------------------------------------------------------------

TASK_REF_SOURCES: frozenset[str] = frozenset({"tasknotes"})

RESPONSE_ACTIONS: frozenset[str] = frozenset(
    {"start", "shrink", "blocked", "defer", "dismiss"}
)

BLOCKER_CATEGORIES: frozenset[str] = frozenset({
    "too_big",
    "unclear_next_step",
    "waiting_for",
    "low_energy",
    "distracted",
    "perfectionism",
    "other",
})

TINY_START_KINDS: frozenset[str] = frozenset({"physical", "digital"})

CARD_BUTTONS: tuple[dict[str, str], ...] = (
    {"id": "start", "label": "Start"},
    {"id": "shrink", "label": "Shrink"},
    {"id": "blocked", "label": "Blocked"},
    {"id": "defer", "label": "Defer"},
)

CONTEXT_POLICY_VERSION = "task_initiation_context_allowlist.v1"

PROVENANCE_CATEGORIES: frozenset[str] = frozenset({
    "task",
    "interaction_feedback",
    "linked_project",
    "session_capsule",
    "recent_interaction",
    "helper_accessible",
})

OMISSION_CODES: frozenset[str] = frozenset({
    "stale",
    "privacy",
    "unavailable",
    "empty",
    "oversized",
    "unsafe",
    "excluded_by_policy",
})

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "expired", "superseded", "refused", "failed"}
)

# ---------------------------------------------------------------------------
# Schema version identifiers (public)
# ---------------------------------------------------------------------------

SCHEMA_STUCK = "task_initiation_stuck.v1"
SCHEMA_CARD = "task_initiation_card.v1"
SCHEMA_RESPONSE = "task_initiation_response.v1"
SCHEMA_CONTEXT = "task_initiation_context.v1"
SCHEMA_PROPOSAL = "task_initiation_proposal.v1"

_SCHEMA_CARD_RECEIPT = "task_initiation_card_receipt.v1"

ALL_SCHEMA_VERSIONS: frozenset[str] = frozenset({
    SCHEMA_STUCK,
    SCHEMA_CARD,
    SCHEMA_RESPONSE,
    SCHEMA_CONTEXT,
    SCHEMA_PROPOSAL,
})

_TASK_INITIATION_EXTRA_FORBIDDEN: frozenset[str] = frozenset({
    "action",
    "raw_action",
    "action_file",
    "path",
})
_TI_FORBIDDEN_FIELDS: set[str] = set(
    DIRECT_EXECUTION_FIELDS | _TASK_INITIATION_EXTRA_FORBIDDEN
)


class TaskInitiationContractError(ValueError):
    """Validation or policy error with machine-readable code and field."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TASK_REF_RE = re.compile(r"^Tasks(/[\w ._@+%!-]+)+\.md$")
# Detect rooted local locations without maintaining an incomplete list of Unix
# roots.  The negative look-behind avoids matching the path portion of an
# ordinary URL (``https://``) while rejecting even single-component rooted
# paths such as ``/secret`` as well as ``/nix/store/...`` and Windows paths.
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![:/\w])/(?:[^\s,;)\]\"']+)"
    r"|(?<![\w])[A-Za-z]:\\[^\s,;)\]\"']+"
    r"|\bfile:///(?:[^\s,;)\]\"']+)"
    r"|(?<![\w])~/(?:[^\s,;)\]\"']+)"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(data: Mapping[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _payload_sha256(data: Mapping[str, Any]) -> str:
    return _sha256(_canonical_json(data))


def _normalize_text(value: str) -> str:
    if "\x00" in value:
        raise TaskInitiationContractError("invalid_schema", "contains_nul")
    return re.sub(r"\s+", " ", value).strip()


def _require_normalized(value: Any, field: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise TaskInitiationContractError("invalid_schema", field)
    text = _normalize_text(value)
    if not text or len(text) > max_len:
        raise TaskInitiationContractError("invalid_schema", field)
    return text


def _require_optional_normalized(value: Any, field: str, max_len: int) -> str | None:
    if value is None:
        return None
    return _require_normalized(value, field, max_len)


def _require_str(value: Any, field: str, max_len: int | None = None) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise TaskInitiationContractError("invalid_schema", field)
    if max_len is not None and len(value) > max_len:
        raise TaskInitiationContractError("invalid_schema", field)
    return value


def _require_nonempty_str(value: Any, field: str, max_len: int | None = None) -> str:
    text = _require_str(value, field, max_len)
    if not text.strip():
        raise TaskInitiationContractError("invalid_schema", field)
    return text


def _require_epoch(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TaskInitiationContractError("invalid_schema", field)
    return value


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TaskInitiationContractError("invalid_schema", field)
    return value


def _require_sha256(value: Any, field: str) -> str:
    text = _require_str(value, field, 64)
    if not _SHA256_RE.fullmatch(text):
        raise TaskInitiationContractError("invalid_schema", field)
    return text


def _require_enum(value: Any, field: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise TaskInitiationContractError("invalid_schema", field)
    return value


def _require_literal(value: Any, field: str, literal: str) -> str:
    if value != literal:
        raise TaskInitiationContractError("invalid_schema", field)
    return literal


def _require_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TaskInitiationContractError("invalid_schema", field)
    return dict(value)


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise TaskInitiationContractError("invalid_schema", field)
    return list(value)


def _require_uuid4(value: Any, field: str) -> str:
    text = _require_str(value, field)
    if not _UUID4_RE.fullmatch(text):
        raise TaskInitiationContractError("invalid_id", field)
    return text


def _require_ordered(
    earlier: int, later: int, field: str, *, allow_equal: bool = True
) -> None:
    if later < earlier or (not allow_equal and later == earlier):
        raise TaskInitiationContractError("invalid_timestamp", field)


def _check_unknown_fields(
    value: Mapping[str, Any], known: frozenset[str], *, prefix: str = ""
) -> None:
    for key in value:
        if key not in known:
            field = f"{prefix}.{key}" if prefix else str(key)
            raise TaskInitiationContractError("invalid_schema", field)


def _policy_int(
    policy: Mapping[str, Any] | None,
    key: str,
    default: int,
) -> int:
    value = default if policy is None else policy.get(key, default)
    return _require_int(value, f"policy.{key}")


def _check_future_timestamp(
    epoch: int,
    *,
    received_at_epoch: int,
    max_future_skew_seconds: int,
    field: str,
) -> None:
    if epoch > received_at_epoch + max_future_skew_seconds:
        raise TaskInitiationContractError("invalid_timestamp", field)


def _reject_absolute_paths(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_absolute_paths(child, f"{field}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_absolute_paths(child, f"{field}[{index}]")
    elif isinstance(value, str) and _ABSOLUTE_PATH_RE.search(value):
        raise TaskInitiationContractError("privacy_rejected", field)


# ---------------------------------------------------------------------------
# Public structural validators
# ---------------------------------------------------------------------------


def _validate_inline_task_ref(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    _check_unknown_fields(value, frozenset({"source", "ref"}), prefix="task_ref")
    source = _require_enum(value.get("source"), "task_ref.source", TASK_REF_SOURCES)
    ref = _require_str(value.get("ref"), "task_ref.ref", 500)
    if ref.startswith("/") or not _TASK_REF_RE.fullmatch(ref):
        raise TaskInitiationContractError("invalid_schema", "task_ref.ref")
    for segment in ref.split("/"):
        if segment in {".", ".."} or "\\" in segment or "\x00" in segment:
            raise TaskInitiationContractError("invalid_schema", "task_ref.ref")
    return {"source": source, "ref": ref}


def validate_stuck_event(
    value: Mapping[str, Any],
    *,
    now_epoch: int | None = None,
    max_future_skew_seconds: int | None = None,
) -> dict[str, Any]:
    """Validate Stuck structure; optionally apply ingress clock-skew policy."""
    v = dict(value)
    _check_unknown_fields(v, frozenset({
        "schema_version",
        "event_id",
        "source",
        "occurred_at_epoch",
        "task_ref",
        "task_description",
    }))
    _require_literal(v.get("schema_version"), "schema_version", SCHEMA_STUCK)
    event_id = _require_uuid4(v.get("event_id"), "event_id")
    _require_literal(v.get("source"), "source", "tasker")
    occurred = _require_epoch(v.get("occurred_at_epoch"), "occurred_at_epoch")
    if now_epoch is not None:
        skew = max_future_skew_seconds or _MAX_FUTURE_CLOCK_SKEW_SECONDS
        _check_future_timestamp(
            occurred,
            received_at_epoch=now_epoch,
            max_future_skew_seconds=skew,
            field="occurred_at_epoch",
        )
    task_ref_raw = v.get("task_ref")
    task_ref = None if task_ref_raw is None else _validate_inline_task_ref(
        _require_dict(task_ref_raw, "task_ref")
    )
    task_description = _require_optional_normalized(
        v.get("task_description"), "task_description", 500
    )
    return {
        "schema_version": SCHEMA_STUCK,
        "event_id": event_id,
        "source": "tasker",
        "occurred_at_epoch": occurred,
        "task_ref": task_ref,
        "task_description": task_description,
    }


def _validate_blocker(raw: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    value = dict(raw)
    _check_unknown_fields(value, frozenset({"category", "summary"}), prefix=prefix)
    return {
        "category": _require_enum(
            value.get("category"), f"{prefix}.category", BLOCKER_CATEGORIES
        ),
        "summary": _require_normalized(
            value.get("summary"), f"{prefix}.summary", 300
        ),
    }


def _validate_tiny_start(raw: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    value = dict(raw)
    _check_unknown_fields(
        value,
        frozenset({"kind", "instruction", "estimated_minutes", "completion_signal"}),
        prefix=prefix,
    )
    return {
        "kind": _require_enum(value.get("kind"), f"{prefix}.kind", TINY_START_KINDS),
        "instruction": _require_normalized(
            value.get("instruction"), f"{prefix}.instruction", 300
        ),
        "estimated_minutes": _require_int(
            value.get("estimated_minutes"), f"{prefix}.estimated_minutes"
        ),
        "completion_signal": _require_normalized(
            value.get("completion_signal"), f"{prefix}.completion_signal", 200
        ),
    }


def validate_card(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate immutable Card structure; trial caps are a separate policy gate."""
    v = dict(value)
    _check_unknown_fields(v, frozenset({
        "schema_version",
        "card_id",
        "interaction_id",
        "revision",
        "issued_at_epoch",
        "expires_at_epoch",
        "title",
        "task_label",
        "blocker",
        "tiny_start",
        "start_countdown_seconds",
        "actions",
        "dismiss_action",
    }))
    _require_literal(v.get("schema_version"), "schema_version", SCHEMA_CARD)
    issued = _require_epoch(v.get("issued_at_epoch"), "issued_at_epoch")
    expires = _require_epoch(v.get("expires_at_epoch"), "expires_at_epoch")
    _require_ordered(issued, expires, "expires_at_epoch", allow_equal=False)

    blocker = _validate_blocker(_require_dict(v.get("blocker"), "blocker"), prefix="blocker")
    tiny_start = _validate_tiny_start(
        _require_dict(v.get("tiny_start"), "tiny_start"), prefix="tiny_start"
    )

    actions_raw = _require_list(v.get("actions"), "actions")
    if len(actions_raw) != len(CARD_BUTTONS):
        raise TaskInitiationContractError("invalid_schema", "actions")
    actions: list[dict[str, str]] = []
    for index, expected in enumerate(CARD_BUTTONS):
        raw = _require_dict(actions_raw[index], f"actions[{index}]")
        _check_unknown_fields(raw, frozenset({"id", "label"}), prefix=f"actions[{index}]")
        if raw.get("id") != expected["id"] or raw.get("label") != expected["label"]:
            raise TaskInitiationContractError("invalid_schema", f"actions[{index}]")
        actions.append(dict(expected))

    _require_literal(v.get("dismiss_action"), "dismiss_action", "dismiss")
    return {
        "schema_version": SCHEMA_CARD,
        "card_id": _require_uuid4(v.get("card_id"), "card_id"),
        "interaction_id": _require_uuid4(v.get("interaction_id"), "interaction_id"),
        "revision": _require_int(v.get("revision"), "revision"),
        "issued_at_epoch": issued,
        "expires_at_epoch": expires,
        "title": _require_normalized(v.get("title"), "title", 120),
        "task_label": _require_normalized(v.get("task_label"), "task_label", 500),
        "blocker": blocker,
        "tiny_start": tiny_start,
        "start_countdown_seconds": _require_int(
            v.get("start_countdown_seconds"), "start_countdown_seconds"
        ),
        "actions": actions,
        "dismiss_action": "dismiss",
    }


def _validate_card_policy(
    card: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    validated = validate_card(card)
    cap = _policy_int(policy, "start_countdown_seconds_cap", _START_COUNTDOWN_SECONDS_CAP)
    if validated["start_countdown_seconds"] > cap:
        raise TaskInitiationContractError("policy_rejected", "start_countdown_seconds")
    return validated


def validate_response(
    value: Mapping[str, Any],
    *,
    now_epoch: int | None = None,
    max_future_skew_seconds: int | None = None,
) -> dict[str, Any]:
    """Validate Response structure; optionally apply ingress clock-skew policy."""
    v = dict(value)
    _check_unknown_fields(v, frozenset({
        "schema_version",
        "response_id",
        "card_id",
        "action",
        "detail",
        "occurred_at_epoch",
    }))
    _require_literal(v.get("schema_version"), "schema_version", SCHEMA_RESPONSE)
    occurred = _require_epoch(v.get("occurred_at_epoch"), "occurred_at_epoch")
    if now_epoch is not None:
        skew = max_future_skew_seconds or _MAX_FUTURE_CLOCK_SKEW_SECONDS
        _check_future_timestamp(
            occurred,
            received_at_epoch=now_epoch,
            max_future_skew_seconds=skew,
            field="occurred_at_epoch",
        )
    action = _require_enum(v.get("action"), "action", RESPONSE_ACTIONS)
    if action in {"shrink", "blocked"}:
        detail = _require_optional_normalized(v.get("detail"), "detail", 500)
    else:
        if v.get("detail") is not None:
            raise TaskInitiationContractError("invalid_schema", "detail")
        detail = None
    return {
        "schema_version": SCHEMA_RESPONSE,
        "response_id": _require_uuid4(v.get("response_id"), "response_id"),
        "card_id": _require_uuid4(v.get("card_id"), "card_id"),
        "action": action,
        "detail": detail,
        "occurred_at_epoch": occurred,
    }


def _context_policy(policy: Mapping[str, Any] | None) -> dict[str, int]:
    return {
        key: _policy_int(policy, key, default)
        for key, default in _DEFAULT_CONTEXT_POLICY.items()
    }


def _enforce_max_items(items: list[Any], limit: int, field: str) -> None:
    if len(items) > limit:
        raise TaskInitiationContractError("policy_rejected", field)


def _validate_disclosed_facts(
    raw: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    limits = _context_policy(policy)
    value = dict(raw)
    _check_unknown_fields(value, frozenset({
        "task",
        "followup",
        "project_summary",
        "session_capsule",
        "recent_interactions",
        "helper_material",
    }), prefix="disclosed_facts")

    task_raw = _require_dict(value.get("task"), "disclosed_facts.task")
    _check_unknown_fields(task_raw, frozenset({"label"}), prefix="disclosed_facts.task")
    task = {"label": _require_normalized(
        task_raw.get("label"), "disclosed_facts.task.label", 500
    )}

    followup = None
    if value.get("followup") is not None:
        raw_followup = _require_dict(value["followup"], "disclosed_facts.followup")
        _check_unknown_fields(
            raw_followup,
            frozenset({"action", "detail", "prior_tiny_start"}),
            prefix="disclosed_facts.followup",
        )
        followup = {
            "action": _require_enum(
                raw_followup.get("action"),
                "disclosed_facts.followup.action",
                frozenset({"shrink", "blocked"}),
            ),
            "detail": _require_optional_normalized(
                raw_followup.get("detail"), "disclosed_facts.followup.detail", 500
            ),
            "prior_tiny_start": _require_normalized(
                raw_followup.get("prior_tiny_start"),
                "disclosed_facts.followup.prior_tiny_start",
                300,
            ),
        }

    project_summary = None
    if value.get("project_summary") is not None:
        raw_project = _require_dict(
            value["project_summary"], "disclosed_facts.project_summary"
        )
        _check_unknown_fields(
            raw_project,
            frozenset({"title", "summary"}),
            prefix="disclosed_facts.project_summary",
        )
        project_summary = {
            "title": _require_normalized(
                raw_project.get("title"), "disclosed_facts.project_summary.title", 200
            ),
            "summary": _require_normalized(
                raw_project.get("summary"),
                "disclosed_facts.project_summary.summary",
                1000,
            ),
        }

    session_capsule = None
    if value.get("session_capsule") is not None:
        raw_session = _require_dict(
            value["session_capsule"], "disclosed_facts.session_capsule"
        )
        _check_unknown_fields(
            raw_session,
            frozenset({"summary", "ended_at_epoch"}),
            prefix="disclosed_facts.session_capsule",
        )
        session_capsule = {
            "summary": _require_normalized(
                raw_session.get("summary"),
                "disclosed_facts.session_capsule.summary",
                1000,
            ),
            "ended_at_epoch": _require_epoch(
                raw_session.get("ended_at_epoch"),
                "disclosed_facts.session_capsule.ended_at_epoch",
            ),
        }

    recent_raw = _require_list(
        value.get("recent_interactions", []), "disclosed_facts.recent_interactions"
    )
    _enforce_max_items(
        recent_raw,
        limits["max_recent_interactions"],
        "disclosed_facts.recent_interactions",
    )
    recent_interactions: list[dict[str, Any]] = []
    for index, item in enumerate(recent_raw):
        raw_item = _require_dict(
            item, f"disclosed_facts.recent_interactions[{index}]"
        )
        prefix = f"disclosed_facts.recent_interactions[{index}]"
        _check_unknown_fields(
            raw_item,
            frozenset({"user_action", "terminal_status", "resolution_reason", "occurred_at_epoch"}),
            prefix=prefix,
        )
        action = raw_item.get("user_action")
        if action is not None:
            action = _require_enum(action, f"{prefix}.user_action", RESPONSE_ACTIONS)
        recent_interactions.append({
            "user_action": action,
            "terminal_status": _require_enum(
                raw_item.get("terminal_status"),
                f"{prefix}.terminal_status",
                TERMINAL_STATUSES,
            ),
            "resolution_reason": _require_normalized(
                raw_item.get("resolution_reason"), f"{prefix}.resolution_reason", 120
            ),
            "occurred_at_epoch": _require_epoch(
                raw_item.get("occurred_at_epoch"), f"{prefix}.occurred_at_epoch"
            ),
        })

    helper_raw = _require_list(
        value.get("helper_material", []), "disclosed_facts.helper_material"
    )
    _enforce_max_items(
        helper_raw, limits["max_helper_material"], "disclosed_facts.helper_material"
    )
    helper_material: list[dict[str, Any]] = []
    for index, item in enumerate(helper_raw):
        raw_item = _require_dict(item, f"disclosed_facts.helper_material[{index}]")
        prefix = f"disclosed_facts.helper_material[{index}]"
        _check_unknown_fields(raw_item, frozenset({"label", "excerpt"}), prefix=prefix)
        helper_material.append({
            "label": _require_normalized(raw_item.get("label"), f"{prefix}.label", 200),
            "excerpt": _require_normalized(
                raw_item.get("excerpt"),
                f"{prefix}.excerpt",
                limits["max_helper_excerpt_chars"],
            ),
        })

    return {
        "task": task,
        "followup": followup,
        "project_summary": project_summary,
        "session_capsule": session_capsule,
        "recent_interactions": recent_interactions,
        "helper_material": helper_material,
    }


def _validate_provenance(
    raw: list[Any], *, policy: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    limits = _context_policy(policy)
    _enforce_max_items(raw, limits["max_provenance"], "provenance")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        value = _require_dict(item, f"provenance[{index}]")
        prefix = f"provenance[{index}]"
        _check_unknown_fields(
            value,
            frozenset({"category", "source_ref_sha256", "observed_at_epoch", "fresh_until_epoch"}),
            prefix=prefix,
        )
        observed = _require_epoch(value.get("observed_at_epoch"), f"{prefix}.observed_at_epoch")
        fresh = _require_epoch(value.get("fresh_until_epoch"), f"{prefix}.fresh_until_epoch")
        _require_ordered(observed, fresh, f"{prefix}.fresh_until_epoch")
        result.append({
            "category": _require_enum(
                value.get("category"), f"{prefix}.category", PROVENANCE_CATEGORIES
            ),
            "source_ref_sha256": _require_sha256(
                value.get("source_ref_sha256"), f"{prefix}.source_ref_sha256"
            ),
            "observed_at_epoch": observed,
            "fresh_until_epoch": fresh,
        })
    return result


def api_payload_from_context(
    manifest: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return the exact allowlisted semantic payload sent to the model.

    This function is deliberately safe when called with an unvalidated raw
    manifest: nested objects are reconstructed through the same strict
    allowlist validator used by :func:`validate_context`, rather than copied
    wholesale.  Local audit metadata therefore cannot leak through an unknown
    nested key.
    """

    facts = manifest.get("disclosed_facts", {})
    normalized = _validate_disclosed_facts(
        _require_dict(facts, "disclosed_facts"), policy=policy
    )
    payload: dict[str, Any] = {}
    for key in (
        "task",
        "followup",
        "project_summary",
        "session_capsule",
        "recent_interactions",
        "helper_material",
    ):
        value = normalized.get(key)
        if value is not None:
            payload[key] = copy.deepcopy(value)
    _reject_absolute_paths(payload, "disclosed_facts")
    return payload


def validate_context(
    value: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Validate local disclosure manifest and verify the model-content hash."""
    v = dict(value)
    _check_unknown_fields(v, frozenset({
        "schema_version",
        "context_id",
        "interaction_id",
        "revision",
        "task_fingerprint",
        "policy_version",
        "generated_at_epoch",
        "expires_at_epoch",
        "privacy_class",
        "disclosed_facts",
        "provenance",
        "omissions",
        "model_content_sha256",
    }))
    _require_literal(v.get("schema_version"), "schema_version", SCHEMA_CONTEXT)
    generated = _require_epoch(v.get("generated_at_epoch"), "generated_at_epoch")
    expires = _require_epoch(v.get("expires_at_epoch"), "expires_at_epoch")
    _require_ordered(generated, expires, "expires_at_epoch", allow_equal=False)
    disclosed = _validate_disclosed_facts(
        _require_dict(v.get("disclosed_facts"), "disclosed_facts"), policy=policy
    )
    provenance = _validate_provenance(
        _require_list(v.get("provenance"), "provenance"), policy=policy
    )
    limits = _context_policy(policy)
    omission_raw = _require_list(v.get("omissions"), "omissions")
    _enforce_max_items(omission_raw, limits["max_omissions"], "omissions")
    omissions: list[str] = []
    for item in omission_raw:
        code = _require_enum(item, "omissions", OMISSION_CODES)
        if code in omissions:
            raise TaskInitiationContractError("invalid_schema", "omissions")
        omissions.append(code)
    omissions.sort()

    normalized = {
        "schema_version": SCHEMA_CONTEXT,
        "context_id": _require_uuid4(v.get("context_id"), "context_id"),
        "interaction_id": _require_uuid4(v.get("interaction_id"), "interaction_id"),
        "revision": _require_int(v.get("revision"), "revision"),
        "task_fingerprint": _require_sha256(v.get("task_fingerprint"), "task_fingerprint"),
        "policy_version": _require_nonempty_str(
            v.get("policy_version"), "policy_version", 200
        ),
        "generated_at_epoch": generated,
        "expires_at_epoch": expires,
        "privacy_class": _require_literal(
            v.get("privacy_class"), "privacy_class", "sensitive_personal"
        ),
        "disclosed_facts": disclosed,
        "provenance": provenance,
        "omissions": omissions,
        "model_content_sha256": _require_sha256(
            v.get("model_content_sha256"), "model_content_sha256"
        ),
    }
    expected_hash = _payload_sha256(api_payload_from_context(normalized, policy=policy))
    if normalized["model_content_sha256"] != expected_hash:
        raise TaskInitiationContractError("content_hash_mismatch", "model_content_sha256")
    return normalized


def _reject_forbidden_fields(value: Any, field: str) -> None:
    if contains_direct_execution(
        value,
        fields=_TI_FORBIDDEN_FIELDS,
        ignore_empty_dict=True,
    ):
        raise TaskInitiationContractError("proposal_unsafe", field)


def validate_proposal(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate semantic-only model/deterministic proposal output."""
    v = dict(value)
    _check_unknown_fields(v, frozenset({"schema_version", "blocker", "tiny_start"}))
    _require_literal(v.get("schema_version"), "schema_version", SCHEMA_PROPOSAL)
    blocker_raw = _require_dict(v.get("blocker"), "blocker")
    tiny_raw = _require_dict(v.get("tiny_start"), "tiny_start")
    _reject_forbidden_fields(blocker_raw, "blocker")
    _reject_forbidden_fields(tiny_raw, "tiny_start")
    return {
        "schema_version": SCHEMA_PROPOSAL,
        "blocker": _validate_blocker(blocker_raw, prefix="blocker"),
        "tiny_start": _validate_tiny_start(tiny_raw, prefix="tiny_start"),
    }


def _validate_proposal_policy(
    proposal: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    validated = validate_proposal(proposal)
    cap = _policy_int(policy, "tiny_start_minutes_cap", _TINY_START_MINUTES_CAP)
    if validated["tiny_start"]["estimated_minutes"] > cap:
        raise TaskInitiationContractError(
            "policy_rejected", "tiny_start.estimated_minutes"
        )
    return validated


def validate_card_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate provisional notification-posted evidence."""
    v = dict(value)
    _check_unknown_fields(
        v, frozenset({"schema_version", "receipt_id", "card_id", "posted_at_epoch"})
    )
    _require_literal(v.get("schema_version"), "schema_version", _SCHEMA_CARD_RECEIPT)
    return {
        "schema_version": _SCHEMA_CARD_RECEIPT,
        "receipt_id": _require_uuid4(v.get("receipt_id"), "receipt_id"),
        "card_id": _require_uuid4(v.get("card_id"), "card_id"),
        "posted_at_epoch": _require_epoch(v.get("posted_at_epoch"), "posted_at_epoch"),
    }


# ---------------------------------------------------------------------------
# Task resolution and identity
# ---------------------------------------------------------------------------


def resolve_task(
    stuck: Mapping[str, Any],
    session: Mapping[str, Any] | None = None,
    lookup: Any = None,
) -> dict[str, Any]:
    s = dict(stuck)
    task_ref = s.get("task_ref")
    if task_ref is not None:
        if lookup is None:
            raise TaskInitiationContractError("explicit_task_missing", "task_ref")
        result = lookup(task_ref["ref"])
        if result is None:
            raise TaskInitiationContractError("explicit_task_missing", "task_ref")
        if not isinstance(result, dict):
            raise TaskInitiationContractError("explicit_task_invalid", "task_ref")
        label = result.get("label")
        revision = result.get("revision")
        if not isinstance(label, str) or not label.strip():
            raise TaskInitiationContractError("explicit_task_invalid", "task_ref")
        if not isinstance(revision, str) or not _SHA256_RE.fullmatch(revision):
            raise TaskInitiationContractError("explicit_task_invalid", "task_ref")
        return {
            "source": "explicit_task_ref",
            "task_ref": task_ref["ref"],
            "label": _normalize_text(label),
            "source_revision": revision,
        }
    if session is not None:
        session_value = dict(session)
        if (
            session_value.get("status") == "active"
            and session_value.get("session_id")
            and session_value.get("task")
        ):
            label = _normalize_text(str(session_value["task"]))
            if label:
                return {
                    "source": "active_session",
                    "session_id": str(session_value["session_id"]),
                    "label": label,
                }
    description = s.get("task_description")
    if isinstance(description, str) and description.strip():
        return {"source": "fallback_description", "label": _normalize_text(description)}
    raise TaskInitiationContractError("task_unresolved", "task_ref")


def task_fingerprint(resolved_task: Mapping[str, Any]) -> str:
    task = dict(resolved_task)
    source = task.get("source")
    if source == "explicit_task_ref":
        material = (
            f"tasknotes\x00{task.get('task_ref', '')}\x00"
            f"{task.get('source_revision', '')}"
        )
    elif source == "active_session":
        material = (
            f"active_session\x00{task.get('session_id', '')}\x00{task.get('label', '')}"
        )
    elif source == "fallback_description":
        material = f"fallback_description\x00{task.get('label', '')}"
    else:
        raise TaskInitiationContractError("task_unresolved", "task_ref")
    return _sha256(material.encode("utf-8"))


# ---------------------------------------------------------------------------
# Private aggregate reducer and replay reservations
# ---------------------------------------------------------------------------


def _reservation_key(kind: str, message_id: str) -> str:
    return f"{kind}:{message_id}"


def _reserve_message(
    state: Mapping[str, Any],
    *,
    kind: str,
    message_id: str,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Reserve an ID/payload pair. Return (new_state, exact_replay)."""
    key = _reservation_key(kind, message_id)
    payload_hash = _payload_sha256(payload)
    reservations = dict(state.get("message_reservations", {}))
    previous = reservations.get(key)
    if previous is not None:
        if previous != payload_hash:
            raise TaskInitiationContractError("idempotency_conflict", message_id)
        return dict(state), True
    reservations[key] = payload_hash
    result = copy.deepcopy(dict(state))
    result["message_reservations"] = reservations
    return result, False


def _require_phase(state: Mapping[str, Any], *allowed: str) -> None:
    if state.get("phase") not in allowed:
        raise TaskInitiationContractError("invalid_transition", "phase")


def _require_pre_card_deadline(state: Mapping[str, Any], *, now_epoch: int) -> None:
    """Reject work that tries to advance an expired pre-Card request."""

    if not state.get("has_published_card") and now_epoch >= state.get(
        "request_expires_at_epoch", 0
    ):
        raise TaskInitiationContractError("expired", "stuck")


def _resolved_task_label(resolved_task: Mapping[str, Any]) -> str:
    return _require_normalized(resolved_task.get("label"), "resolved_task.label", 500)


def _earliest_epoch(current: Any, candidate: int) -> int:
    if current is None:
        return candidate
    existing = _require_epoch(current, "aggregate_epoch")
    return min(existing, candidate)


def _ingest_stuck(
    existing_state: Mapping[str, Any] | None,
    stuck: Mapping[str, Any],
    *,
    received_at_epoch: int,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validated = validate_stuck_event(stuck)
    if existing_state is not None:
        state, replay = _reserve_message(
            existing_state,
            kind="stuck",
            message_id=validated["event_id"],
            payload=validated,
        )
        if replay:
            return dict(existing_state)
        raise TaskInitiationContractError("idempotency_conflict", "event_id")
    return _new_interaction(
        validated, received_at_epoch=received_at_epoch, policy=dict(policy or {})
    )


def _new_interaction(
    stuck: Mapping[str, Any],
    *,
    received_at_epoch: int,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validated = validate_stuck_event(stuck)
    received_at_epoch = _require_epoch(received_at_epoch, "received_at_epoch")
    skew = _policy_int(policy, "max_future_skew_seconds", _MAX_FUTURE_CLOCK_SKEW_SECONDS)
    _check_future_timestamp(
        validated["occurred_at_epoch"],
        received_at_epoch=received_at_epoch,
        max_future_skew_seconds=skew,
        field="occurred_at_epoch",
    )
    ttl = _policy_int(policy, "stuck_ttl_seconds", _STUCK_TTL_SECONDS)
    expires = validated["occurred_at_epoch"] + ttl
    if received_at_epoch >= expires:
        raise TaskInitiationContractError("expired", "stuck")
    state: dict[str, Any] = {
        "interaction_id": None,
        "event_id": validated["event_id"],
        "phase": "queued",
        "terminal_status": None,
        "resolution_reason": None,
        "resolved_task": None,
        "task_fingerprint": None,
        "current_revision": None,
        "revisions": [],
        "accepted_responses": [],
        "request_occurred_at_epoch": validated["occurred_at_epoch"],
        "request_received_at_epoch": received_at_epoch,
        "request_expires_at_epoch": expires,
        "has_published_card": False,
        "actionable_surface_proven_by_epoch": None,
        "first_response_at_epoch": None,
        "first_response_received_at_epoch": None,
        "start_at_epoch": None,
        "start_received_at_epoch": None,
        "observation_due_at_epoch": None,
        "terminal_at_epoch": None,
        "evidence_issues": set(),
        "state_version": 1,
        "latest_error": None,
        "message_reservations": {},
    }
    reserved, replay = _reserve_message(
        state,
        kind="stuck",
        message_id=validated["event_id"],
        payload=validated,
    )
    assert not replay
    return reserved


def _attach_resolved_task(
    state: Mapping[str, Any],
    resolved_task: Mapping[str, Any],
    *,
    now_epoch: int,
) -> dict[str, Any]:
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        raise TaskInitiationContractError("terminal_immutable", "state")
    if now_epoch < state.get("request_received_at_epoch", 0):
        raise TaskInitiationContractError("invalid_timestamp", "now_epoch")
    _require_phase(state, "queued", "resolving_task")
    _require_pre_card_deadline(state, now_epoch=now_epoch)
    fingerprint = task_fingerprint(resolved_task)
    existing = state.get("task_fingerprint")
    if existing is not None and existing != fingerprint:
        return _supersede_task_changed(state, now_epoch=now_epoch)
    result = copy.deepcopy(dict(state))
    result["resolved_task"] = copy.deepcopy(dict(resolved_task))
    result["task_fingerprint"] = fingerprint
    result["phase"] = "preparing"
    result["state_version"] += 1
    return result


def _supersede_task_changed(
    state: Mapping[str, Any], *, now_epoch: int
) -> dict[str, Any]:
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    result = copy.deepcopy(dict(state))
    if result.get("terminal_status") is None:
        result["terminal_status"] = "superseded"
        result["resolution_reason"] = "task_changed"
        result["terminal_at_epoch"] = now_epoch
        result["state_version"] += 1
    return result


def _verify_task_at_gate(
    state: Mapping[str, Any],
    resolved_task: Mapping[str, Any],
    *,
    gate: Literal["context", "card", "response"],
    now_epoch: int,
) -> dict[str, Any]:
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        return dict(state)
    expected = state.get("task_fingerprint")
    if expected is None:
        raise TaskInitiationContractError("task_unresolved", gate)
    actual = task_fingerprint(resolved_task)
    if actual != expected:
        return _supersede_task_changed(state, now_epoch=now_epoch)
    return dict(state)


def _record_context_prepared(
    state: Mapping[str, Any],
    context: Mapping[str, Any],
    resolved_task: Mapping[str, Any],
    *,
    now_epoch: int,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        raise TaskInitiationContractError("terminal_immutable", "state")
    _require_phase(state, "preparing")
    _require_pre_card_deadline(state, now_epoch=now_epoch)
    if state.get("prepared_context_id") is not None:
        raise TaskInitiationContractError("context_already_prepared", "context_id")
    checked = _verify_task_at_gate(
        state, resolved_task, gate="context", now_epoch=now_epoch
    )
    if checked.get("terminal_status") is not None:
        return checked
    validated = validate_context(context, policy=policy)
    if validated["task_fingerprint"] != checked["task_fingerprint"]:
        return _supersede_task_changed(checked, now_epoch=now_epoch)
    if validated["generated_at_epoch"] > now_epoch:
        raise TaskInitiationContractError("invalid_timestamp", "generated_at_epoch")
    if validated["generated_at_epoch"] < checked.get("request_received_at_epoch", 0):
        raise TaskInitiationContractError("invalid_timestamp", "generated_at_epoch")
    if now_epoch >= validated["expires_at_epoch"]:
        raise TaskInitiationContractError("expired", "context")
    if validated["disclosed_facts"]["task"]["label"] != _resolved_task_label(
        resolved_task
    ):
        raise TaskInitiationContractError("task_mismatch", "disclosed_facts.task.label")
    expected_revision = (checked.get("current_revision") or 0) + 1
    if validated["revision"] != expected_revision:
        raise TaskInitiationContractError("invalid_revision", "revision")
    if checked.get("interaction_id") is not None and (
        validated["interaction_id"] != checked["interaction_id"]
    ):
        raise TaskInitiationContractError("invalid_id", "interaction_id")
    if any(
        revision.get("context_id") == validated["context_id"]
        for revision in checked.get("revisions", [])
    ):
        raise TaskInitiationContractError("duplicate_context", "context_id")
    result = copy.deepcopy(checked)
    if result.get("interaction_id") is None:
        result["interaction_id"] = validated["interaction_id"]
    result["prepared_context_id"] = validated["context_id"]
    result["prepared_context_revision"] = validated["revision"]
    result["prepared_context"] = validated
    result.pop("prepared_proposal", None)
    result.pop("prepared_proposal_sha256", None)
    result.pop("prepared_proposal_revision", None)
    result["state_version"] += 1
    return result


def _record_proposal_validated(
    state: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    now_epoch: int,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind one validated semantic proposal to the prepared revision."""

    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        raise TaskInitiationContractError("terminal_immutable", "state")
    _require_phase(state, "preparing")
    _require_pre_card_deadline(state, now_epoch=now_epoch)
    expected_revision = (state.get("current_revision") or 0) + 1
    if state.get("prepared_context_id") is None:
        raise TaskInitiationContractError("context_required", "proposal")
    if state.get("prepared_context_revision") != expected_revision:
        raise TaskInitiationContractError("invalid_revision", "proposal")
    if state.get("prepared_proposal") is not None:
        raise TaskInitiationContractError("proposal_already_prepared", "proposal")
    prepared_context = state.get("prepared_context")
    if not isinstance(prepared_context, Mapping):
        raise TaskInitiationContractError("context_required", "proposal")
    if now_epoch >= prepared_context["expires_at_epoch"]:
        raise TaskInitiationContractError("expired", "context")
    if now_epoch < prepared_context["generated_at_epoch"]:
        raise TaskInitiationContractError("invalid_timestamp", "now_epoch")
    validated = _validate_proposal_policy(proposal, policy=policy)
    result = copy.deepcopy(dict(state))
    result["prepared_proposal"] = validated
    result["prepared_proposal_sha256"] = _payload_sha256(validated)
    result["prepared_proposal_revision"] = expected_revision
    result["prepared_proposal_at_epoch"] = now_epoch
    result["state_version"] += 1
    return result


def _find_revision(
    state: Mapping[str, Any], card_id: str
) -> tuple[int, dict[str, Any]] | None:
    for index, revision in enumerate(state.get("revisions", [])):
        if revision.get("card_id") == card_id:
            return index, revision
    return None


def _current_revision(state: Mapping[str, Any]) -> dict[str, Any] | None:
    current = state.get("current_revision")
    if current is None:
        return None
    for revision in state.get("revisions", []):
        if revision.get("revision") == current:
            return revision
    return None


def _record_card_published(
    state: Mapping[str, Any],
    card: Mapping[str, Any],
    *,
    now_epoch: int,
    resolved_task: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        raise TaskInitiationContractError("terminal_immutable", "state")
    _require_phase(state, "preparing")
    _require_pre_card_deadline(state, now_epoch=now_epoch)
    checked = _verify_task_at_gate(
        state, resolved_task, gate="card", now_epoch=now_epoch
    )
    if checked.get("terminal_status") is not None:
        return checked
    validated = _validate_card_policy(card, policy=policy)
    expected_revision = 1 if checked.get("current_revision") is None else checked["current_revision"] + 1
    if checked.get("prepared_context_id") is None:
        raise TaskInitiationContractError("context_required", "card")
    if checked.get("prepared_context_revision") != expected_revision:
        raise TaskInitiationContractError("invalid_revision", "prepared_context")
    if checked.get("prepared_proposal") is None:
        raise TaskInitiationContractError("proposal_required", "card")
    if checked.get("prepared_proposal_revision") != expected_revision:
        raise TaskInitiationContractError("invalid_revision", "prepared_proposal")
    if validated["revision"] != expected_revision:
        raise TaskInitiationContractError("invalid_revision", "revision")
    if checked.get("interaction_id") is not None and (
        validated["interaction_id"] != checked["interaction_id"]
    ):
        raise TaskInitiationContractError("invalid_id", "interaction_id")
    if any(
        revision.get("card_id") == validated["card_id"]
        for revision in checked.get("revisions", [])
    ):
        raise TaskInitiationContractError("duplicate_card", "card_id")
    if any(
        revision.get("revision") == validated["revision"]
        for revision in checked.get("revisions", [])
    ):
        raise TaskInitiationContractError("invalid_revision", "revision")
    if validated["issued_at_epoch"] > now_epoch:
        raise TaskInitiationContractError("invalid_timestamp", "issued_at_epoch")
    if validated["issued_at_epoch"] < checked.get("prepared_proposal_at_epoch", 0):
        raise TaskInitiationContractError("invalid_timestamp", "issued_at_epoch")
    if now_epoch >= validated["expires_at_epoch"]:
        raise TaskInitiationContractError("expired", "card")
    prepared_context = checked.get("prepared_context")
    if not isinstance(prepared_context, Mapping):
        raise TaskInitiationContractError("context_required", "card")
    if now_epoch >= prepared_context["expires_at_epoch"]:
        raise TaskInitiationContractError("expired", "context")
    expected_label = _resolved_task_label(resolved_task)
    if validated["task_label"] != expected_label:
        raise TaskInitiationContractError("task_mismatch", "task_label")
    prepared_proposal = checked["prepared_proposal"]
    if validated["blocker"] != prepared_proposal["blocker"]:
        raise TaskInitiationContractError("proposal_mismatch", "blocker")
    if validated["tiny_start"] != prepared_proposal["tiny_start"]:
        raise TaskInitiationContractError("proposal_mismatch", "tiny_start")

    revision = {
        "revision": validated["revision"],
        "context_id": checked.get("prepared_context_id"),
        "context": copy.deepcopy(dict(prepared_context)),
        "proposal": copy.deepcopy(dict(prepared_proposal)),
        "proposal_sha256": checked.get("prepared_proposal_sha256"),
        "task_fingerprint": checked.get("task_fingerprint"),
        "card_id": validated["card_id"],
        "card": validated,
        "card_issued_at_epoch": validated["issued_at_epoch"],
        "card_expires_at_epoch": validated["expires_at_epoch"],
        "receipt": None,
        "receipt_payload_sha256": None,
        "card_posted_at_epoch": None,
        "response": None,
        "response_payload_sha256": None,
        "delivery_evidence": "none",
        "delivery_occurred_at_epoch": None,
        "evidence_issues": set(),
    }
    result = copy.deepcopy(checked)
    result["revisions"].append(revision)
    result["interaction_id"] = validated["interaction_id"]
    result["current_revision"] = validated["revision"]
    result["has_published_card"] = True
    result["phase"] = "awaiting_response"
    for key in (
        "prepared_context_id",
        "prepared_context_revision",
        "prepared_context",
        "prepared_proposal",
        "prepared_proposal_sha256",
        "prepared_proposal_revision",
        "prepared_proposal_at_epoch",
    ):
        result.pop(key, None)
    result["state_version"] += 1
    return result


def _record_card_receipt(
    state: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    received_at_epoch: int,
) -> dict[str, Any]:
    received_at_epoch = _require_epoch(received_at_epoch, "received_at_epoch")
    validated = validate_card_receipt(receipt)
    reserved, replay = _reserve_message(
        state,
        kind="receipt",
        message_id=validated["receipt_id"],
        payload=validated,
    )
    if replay:
        return dict(state)
    found = _find_revision(reserved, validated["card_id"])
    if found is None:
        raise TaskInitiationContractError("invalid_id", "card_id")
    index, revision = found
    if received_at_epoch < revision["card_issued_at_epoch"]:
        raise TaskInitiationContractError("invalid_timestamp", "received_at_epoch")
    if revision.get("receipt") is not None:
        raise TaskInitiationContractError("receipt_already_recorded", "card_id")

    posted = validated["posted_at_epoch"]
    consistent = (
        revision["card_issued_at_epoch"] <= posted < revision["card_expires_at_epoch"]
    )
    response = revision.get("response")
    if consistent and response is not None and response.get("occurred_at_epoch_usable"):
        consistent = posted <= response["occurred_at_epoch"]

    result = copy.deepcopy(reserved)
    target = result["revisions"][index]
    target["receipt"] = {
        **validated,
        "received_at_epoch": received_at_epoch,
    }
    target["receipt_payload_sha256"] = _payload_sha256(validated)
    if consistent:
        target["card_posted_at_epoch"] = posted
        if target.get("delivery_evidence") not in {None, "none", "posted"}:
            target["evidence_issues"].add("delivery_evidence_conflict")
            result["evidence_issues"].add("delivery_evidence_conflict")
        # A validated posting receipt is stronger evidence than an earlier
        # adapter attempt result.  It prevents a later no-response expiry from
        # being misclassified as "not posted" while never reopening terminal
        # state.
        target["delivery_evidence"] = "posted"
        target["delivery_occurred_at_epoch"] = posted
    else:
        target["evidence_issues"].add("receipt_timestamp_inconsistent")
        result["evidence_issues"].add("receipt_timestamp_inconsistent")
    result["state_version"] += 1
    return result


def _record_delivery_result(
    state: Mapping[str, Any],
    *,
    card_id: str,
    result: Literal["confirmed_not_posted", "ambiguous"],
    occurred_at_epoch: int,
) -> dict[str, Any]:
    occurred = _require_epoch(occurred_at_epoch, "occurred_at_epoch")
    found = _find_revision(state, card_id)
    if found is None:
        raise TaskInitiationContractError("invalid_id", "card_id")
    index, _ = found
    output = copy.deepcopy(dict(state))
    target = output["revisions"][index]
    if occurred < target["card_issued_at_epoch"]:
        raise TaskInitiationContractError("invalid_timestamp", "occurred_at_epoch")
    if result not in {"confirmed_not_posted", "ambiguous"}:
        raise TaskInitiationContractError("invalid_schema", "result")
    current = target.get("delivery_evidence", "none")
    current_epoch = target.get("delivery_occurred_at_epoch")
    if (
        current == result
        and current_epoch == occurred
    ):
        return dict(state)
    if current == "posted":
        raise TaskInitiationContractError("delivery_evidence_conflict", "card_id")
    if current != "none":
        raise TaskInitiationContractError("delivery_evidence_conflict", "card_id")
    target["delivery_evidence"] = result
    target["delivery_occurred_at_epoch"] = occurred
    output["state_version"] += 1
    return output


def _apply_response(
    state: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    received_at_epoch: int,
    resolved_task: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    received_at_epoch = _require_epoch(received_at_epoch, "received_at_epoch")
    validated = validate_response(response)
    reserved, replay = _reserve_message(
        state,
        kind="response",
        message_id=validated["response_id"],
        payload=validated,
    )
    if replay:
        return dict(state)
    found_before_terminal = _find_revision(reserved, validated["card_id"])
    if found_before_terminal is None:
        raise TaskInitiationContractError("invalid_id", "card_id")
    if found_before_terminal[1].get("response") is not None:
        raise TaskInitiationContractError("card_already_responded", "card_id")
    if state.get("terminal_status") is not None:
        raise TaskInitiationContractError("terminal_immutable", "state")
    _require_phase(state, "awaiting_response")
    checked = _verify_task_at_gate(
        reserved, resolved_task, gate="response", now_epoch=received_at_epoch
    )
    if checked.get("terminal_status") is not None:
        return checked
    found = _find_revision(checked, validated["card_id"])
    if found is None:
        raise TaskInitiationContractError("invalid_id", "card_id")
    index, revision = found
    if received_at_epoch < revision["card_issued_at_epoch"]:
        raise TaskInitiationContractError("invalid_timestamp", "received_at_epoch")
    if revision["revision"] != checked.get("current_revision"):
        raise TaskInitiationContractError("stale_card", "card_id")
    if received_at_epoch >= revision["card_expires_at_epoch"]:
        raise TaskInitiationContractError("expired", "response")

    skew = _policy_int(policy, "max_future_skew_seconds", _MAX_FUTURE_CLOCK_SKEW_SECONDS)
    occurred = validated["occurred_at_epoch"]
    timestamp_consistent = (
        revision["card_issued_at_epoch"] <= occurred < revision["card_expires_at_epoch"]
        and occurred <= received_at_epoch + skew
    )

    result = copy.deepcopy(checked)
    target = result["revisions"][index]
    response_record = {
        **validated,
        "received_at_epoch": received_at_epoch,
        "occurred_at_epoch_usable": timestamp_consistent,
    }
    target["response"] = response_record
    target["response_payload_sha256"] = _payload_sha256(validated)
    if not timestamp_consistent:
        target["evidence_issues"].add("response_timestamp_inconsistent")
        result["evidence_issues"].add("response_timestamp_inconsistent")

    result["accepted_responses"].append({
        "response_id": validated["response_id"],
        "card_id": validated["card_id"],
        "revision": target["revision"],
        "user_action": validated["action"],
        "detail": validated["detail"],
    })
    proven = occurred if timestamp_consistent else received_at_epoch
    result["actionable_surface_proven_by_epoch"] = _earliest_epoch(
        result.get("actionable_surface_proven_by_epoch"), proven
    )
    result["first_response_received_at_epoch"] = _earliest_epoch(
        result.get("first_response_received_at_epoch"), received_at_epoch
    )
    if timestamp_consistent:
        result["first_response_at_epoch"] = _earliest_epoch(
            result.get("first_response_at_epoch"), occurred
        )
    if validated["action"] == "start":
        result["start_received_at_epoch"] = _earliest_epoch(
            result.get("start_received_at_epoch"), received_at_epoch
        )
        if timestamp_consistent:
            result["start_at_epoch"] = _earliest_epoch(
                result.get("start_at_epoch"), occurred
            )

    max_revisions = _policy_int(policy, "max_card_revisions", _MAX_CARD_REVISIONS)
    action = validated["action"]
    if action in {"defer", "dismiss"}:
        result["terminal_status"] = "completed"
        result["resolution_reason"] = "deferred" if action == "defer" else "dismissed"
        result["terminal_at_epoch"] = received_at_epoch
        result["phase"] = "observing"
    elif action in {"shrink", "blocked"}:
        if target["revision"] >= max_revisions:
            result["terminal_status"] = "completed"
            result["resolution_reason"] = (
                "shrink_limit_reached" if action == "shrink" else "blocked_unresolved"
            )
            result["terminal_at_epoch"] = received_at_epoch
            result["phase"] = "observing"
        else:
            result["phase"] = "preparing"
            for key in (
                "prepared_context_id",
                "prepared_context_revision",
                "prepared_context",
                "prepared_proposal",
                "prepared_proposal_sha256",
                "prepared_proposal_revision",
                "prepared_proposal_at_epoch",
            ):
                result.pop(key, None)
    elif action == "start":
        observation = _policy_int(policy, "observation_seconds", _OBSERVATION_SECONDS)
        result["observation_due_at_epoch"] = received_at_epoch + observation
        result["phase"] = "observing"
    result["state_version"] += 1
    return result


def _advance_time(
    state: Mapping[str, Any],
    *,
    now_epoch: int,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del policy  # reserved for later runtime policy; keeps signature stable for candidate tests
    now_epoch = _require_epoch(now_epoch, "now_epoch")
    if state.get("terminal_status") is not None:
        return dict(state)
    result = copy.deepcopy(dict(state))
    if (
        result.get("phase") == "observing"
        and result.get("observation_due_at_epoch") is not None
        and now_epoch >= result["observation_due_at_epoch"]
    ):
        result["terminal_status"] = "completed"
        result["resolution_reason"] = "start_observation_elapsed"
        result["terminal_at_epoch"] = now_epoch
        result["state_version"] += 1
        return result

    if result.get("phase") == "awaiting_response":
        revision = _current_revision(result)
        if revision is not None and now_epoch >= revision["card_expires_at_epoch"]:
            delivery = revision.get("delivery_evidence", "none")
            if delivery == "confirmed_not_posted":
                result["terminal_status"] = "expired"
                result["resolution_reason"] = "card_not_posted_before_expiry"
            elif delivery == "ambiguous":
                result["terminal_status"] = "failed"
                result["resolution_reason"] = "delivery_ambiguous"
            else:
                result["terminal_status"] = "expired"
                result["resolution_reason"] = "card_expired_without_response"
            result["terminal_at_epoch"] = now_epoch
            result["phase"] = "observing"
            result["state_version"] += 1
            return result

    # Request TTL governs only work before the first Card has been published.
    if (
        not result.get("has_published_card")
        and result.get("phase") in {"queued", "resolving_task", "preparing"}
        and now_epoch >= result["request_expires_at_epoch"]
    ):
        result["terminal_status"] = "expired"
        result["resolution_reason"] = "request_expired"
        result["terminal_at_epoch"] = now_epoch
        result["phase"] = "observing"
        result["state_version"] += 1
    return result
