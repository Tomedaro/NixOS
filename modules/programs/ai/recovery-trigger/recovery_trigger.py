#!/usr/bin/env python3

import argparse
import json
import os
import time
from pathlib import Path
from ai_system.recovery_targets import get_recovery_target
from ai_system.proposal_gate import validate_recovery_proposal
from ai_system.agent_context import build_agent_context
from ai_system.recovery_proposals import build_deterministic_recovery_proposal, build_recovery_reasoning
from ai_system.io_utils import atomic_write_json, atomic_write_text
from ai_system.time_utils import get_timezone, now_iso as shared_now_iso


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = get_timezone(os.environ.get("RECOVERY_TRIGGER_TIMEZONE", "Europe/Paris"))

SNOOZE_COOLDOWN_SECONDS = int(os.environ.get("RECOVERY_TRIGGER_SNOOZE_COOLDOWN_SECONDS", "1800"))
RECENT_RECOVERY_COOLDOWN_SECONDS = int(os.environ.get("RECOVERY_TRIGGER_RECENT_RECOVERY_COOLDOWN_SECONDS", "1800"))

STATE_DIR = AI_DIR / "state"
OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"


CURRENT_NUDGE_JSON = OUTBOX_TO_PHONE_DIR / "current-nudge.json"
CURRENT_NUDGE_MD = OUTBOX_TO_PHONE_DIR / "current-nudge.md"
CURRENT_QUESTION_JSON = OUTBOX_TO_PHONE_DIR / "current-question.json"
CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"
INTERACTION_STATE_JSON = OUTBOX_TO_PHONE_DIR / "interaction-state.json"

TRIGGER_STATE_DIR = STATE_DIR / "recovery-trigger"
LAST_DECISION_JSON = TRIGGER_STATE_DIR / "last-decision.json"
STATUS_MD = TRIGGER_STATE_DIR / "status.md"


def epoch_now():
    return int(time.time())


def ensure_dirs():
    for path in [OUTBOX_TO_PHONE_DIR, TRIGGER_STATE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


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
    now_epoch = epoch_now()
    now_text = shared_now_iso(TIMEZONE)
    target = get_recovery_target("anki")

    # Use the shared read-only agent context as the fact source for both the
    # deterministic trigger and future LLM/agent proposal producers. This keeps
    # proposal inputs aligned while preserving the authority boundary:
    #
    #   agent_context.py reads facts
    #   recovery-trigger proposes
    #   proposal_gate.py validates
    #   action-bridge executes only after validated/user-triggered actions
    #
    # build_agent_context is intentionally non-executing and does not write
    # phone nudges or action files.
    agent_context = build_agent_context(AI_DIR, now_epoch=now_epoch)
    facts = agent_context.get("derived_facts", {})
    if not isinstance(facts, dict):
        facts = {}

    reasoning = build_recovery_reasoning(facts, target_id="anki")
    reason_codes = list(reasoning.get("reason_codes", []))
    blocked = list(reasoning.get("blocked_reasons", []))

    nudge_id = f"n-recovery-trigger-anki-{epoch_now()}"

    # The deterministic trigger now produces the same proposal shape a future
    # LLM/agent should produce. The proposal gate is the authority boundary.
    candidate_proposal = build_deterministic_recovery_proposal(
        facts,
        target_id=target["target_id"],
        source="deterministic-v0",
        cooldown_seconds=SNOOZE_COOLDOWN_SECONDS,
    )

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
        "agent_context": {
            "schema_version": agent_context.get("schema_version", ""),
            "generated_at": agent_context.get("generated_at", ""),
            "source": "agent_context.py",
        },
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
