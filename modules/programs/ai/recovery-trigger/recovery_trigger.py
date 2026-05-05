#!/usr/bin/env python3

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from ai_system.recovery_targets import get_recovery_target, recovery_target_action
from ai_system.proposal_gate import validate_recovery_proposal
from ai_system.io_utils import atomic_write_json, atomic_write_text, read_json, read_jsonl
from ai_system.time_utils import get_timezone, now_iso as shared_now_iso, today as shared_today


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = get_timezone(os.environ.get("RECOVERY_TRIGGER_TIMEZONE", "Europe/Paris"))

SNOOZE_COOLDOWN_SECONDS = int(os.environ.get("RECOVERY_TRIGGER_SNOOZE_COOLDOWN_SECONDS", "1800"))
RECENT_RECOVERY_COOLDOWN_SECONDS = int(os.environ.get("RECOVERY_TRIGGER_RECENT_RECOVERY_COOLDOWN_SECONDS", "1800"))

STATE_DIR = AI_DIR / "state"
OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"
EVENTS_ACTIONS_DIR = AI_DIR / "events" / "actions"

SESSION_CURRENT_JSON = STATE_DIR / "session" / "current.json"
ANKI_STATUS_JSON = STATE_DIR / "anki" / "status.json"
DESKTOP_NOW_JSON = STATE_DIR / "desktop" / "now.json"
RECOVERY_CURRENT_JSON = STATE_DIR / "recovery" / "current.json"

CURRENT_NUDGE_JSON = OUTBOX_TO_PHONE_DIR / "current-nudge.json"
CURRENT_NUDGE_MD = OUTBOX_TO_PHONE_DIR / "current-nudge.md"
CURRENT_QUESTION_JSON = OUTBOX_TO_PHONE_DIR / "current-question.json"
CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"
INTERACTION_STATE_JSON = OUTBOX_TO_PHONE_DIR / "interaction-state.json"

TRIGGER_STATE_DIR = STATE_DIR / "recovery-trigger"
LAST_DECISION_JSON = TRIGGER_STATE_DIR / "last-decision.json"
STATUS_MD = TRIGGER_STATE_DIR / "status.md"


ACTIVE_RECOVERY_STATUSES = {"active", "observing"}
TERMINAL_RECOVERY_STATUSES = {"possible_success", "possible_abort", "expired", "cancelled", "completed"}
GOOD_DESKTOP_VERDICTS = {"idle", "no_plan", "off_task", "distracted", "unknown"}


def epoch_now():
    return int(time.time())


