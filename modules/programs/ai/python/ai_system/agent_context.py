"""Read-only context pack for deterministic and future LLM proposal producers.

The context pack is the stable input contract for agentic planning.
It gathers vault state and recent events into one JSON-safe object.

This module must remain non-executing:
- it does not create action files;
- it does not write phone nudges;
- it does not call an LLM;
- optional writes are limited to state/agent/context.json and status.md.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text, read_json, read_jsonl
from ai_system.time_utils import get_timezone
from ai_system.interaction_lifecycle import clear_reason_for_active_nudge


DEFAULT_AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
DEFAULT_TIMEZONE = os.environ.get("AI_AGENT_CONTEXT_TIMEZONE", "Europe/Paris")

ACTIVE_SESSION_STATUSES = {"active", "running", "started"}
ACTIVE_NUDGE_STATUSES = {"active"}
ACTIVE_QUESTION_STATUSES = {"active", "pending"}
ACTIVE_RECOVERY_STATUSES = {"active", "observing"}
TERMINAL_RECOVERY_STATUSES = {"possible_success", "possible_abort", "expired", "cancelled", "completed"}


def current_epoch() -> int:
    return int(time.time())


def iso_from_epoch(epoch: int, tz) -> str:
    return datetime.fromtimestamp(int(epoch), tz).isoformat(timespec="seconds")


def date_from_epoch(epoch: int, tz) -> str:
    return datetime.fromtimestamp(int(epoch), tz).strftime("%Y-%m-%d")


def parse_epoch(value: Any) -> int:
    if value is None:
        return 0

    try:
        return int(float(value))
    except Exception:
        pass

    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def event_epoch(event: Any) -> int:
    if not isinstance(event, dict):
        return 0

    return (
        parse_epoch(event.get("timestamp_epoch"))
        or parse_epoch(event.get("processed_at"))
        or parse_epoch(event.get("timestamp"))
        or parse_epoch(event.get("updated_at"))
        or parse_epoch(event.get("created_at"))
    )


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_status(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("status") or "").strip().lower()


def active_session(session: dict[str, Any]) -> bool:
    status = safe_status(session)
    if status in ACTIVE_SESSION_STATUSES:
        return True

    if session.get("active") is True:
        return True

    return False


def active_recovery(recovery: dict[str, Any]) -> bool:
    return safe_status(recovery) in ACTIVE_RECOVERY_STATUSES


def normalize_active_nudge_candidate(value: Any) -> dict[str, Any]:
   candidate = safe_dict(value)
   if safe_status(candidate) not in ACTIVE_NUDGE_STATUSES:
       return {}

   normalized = dict(candidate)

   # interaction-state.json historically stores compact active_nudge objects.
   # Lifecycle helpers expect the full phone_interaction nudge shape.
   normalized.setdefault("schema_version", "phone_interaction.v1")
   normalized.setdefault("kind", "nudge")

   return normalized


def merge_active_nudge_candidates(
   current: dict[str, Any],
   compact: dict[str, Any],
) -> dict[str, Any]:
   merged = dict(current)

   for key, value in compact.items():
       if value in (None, "", []):
           continue
       merged[key] = value

   return merged


def active_nudge_candidates(
   nudge: dict[str, Any],
   interaction_state: dict[str, Any],
) -> list[dict[str, Any]]:
   current = normalize_active_nudge_candidate(nudge)
   compact = normalize_active_nudge_candidate(interaction_state.get("active_nudge"))

   current_id = current.get("nudge_id")
   compact_id = compact.get("nudge_id")

   if current and compact and current_id and current_id == compact_id:
       return [merge_active_nudge_candidates(current, compact)]

   candidates: list[dict[str, Any]] = []
   if current:
       candidates.append(current)
   if compact:
       candidates.append(compact)

   return candidates


def active_nudge_clear_reason(
   nudge: dict[str, Any],
   interaction_state: dict[str, Any],
) -> str | None:
   saw_expired_reason: str | None = None

   for candidate in active_nudge_candidates(nudge, interaction_state):
       clear_reason = clear_reason_for_active_nudge({"active_nudge": candidate})
       if clear_reason:
           saw_expired_reason = saw_expired_reason or clear_reason
           continue
       return None

   return saw_expired_reason


def active_nudge(nudge: dict[str, Any], interaction_state: dict[str, Any]) -> bool:
   for candidate in active_nudge_candidates(nudge, interaction_state):
       clear_reason = clear_reason_for_active_nudge({"active_nudge": candidate})
       if not clear_reason:
           return True

   return False


def active_question(question: dict[str, Any], interaction_state: dict[str, Any]) -> bool:
    if safe_status(question) in ACTIVE_QUESTION_STATUSES:
        return True

    active = interaction_state.get("active_question")
    if isinstance(active, dict) and safe_status(active) in ACTIVE_QUESTION_STATUSES:
        return True

    return False


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def anki_due_count(anki: dict[str, Any]) -> int:
    for key in [
        "due",
        "due_count",
        "cards_due",
        "total_due",
        "totalDue",
        "new_plus_review_due",
    ]:
        if key in anki:
            value = int_value(anki.get(key), default=0)
            if value > 0:
                return value

    totals = anki.get("totals")
    if isinstance(totals, dict):
        total_due = anki_due_count(totals)
        if total_due > 0:
            return total_due

    for key in ["counts", "due_counts", "deck_counts"]:
        value = anki.get(key)
        if isinstance(value, dict):
            total = 0
            for item in value.values():
                total += max(0, int_value(item, default=0))
            if total > 0:
                return total

    summary = anki.get("summary")
    if isinstance(summary, dict):
        return anki_due_count(summary)

    return 0


def desktop_verdict(desktop: dict[str, Any]) -> str:
    for key in ["verdict", "alignment", "status"]:
        value = str(desktop.get(key) or "").strip().lower()
        if value:
            return value
    return "unknown"


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}

    keys = [
        "schema_version",
        "event",
        "event_type",
        "action",
        "source",
        "device",
        "timestamp",
        "timestamp_epoch",
        "processed_at",
        "date",
        "time",
        "status",
        "reason",
        "nudge_id",
        "question_id",
        "recovery_id",
        "target_id",
        "target_name",
        "snooze_minutes",
        "snoozed_until",
        "message",
        "raw_file",
    ]

    out = {key: event.get(key) for key in keys if key in event}

    if "timestamp_epoch" not in out:
        epoch = event_epoch(event)
        if epoch:
            out["timestamp_epoch"] = epoch

    return out


def read_recent_events(events_dir: Path, *, limit: int = 25, days: int = 2, now_epoch: int | None = None, tz=None) -> list[dict[str, Any]]:
    events_dir = Path(events_dir)

    if not events_dir.exists():
        return []

    if tz is None:
        tz = get_timezone(DEFAULT_TIMEZONE)

    if now_epoch is None:
        now_epoch = current_epoch()

    allowed_dates = {
        (datetime.fromtimestamp(now_epoch, tz) - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(max(1, days))
    }

    events: list[dict[str, Any]] = []
    for path in sorted(events_dir.glob("*.jsonl")):
        if path.stem not in allowed_dates:
            continue
        events.extend(read_jsonl(path))

    events = [event for event in events if isinstance(event, dict)]
    events.sort(key=event_epoch)

    if limit <= 0:
        return []

    return [compact_event(event) for event in events[-limit:]]


def latest_event_named(events: list[dict[str, Any]], names: set[str]) -> dict[str, Any] | None:
    for event in sorted(events, key=event_epoch, reverse=True):
        event_name = str(event.get("event") or event.get("event_type") or event.get("action") or "").strip()
        if event_name in names:
            return event
    return None


def recent_snooze(actions: list[dict[str, Any]], now_epoch: int, cooldown_seconds: int) -> tuple[bool, int | None, dict[str, Any] | None]:
    event = latest_event_named(actions, {"snooze_nudge", "nudge_snoozed"})
    if not event:
        return False, None, None

    epoch = event_epoch(event)
    if epoch <= 0:
        return False, None, event

    age = max(0, now_epoch - epoch)
    return age < cooldown_seconds, age, event


def recent_terminal_recovery(recovery: dict[str, Any], now_epoch: int, cooldown_seconds: int) -> tuple[bool, int | None]:
    status = safe_status(recovery)
    if status not in TERMINAL_RECOVERY_STATUSES:
        return False, None

    # For terminal recovery states, prefer lifecycle/classification evidence
    # over the top-level updated_at timestamp. updated_at can be rewritten by
    # later status rendering, while last_lifecycle_event/classification carries
    # the actual terminal transition time.
    candidates = []

    last_lifecycle = recovery.get("last_lifecycle_event")
    if isinstance(last_lifecycle, dict):
        candidates.extend([
            last_lifecycle.get("processed_at"),
            last_lifecycle.get("timestamp"),
            last_lifecycle.get("timestamp_epoch"),
        ])

    classification = recovery.get("classification")
    if isinstance(classification, dict):
        candidates.extend([
            classification.get("classified_at"),
            classification.get("updated_at"),
        ])

    candidates.extend([
        recovery.get("classified_at"),
        recovery.get("processed_at"),
        recovery.get("timestamp"),
        recovery.get("timestamp_epoch"),
        recovery.get("updated_at"),
    ])

    epoch = 0
    for item in candidates:
        epoch = parse_epoch(item)
        if epoch:
            break

    if epoch <= 0:
        return False, None

    age = max(0, now_epoch - epoch)
    return age < cooldown_seconds, age


def build_derived_facts(
    *,
    session: dict[str, Any],
    anki: dict[str, Any],
    desktop: dict[str, Any],
    recovery: dict[str, Any],
    current_nudge: dict[str, Any],
    current_question: dict[str, Any],
    interaction_state: dict[str, Any],
    recent_actions: list[dict[str, Any]],
    now_epoch: int,
    snooze_cooldown_seconds: int,
    recent_recovery_cooldown_seconds: int,
) -> dict[str, Any]:
    snooze_recent, snooze_age, latest_snooze = recent_snooze(
        recent_actions,
        now_epoch,
        snooze_cooldown_seconds,
    )

    recovery_recent, recovery_age = recent_terminal_recovery(
        recovery,
        now_epoch,
        recent_recovery_cooldown_seconds,
    )

    return {
        "has_active_session": active_session(session),
        "has_active_nudge": active_nudge(current_nudge, interaction_state),
        "active_nudge_clear_reason": active_nudge_clear_reason(current_nudge, interaction_state),
        "has_active_question": active_question(current_question, interaction_state),
        "has_active_recovery": active_recovery(recovery),
        "recent_terminal_recovery": recovery_recent,
        "recent_terminal_recovery_age_seconds": recovery_age,
        "recent_snooze": snooze_recent,
        "recent_snooze_age_seconds": snooze_age,
        "latest_snooze": latest_snooze or {},
        "anki_due": anki_due_count(anki),
        "desktop_verdict": desktop_verdict(desktop),
    }


def build_agent_context(
    ai_dir: str | Path | None = None,
    *,
    now_epoch: int | None = None,
    timezone_name: str | None = None,
    event_limit: int = 25,
    recent_days: int = 2,
    snooze_cooldown_seconds: int = 1800,
    recent_recovery_cooldown_seconds: int = 1800,
) -> dict[str, Any]:
    ai_dir = Path(ai_dir or DEFAULT_AI_DIR).expanduser()
    tz = get_timezone(timezone_name or DEFAULT_TIMEZONE)

    if now_epoch is None:
        now_epoch = current_epoch()

    state_dir = ai_dir / "state"
    outbox_to_phone_dir = ai_dir / "outbox" / "to-phone"
    events_dir = ai_dir / "events"

    session = safe_dict(read_json(state_dir / "session" / "current.json", {}))
    anki = safe_dict(read_json(state_dir / "anki" / "status.json", {}))

    # Compatibility:
    # anki-bridge currently writes the live status to AI/anki/status.json.
    # New shared-agent consumers prefer AI/state/anki/status.json.
    # Read the canonical state path first, then fall back to the legacy bridge path.
    if not anki or anki.get("error"):
        legacy_anki = safe_dict(read_json(ai_dir / "anki" / "status.json", {}))
        if legacy_anki and not legacy_anki.get("error"):
            anki = legacy_anki
    desktop = safe_dict(read_json(state_dir / "desktop" / "now.json", {}))
    recovery = safe_dict(read_json(state_dir / "recovery" / "current.json", {}))
    current_nudge = safe_dict(read_json(outbox_to_phone_dir / "current-nudge.json", {}))
    current_question = safe_dict(read_json(outbox_to_phone_dir / "current-question.json", {}))
    interaction_state = safe_dict(read_json(outbox_to_phone_dir / "interaction-state.json", {}))

    recent_actions = read_recent_events(
        events_dir / "actions",
        limit=event_limit,
        days=recent_days,
        now_epoch=now_epoch,
        tz=tz,
    )
    recent_recovery = read_recent_events(
        events_dir / "recovery",
        limit=event_limit,
        days=recent_days,
        now_epoch=now_epoch,
        tz=tz,
    )
    recent_phone = read_recent_events(
        events_dir / "phone",
        limit=event_limit,
        days=recent_days,
        now_epoch=now_epoch,
        tz=tz,
    )

    facts = build_derived_facts(
        session=session,
        anki=anki,
        desktop=desktop,
        recovery=recovery,
        current_nudge=current_nudge,
        current_question=current_question,
        interaction_state=interaction_state,
        recent_actions=recent_actions,
        now_epoch=now_epoch,
        snooze_cooldown_seconds=snooze_cooldown_seconds,
        recent_recovery_cooldown_seconds=recent_recovery_cooldown_seconds,
    )

    return {
        "schema_version": "agent_context.v1",
        "generated_at": iso_from_epoch(now_epoch, tz),
        "timestamp_epoch": now_epoch,
        "source": "agent-context",
        "timezone": str(tz),
        "cooldowns": {
            "snooze_cooldown_seconds": snooze_cooldown_seconds,
            "recent_recovery_cooldown_seconds": recent_recovery_cooldown_seconds,
        },
        "state": {
            "session": session,
            "anki": anki,
            "desktop": desktop,
            "recovery": recovery,
            "current_nudge": current_nudge,
            "current_question": current_question,
            "interaction_state": interaction_state,
        },
        "recent_events": {
            "actions": recent_actions,
            "recovery": recent_recovery,
            "phone": recent_phone,
        },
        "derived_facts": facts,
        "agent_contract": {
            "proposal_schema": "agent_recovery_proposal.v1",
            "validation_gate": "ai_system.proposal_gate.validate_recovery_proposal",
            "execution_rule": "LLM/agent may propose only; deterministic gate validates; action-bridge executes after user action.",
        },
    }


def write_agent_context(ai_dir: str | Path | None = None, **kwargs: Any) -> dict[str, Any]:
    ai_dir = Path(ai_dir or DEFAULT_AI_DIR).expanduser()
    context = build_agent_context(ai_dir, **kwargs)

    state_dir = ai_dir / "state" / "agent"
    context_json = state_dir / "context.json"
    status_md = state_dir / "status.md"

    atomic_write_json(context_json, context)

    facts = context.get("derived_facts", {})
    lines = [
        "# Agent Context",
        "",
        f"Updated: {context.get('generated_at', '')}",
        f"Schema: `{context.get('schema_version', '')}`",
        "",
        "## Derived facts",
        "",
        "```json",
        json.dumps(facts, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Contract",
        "",
        context.get("agent_contract", {}).get("execution_rule", ""),
        "",
    ]

    atomic_write_text(status_md, "\n".join(lines))
    return context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local AI agent context pack")
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR), help="AI directory inside the vault")
    parser.add_argument("--dry-run", action="store_true", help="Print context JSON without writing")
    parser.add_argument("--write", action="store_true", help="Write state/agent/context.json and status.md")
    parser.add_argument("--event-limit", type=int, default=25, help="Max recent events per stream")
    parser.add_argument("--recent-days", type=int, default=2, help="Recent event date window")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    kwargs = {
        "event_limit": args.event_limit,
        "recent_days": args.recent_days,
    }

    if args.write:
        context = write_agent_context(args.ai_dir, **kwargs)
    else:
        context = build_agent_context(args.ai_dir, **kwargs)

    print(json.dumps(context, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