def ensure_dirs():
    for path in [OUTBOX_TO_PHONE_DIR, TRIGGER_STATE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def parse_epoch(value):
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


def event_epoch(event):
    if not isinstance(event, dict):
        return 0

    return (
        parse_epoch(event.get("timestamp_epoch"))
        or parse_epoch(event.get("processed_at"))
        or parse_epoch(event.get("timestamp"))
    )


def active_session(session):
    return isinstance(session, dict) and str(session.get("status", "")).strip().lower() == "active"


def active_nudge(nudge, interaction_state):
    if isinstance(nudge, dict) and str(nudge.get("status", "")).strip().lower() == "active":
        return True

    if isinstance(interaction_state, dict) and interaction_state.get("active_nudge"):
        return True

    return False


def active_question(question, interaction_state):
    if isinstance(question, dict) and str(question.get("status", "")).strip().lower() == "active":
        return True

    if isinstance(interaction_state, dict) and interaction_state.get("active_question"):
        return True

    return False


def active_recovery(recovery):
    if not isinstance(recovery, dict):
        return False

    return str(recovery.get("status", "")).strip().lower() in ACTIVE_RECOVERY_STATUSES


def recent_terminal_recovery(recovery):
    if not isinstance(recovery, dict):
        return False, 0

    status = str(recovery.get("status", "")).strip().lower()
    if status not in TERMINAL_RECOVERY_STATUSES:
        return False, 0

    updated_epoch = parse_epoch(recovery.get("updated_at"))
    age = epoch_now() - updated_epoch if updated_epoch else 999999999

    return age < RECENT_RECOVERY_COOLDOWN_SECONDS, age


def anki_due_count(anki):
    if not isinstance(anki, dict):
        return 0

    totals = anki.get("totals", {})
    if not isinstance(totals, dict):
        totals = {}

    try:
        return int(totals.get("due") or totals.get("review_due") or 0)
    except Exception:
        return 0


def desktop_verdict(desktop):
    if not isinstance(desktop, dict):
        return "unknown"

    return str(desktop.get("verdict") or desktop.get("status") or "unknown").strip().lower()


def recent_snooze_from_actions():
    events = read_jsonl(EVENTS_ACTIONS_DIR / f"{shared_today(TIMEZONE)}.jsonl")
    snoozes = []

    for event in events:
        action = str(event.get("action") or event.get("event") or event.get("event_type") or "").strip().lower()
        if action != "snooze_nudge":
            continue
        snoozes.append(event)

    if not snoozes:
        return None, None

    latest = max(snoozes, key=event_epoch)
    age = epoch_now() - event_epoch(latest)

    return latest, age


def make_nudge(now_text, nudge_id):
    target = get_recovery_target("anki")
    return {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "active",
        "nudge_id": nudge_id,
        "created_at": now_text,
        "updated_at": now_text,
        "source": "recovery-trigger",
        "planner_mode": "recovery",
        "urgency": "normal",
        "message": target["nudge_message"],
        "recommended_next_action": target["recommended_next_action"],
        "actions": [
            recovery_target_action("anki"),
            {
                "action": "snooze_nudge",
                "label": "Not now",
                "snooze_minutes": 15
            }
        ]
    }


def make_inactive_question(now_text):
    return {
        "schema_version": "phone_interaction.v1",
        "kind": "question",
        "status": "inactive",
        "updated_at": now_text,
        "source": "recovery-trigger",
        "planner_mode": "recovery",
        "question": "",
        "answer_options": [],
        "free_text_allowed": True,
        "response_action": "answer_question"
    }


def write_phone_outputs(nudge, question, now_text):
    atomic_write_json(CURRENT_NUDGE_JSON, nudge)
    atomic_write_json(CURRENT_QUESTION_JSON, question)

    interaction_state = {
        "schema_version": "phone_interaction_state.v1",
        "updated_at": now_text,
        "source": "recovery-trigger",
        "planner_mode": "recovery",
        "active_nudge": {
            "nudge_id": nudge.get("nudge_id", ""),
            "status": "active",
            "urgency": nudge.get("urgency", "normal"),
            "message": nudge.get("message", ""),
            "recommended_next_action": nudge.get("recommended_next_action", ""),
            "actions": nudge.get("actions", [])
        },
        "active_question": None
    }

    atomic_write_json(INTERACTION_STATE_JSON, interaction_state)

    atomic_write_text(
        CURRENT_NUDGE_MD,
        "\n".join([
            "# Current Nudge",
            "",
            "Status: active",
            f"Nudge ID: {nudge.get('nudge_id', '')}",
            f"Urgency: {nudge.get('urgency', 'normal')}",
            f"Message: {nudge.get('message', '')}",
            f"Recommended next action: {nudge.get('recommended_next_action', '')}",
            f"Updated: {now_text}",
            "Planner mode: recovery",
            "Action: `start_recovery_target`",
            "Snooze action: `snooze_nudge`",
            "",
        ]),
    )

    atomic_write_text(
        CURRENT_QUESTION_MD,
        "\n".join([
            "# Current Question",
            "",
            "Status: inactive",
            "Question: none",
            f"Updated: {now_text}",
            "",
        ]),
    )

    return interaction_state


def build_decision():
    now_text = shared_now_iso(TIMEZONE)
    target = get_recovery_target("anki")
    session = read_json(SESSION_CURRENT_JSON, {})
    anki = read_json(ANKI_STATUS_JSON, {})
    desktop = read_json(DESKTOP_NOW_JSON, {})
    recovery = read_json(RECOVERY_CURRENT_JSON, {})
    nudge = read_json(CURRENT_NUDGE_JSON, {})
    question = read_json(CURRENT_QUESTION_JSON, {})
    interaction_state = read_json(INTERACTION_STATE_JSON, {})

    due = anki_due_count(anki)
    verdict = desktop_verdict(desktop)
    latest_snooze, snooze_age = recent_snooze_from_actions()
    recovery_recent, recovery_age = recent_terminal_recovery(recovery)

    blocked = []
    reason_codes = []
    facts = {
        "has_active_session": active_session(session),
        "has_active_nudge": active_nudge(nudge, interaction_state),
        "has_active_question": active_question(question, interaction_state),
        "has_active_recovery": active_recovery(recovery),
        "recent_terminal_recovery": recovery_recent,
        "recent_terminal_recovery_age_seconds": recovery_age,
        "recent_snooze": latest_snooze is not None and snooze_age is not None and snooze_age < SNOOZE_COOLDOWN_SECONDS,
        "recent_snooze_age_seconds": snooze_age,
        "anki_due": due,
        "desktop_verdict": verdict,
    }

    if facts["has_active_session"]:
        blocked.append("active_session")
    else:
        reason_codes.append("no_active_session")

    if facts["has_active_nudge"]:
        blocked.append("active_nudge")
    else:
        reason_codes.append("no_active_nudge")

    if facts["has_active_question"]:
        blocked.append("active_question")
    else:
        reason_codes.append("no_active_question")

    if facts["has_active_recovery"]:
        blocked.append("active_recovery")
    else:
        reason_codes.append("no_active_recovery")

    if facts["recent_terminal_recovery"]:
        blocked.append("recent_terminal_recovery")
    else:
        reason_codes.append("no_recent_terminal_recovery")

    if facts["recent_snooze"]:
        blocked.append("recent_snooze")
    else:
        reason_codes.append("no_recent_snooze")

    if due > 0:
        reason_codes.append("anki_due")
    else:
        blocked.append("anki_not_due")

    if verdict in GOOD_DESKTOP_VERDICTS:
        reason_codes.append(f"desktop_{verdict}")
    else:
        blocked.append(f"desktop_verdict_{verdict}")

    nudge_id = f"n-recovery-trigger-anki-{epoch_now()}"

    # The deterministic trigger now produces the same proposal shape a future
    # LLM/agent should produce. The proposal gate is the authority boundary.
    candidate_proposal = {
        "schema_version": "agent_recovery_proposal.v1",
        "source": "deterministic-v0",
        "decision": "write_nudge",
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "confidence": 0.72,
        "reason_codes": reason_codes,
        "blocked_reasons": blocked,
        "message": target["nudge_message"],
        "recommended_next_action": target["recommended_next_action"],
        "allowed_actions": [
            "start_recovery_target",
            "snooze_nudge",
        ],
        "cooldown_seconds": SNOOZE_COOLDOWN_SECONDS,
    }

    validation_result = validate_recovery_proposal(candidate_proposal, facts)
    normalized = validation_result.get("normalized") if validation_result.get("ok") else None

    if validation_result.get("ok") and isinstance(normalized, dict) and normalized.get("decision") == "write_nudge":
        decision = "write_nudge"
        confidence = normalized.get("confidence", 0.72)
        final_blocked = []
    else:
        decision = "skip"
        confidence = 0.0
        validation_details = validation_result.get("details", {})
        final_blocked = list(validation_details.get("blocked_reasons") or blocked)

        if validation_result.get("reason") and validation_result.get("reason") not in final_blocked:
            final_blocked.append(str(validation_result.get("reason")))

    return {
        "schema_version": "recovery_trigger_decision.v1",
        "evaluated_at": now_text,
        "timestamp_epoch": epoch_now(),
        "source": "deterministic-v0",
        "decision": decision,
        "target_id": target["target_id"],
        "target_name": target["display_name"],
        "confidence": confidence,
        "reason_codes": reason_codes,
        "blocked_reasons": final_blocked,
        "cooldowns": {
            "snooze_cooldown_seconds": SNOOZE_COOLDOWN_SECONDS,
            "recent_recovery_cooldown_seconds": RECENT_RECOVERY_COOLDOWN_SECONDS,
        },
        "facts": facts,
        "proposal": {
            "schema_version": candidate_proposal["schema_version"],
            "nudge_id": nudge_id,
            "message": candidate_proposal["message"],
            "recommended_next_action": candidate_proposal["recommended_next_action"],
            "actions": candidate_proposal["allowed_actions"],
        },
        "validation_result": validation_result,
        "agent_notes": {
            "future_llm_role": "An LLM agent may later fill agent_recovery_proposal.v1 with richer context, target choice, tone, and confidence.",
            "execution_gate": "Deterministic and future LLM proposals must pass proposal_gate.py before a nudge can be written."
        }
    }


def write_status(decision, wrote_nudge=False):
    atomic_write_json(LAST_DECISION_JSON, decision)

    lines = [
        "# Recovery Trigger Status",
        "",
        f"Updated: {shared_now_iso(TIMEZONE)}",
        f"Decision: `{decision.get('decision', '')}`",
        f"Target: `{decision.get('target_id', '')}`",
        f"Confidence: `{decision.get('confidence', 0)}`",
        f"Wrote nudge: `{str(wrote_nudge).lower()}`",
        "",
        "## Reason codes",
        "",
    ]

    for item in decision.get("reason_codes", []):
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Blocked reasons",
        "",
    ])

    blocked = decision.get("blocked_reasons", [])
    if blocked:
        for item in blocked:
            lines.append(f"- {item}")
    else:
        lines.append("None.")

    lines.extend([
        "",
        "## Facts",
        "",
        "```json",
        json.dumps(decision.get("facts", {}), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Proposal validation",
        "",
        "```json",
        json.dumps(decision.get("validation_result", {}), indent=2, ensure_ascii=False),
        "```",
        "",
    ])

    atomic_write_text(STATUS_MD, "\n".join(lines))


def run_once(dry_run=False):
    ensure_dirs()
    decision = build_decision()

    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "decision": decision,
        }, indent=2, ensure_ascii=False))
        return 0

    wrote_nudge = False

    if decision.get("decision") == "write_nudge":
        now_text = decision["evaluated_at"]
        normalized = decision.get("validation_result", {}).get("normalized", {})
        nudge = dict(normalized.get("phone_nudge", {}))
        nudge["nudge_id"] = decision["proposal"]["nudge_id"]
        nudge["created_at"] = now_text
        nudge["updated_at"] = now_text

        question = make_inactive_question(now_text)
        write_phone_outputs(nudge, question, now_text)
        wrote_nudge = True

    write_status(decision, wrote_nudge=wrote_nudge)

    print(json.dumps({
        "decision": decision.get("decision"),
        "target_id": decision.get("target_id"),
        "wrote_nudge": wrote_nudge,
        "blocked_reasons": decision.get("blocked_reasons", []),
        "reason_codes": decision.get("reason_codes", []),
    }, indent=2, ensure_ascii=False))

    return 1 if wrote_nudge else 0


def parse_args():
    parser = argparse.ArgumentParser(description="Deterministic recovery trigger v0")
    parser.add_argument("--once", action="store_true", help="Evaluate once and write outputs if gates pass")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate once without writing outputs")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.once and not args.dry_run:
        args.dry_run = True

    run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
