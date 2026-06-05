"""Validate untrusted LLM output into safe Obsidian proposals.

This module is the LLM boundary. It does not call a model, execute commands,
edit Obsidian, write phone nudges, or enqueue live actions.

The intended flow is:

agent_context + pending Obsidian intent
    -> bounded prompt package for a local LLM
    -> untrusted JSON candidate
    -> strict validation/sanitization
    -> obsidian_proposal.v1
    -> existing approval/draft bridges
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_system.obsidian_contracts import (
    DIRECT_EXECUTION_FIELDS,
    PROPOSAL_EXECUTION_POLICY,
    as_dict,
    bounded_line,
    bounded_list,
    bounded_text,
    contains_direct_execution as contract_contains_direct_execution,
    read_json_object,
    utc_now,
)

MAX_TEXT = 2000
MAX_MESSAGE = 4000
MAX_LABEL = 220
MAX_ID = 160
MAX_ACTIONS = 6
MAX_LIST_ITEMS = 12

ALLOWED_PROPOSAL_KINDS = {
    "next_goal_step",
    "next_task_step",
    "clarify_or_plan",
    "review_action_request",
}

ALLOWED_ACTION_TYPES = {
    "suggest_next_step",
    "draft_task",
    "select_existing_task",
    "ask_clarifying_question",
    "draft_action_proposal",
}

NOISY_CONTEXT_KEY_MARKERS = (
    "raw",
    "payload",
    "debug",
    "trace",
    "screenshot",
    "transcript",
    "html",
    "full_text",
    "content",
)


SAFE_CONTEXT_FACTS = {
    "interaction",
    "obsidian",
    "obsidian_intent",
    "activitywatch",
    "anki",
    "recovery",
    "interventions",
}


def read_json(path: Path) -> dict[str, Any]:
    return read_json_object(
        path,
        object_error=f"{path} must contain a JSON object",
    )


def contains_direct_execution(value: Any) -> list[str]:
    return contract_contains_direct_execution(
        value,
        max_items=MAX_LIST_ITEMS,
        ignore_empty_dict=True,
    )


def is_noisy_context_key(key: str) -> bool:
    key_lower = key.lower()

    if key_lower in {
        "raw",
        "raw_events",
        "events",
        "full_text",
        "content",
        "large_payload",
    }:
        return True

    return any(marker in key_lower for marker in NOISY_CONTEXT_KEY_MARKERS)


def remove_unsafe_large_fields(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)

            if key_text in DIRECT_EXECUTION_FIELDS:
                continue

            if is_noisy_context_key(key_text):
                continue

            out[key_text] = remove_unsafe_large_fields(child)

        return out

    if isinstance(value, list):
        return [remove_unsafe_large_fields(item) for item in value[:MAX_LIST_ITEMS]]

    if isinstance(value, str):
        return bounded_text(value, max_len=MAX_TEXT)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return bounded_text(value, max_len=MAX_TEXT)


def compact_intent(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "llm_intent_ref.v1",
        "intent_id": bounded_line(
            intent.get("intent_id") or "unknown-intent", max_len=MAX_ID
        ),
        "kind": bounded_line(intent.get("kind"), max_len=80),
        "source": bounded_line(intent.get("source") or "obsidian", max_len=80),
        "surface": bounded_line(intent.get("surface") or "obsidian", max_len=80),
        "mode": bounded_line(intent.get("mode"), max_len=80),
        "note_path": bounded_line(intent.get("note_path"), max_len=MAX_ID),
        "message": bounded_text(
            intent.get("message") or intent.get("message_preview"),
            max_len=MAX_MESSAGE,
        ),
        "requested_action": bounded_line(
            intent.get("requested_action"), max_len=MAX_ID
        ),
        "goal_ids": bounded_list(intent.get("goal_ids")),
        "task_ids": bounded_list(intent.get("task_ids")),
    }


def compact_context_for_llm(context: dict[str, Any]) -> dict[str, Any]:
    hub = as_dict(context.get("context_hub"))
    facts = as_dict(hub.get("facts"))

    compact_facts: dict[str, Any] = {}
    for name in sorted(SAFE_CONTEXT_FACTS):
        compact_facts[name] = remove_unsafe_large_fields(as_dict(facts.get(name)))

    return {
        "schema_version": "llm_context_refs.v1",
        "generated_at": bounded_line(context.get("generated_at"), max_len=80),
        "timestamp_epoch": context.get("timestamp_epoch") or 0,
        "facts": compact_facts,
        "warnings": remove_unsafe_large_fields(hub.get("warnings") or []),
    }


def expected_output_contract() -> dict[str, Any]:
    return {
        "schema_version": "obsidian_proposal.v1",
        "proposal_kind": sorted(ALLOWED_PROPOSAL_KINDS),
        "summary": "short human-readable summary",
        "message_markdown": "mentor-style response for Obsidian",
        "goal_ids": ["optional-goal-id"],
        "suggested_actions": [
            {
                "type": sorted(ALLOWED_ACTION_TYPES),
                "label": "button/action label",
                "requires_approval": True,
                "title": "optional task title",
                "body": "optional task body",
                "priority": "low|normal|high",
                "energy": "low|medium|high|unknown",
                "estimated_minutes": 15,
            }
        ],
        "forbidden": sorted(DIRECT_EXECUTION_FIELDS),
    }


def build_llm_prompt_package(
    intent: dict[str, Any],
    context: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()

    package = {
        "schema_version": "llm_prompt_package.v1",
        "created_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "purpose": "Build one safe Obsidian proposal from the user intent and local context.",
        "system_contract": (
            "You are a local-first planning assistant. Return only JSON matching "
            "obsidian_proposal.v1. You may propose, draft, ask, or suggest. You must "
            "not execute commands, launch apps, edit files, write live queues, or "
            "include direct execution fields."
        ),
        "safety_rules": [
            "Return JSON only.",
            "Do not include shell commands or app launch instructions.",
            "Do not claim that anything has been executed.",
            "Prefer one tiny next action over a large plan.",
            "Use existing goals/tasks from context when available.",
            "Any task creation must be a draft requiring approval.",
        ],
        "intent": compact_intent(intent),
        "context": compact_context_for_llm(context),
        "expected_output": expected_output_contract(),
        "max_output_chars": 6000,
    }
    package = _attach_tasknotes_read_context_to_prompt_package(package, context)
    return package


def infer_kind(candidate: dict[str, Any], intent: dict[str, Any]) -> str:
    kind = bounded_line(candidate.get("proposal_kind"), max_len=80)
    if kind in ALLOWED_PROPOSAL_KINDS:
        return kind

    if intent.get("requested_action") or intent.get("kind") == "action_request":
        return "review_action_request"

    if intent.get("goal_ids"):
        return "next_goal_step"

    return "clarify_or_plan"


def sanitize_action(action: dict[str, Any]) -> dict[str, Any]:
    action_type = bounded_line(action.get("type"), max_len=80)
    if action_type not in ALLOWED_ACTION_TYPES:
        action_type = "ask_clarifying_question"

    sanitized = {
        "type": action_type,
        "label": bounded_line(
            action.get("label") or action.get("title") or "Review proposal"
        ),
        "requires_approval": bool(
            action.get(
                "requires_approval",
                action_type in {"draft_task", "draft_action_proposal"},
            )
        ),
    }

    for key in (
        "title",
        "body",
        "priority",
        "energy",
        "estimated_minutes",
        "goal_id",
        "project_id",
        "area",
    ):
        if key in action and action.get(key) not in (None, "", [], {}):
            if key == "estimated_minutes":
                try:
                    sanitized[key] = max(1, min(240, int(action.get(key))))
                except Exception:
                    sanitized[key] = 15
            elif key == "body":
                sanitized[key] = bounded_text(action.get(key), max_len=MAX_MESSAGE)
            else:
                sanitized[key] = bounded_line(action.get(key), max_len=MAX_LABEL)

    tags = bounded_list(action.get("tags"))
    if tags:
        sanitized["tags"] = tags

    return sanitized


def proposal_markdown(proposal: dict[str, Any]) -> str:
    lines = [
        "# AI Proposal",
        "",
        f"Status: `{proposal['status']}`",
        f"Kind: `{proposal['proposal_kind']}`",
        f"Intent: `{proposal['intent_id']}`",
        f"Source: `{proposal['source']}`",
        "",
        "## Message",
        "",
        proposal["message_markdown"],
        "",
        "## Suggested actions",
        "",
    ]

    for action in proposal.get("suggested_actions", []):
        lines.append(f"- `{action.get('type', 'unknown')}` — {action.get('label', '')}")

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This proposal came through the LLM proposal contract.",
            "- It does not execute anything.",
            "- Approval and downstream bridges are required for any write/action.",
            "",
        ]
    )

    return "\n".join(lines)


def sanitize_llm_obsidian_proposal(
    candidate: dict[str, Any],
    intent: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()

    direct_fields = contains_direct_execution(candidate)
    if direct_fields:
        raise ValueError(
            "LLM proposal contains direct execution fields: "
            + ", ".join(direct_fields[:8])
        )

    intent_ref = compact_intent(intent)
    intent_id = intent_ref["intent_id"]
    proposal_kind = infer_kind(candidate, intent)

    actions_raw = candidate.get("suggested_actions")
    actions: list[dict[str, Any]] = []
    if isinstance(actions_raw, list):
        for action in actions_raw[:MAX_ACTIONS]:
            if isinstance(action, dict):
                actions.append(sanitize_action(action))

    if not actions:
        actions.append(
            {
                "type": "ask_clarifying_question",
                "label": "Ask for the next goal or constraint",
                "requires_approval": False,
            }
        )

    goal_ids = bounded_list(candidate.get("goal_ids")) or intent_ref["goal_ids"]

    summary = bounded_line(
        candidate.get("summary") or candidate.get("title") or "Review next step"
    )
    message_markdown = bounded_text(
        candidate.get("message_markdown")
        or candidate.get("message")
        or candidate.get("response")
        or summary,
        max_len=MAX_MESSAGE,
    )

    proposal = {
        "schema_version": "obsidian_proposal.v1",
        "proposal_id": bounded_line(
            candidate.get("proposal_id") or f"proposal-{intent_id}",
            max_len=MAX_ID,
        ),
        "intent_id": intent_id,
        "status": "proposed",
        "source": "llm-proposal-contract",
        "surface": "obsidian",
        "created_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "proposal_kind": proposal_kind,
        "summary": summary,
        "message_markdown": message_markdown,
        "note_path": intent_ref["note_path"],
        "goal_ids": goal_ids,
        "task_ids": intent_ref["task_ids"],
        "suggested_actions": actions,
        "execution_policy": PROPOSAL_EXECUTION_POLICY,
        "context_refs": (
            compact_context_for_llm(context)
            if isinstance(context, dict)
            else {"schema_version": "llm_context_refs.v1", "facts": {}}
        ),
        "llm_contract": {
            "schema_version": "llm_contract_ref.v1",
            "validated": True,
            "direct_execution_fields_rejected": sorted(DIRECT_EXECUTION_FIELDS),
        },
    }
    proposal["markdown"] = proposal_markdown(proposal)
    return proposal


def validate_llm_obsidian_proposal(
    candidate: dict[str, Any],
    intent: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        proposal = sanitize_llm_obsidian_proposal(candidate, intent, context)
    except Exception as exc:
        return {
            "schema_version": "llm_proposal_validation_result.v1",
            "valid": False,
            "error": str(exc),
            "proposal": {},
        }

    return {
        "schema_version": "llm_proposal_validation_result.v1",
        "valid": True,
        "error": "",
        "proposal": proposal,
    }


def fallback_proposal_from_intent(
    intent: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    reason: str = "llm_unavailable_or_invalid",
) -> dict[str, Any]:
    intent_ref = compact_intent(intent)
    message = intent_ref["message"]
    goal_ids = intent_ref["goal_ids"]

    if intent_ref["requested_action"]:
        candidate = {
            "proposal_kind": "review_action_request",
            "summary": f"Review requested action: {intent_ref['requested_action']}",
            "message_markdown": (
                f"You asked for `{intent_ref['requested_action']}`. I can prepare "
                "a safe proposal, but execution must stay behind explicit approval."
            ),
            "goal_ids": goal_ids,
            "suggested_actions": [
                {
                    "type": "draft_action_proposal",
                    "label": "Draft a safe action proposal",
                    "requires_approval": True,
                }
            ],
        }
    elif goal_ids:
        goal_text = ", ".join(goal_ids)
        candidate = {
            "proposal_kind": "next_goal_step",
            "summary": f"Choose one tiny next step for {goal_text}",
            "message_markdown": (
                f"Fallback planner: pick one 5-15 minute action for `{goal_text}`.\n\n"
                f"Your message: {message or 'No message provided.'}"
            ),
            "goal_ids": goal_ids,
            "suggested_actions": [
                {
                    "type": "draft_task",
                    "label": "Draft one tiny task for this goal",
                    "requires_approval": True,
                    "estimated_minutes": 15,
                    "goal_id": goal_ids[0],
                }
            ],
        }
    else:
        candidate = {
            "proposal_kind": "clarify_or_plan",
            "summary": "Clarify the goal and choose a tiny next step",
            "message_markdown": (
                "Fallback planner: I need a goal, task, or desired mode to choose "
                "the most useful next step."
            ),
            "suggested_actions": [
                {
                    "type": "ask_clarifying_question",
                    "label": "Ask which goal to work on",
                    "requires_approval": False,
                }
            ],
        }

    proposal = sanitize_llm_obsidian_proposal(candidate, intent, context)
    proposal["source"] = "llm-proposal-contract-fallback"
    proposal["fallback_reason"] = reason
    proposal["markdown"] = proposal_markdown(proposal)
    return proposal


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(stripped[start : end + 1])
        if isinstance(data, dict):
            return data

    raise ValueError("could not parse JSON object from LLM output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/validate LLM Obsidian proposal contracts"
    )
    parser.add_argument("--intent", required=True, help="Intent JSON file")
    parser.add_argument("--context", help="Agent context JSON file")
    parser.add_argument("--llm-output", help="Untrusted LLM output text/JSON file")
    parser.add_argument("--prompt-package", action="store_true")
    parser.add_argument("--fallback", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    intent = read_json(Path(args.intent))
    context = read_json(Path(args.context)) if args.context else {}

    if args.prompt_package:
        result = build_llm_prompt_package(intent, context)
    elif args.fallback:
        result = fallback_proposal_from_intent(intent, context)
    else:
        if not args.llm_output:
            raise SystemExit(
                "--llm-output is required unless --prompt-package or --fallback is used"
            )
        candidate = parse_json_object(Path(args.llm_output).read_text(encoding="utf-8"))
        result = validate_llm_obsidian_proposal(candidate, intent, context)

    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0



def _prompt_tasknotes_as_dict(value):
    return value if isinstance(value, dict) else {}


def _prompt_tasknotes_as_list(value):
    return value if isinstance(value, list) else []


def _prompt_tasknotes_find_provider(context_hub):
    hub = _prompt_tasknotes_as_dict(context_hub)

    facts = _prompt_tasknotes_as_dict(hub.get("facts"))
    fact_entry = _prompt_tasknotes_as_dict(facts.get("tasknotes.read_context"))

    provider_entry = {}
    for provider in _prompt_tasknotes_as_list(hub.get("providers")):
        provider = _prompt_tasknotes_as_dict(provider)
        if provider.get("name") == "tasknotes.read_context":
            provider_entry = provider
            break

    if not fact_entry and provider_entry:
        fact_entry = _prompt_tasknotes_as_dict(provider_entry.get("facts"))

    if not fact_entry:
        return {}

    return {
        "provider": provider_entry,
        "facts": fact_entry,
    }


def _compact_tasknotes_read_context_for_prompt(context):
    provider_bundle = _prompt_tasknotes_find_provider(
        _prompt_tasknotes_as_dict(context).get("context_hub")
    )
    if not provider_bundle:
        return {}

    provider = _prompt_tasknotes_as_dict(provider_bundle.get("provider"))
    facts = _prompt_tasknotes_as_dict(provider_bundle.get("facts"))

    source = _prompt_tasknotes_as_dict(facts.get("source"))
    provenance = _prompt_tasknotes_as_dict(facts.get("provenance"))
    omitted = _prompt_tasknotes_as_dict(facts.get("omitted"))
    limits = _prompt_tasknotes_as_dict(facts.get("limits"))

    required_action_capabilities = facts.get("required_action_capabilities")
    if not isinstance(required_action_capabilities, list):
        required_action_capabilities = []

    warnings = provider.get("warnings")
    if not isinstance(warnings, list):
        warnings = facts.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    source_paths = provider.get("source_paths")
    if not isinstance(source_paths, list):
        source_paths = []

    item_paths = provenance.get("item_paths")
    if not isinstance(item_paths, list):
        item_paths = []

    compact = {
        "module": "tasknotes.read_context",
        "status": str(facts.get("status") or ""),
        "available": bool(facts.get("available", provider.get("available", False))),
        "freshness": str(provider.get("freshness") or ""),
        "generated_at_epoch": facts.get("generated_at_epoch"),
        "limits": {
            key: limits[key]
            for key in ("file_limit", "bytes_per_file", "total_bytes")
            if key in limits
        },
        "item_count": facts.get("item_count"),
        "truncated": bool(facts.get("truncated", False)),
        "omitted": {
            key: omitted[key]
            for key in ("over_limit", "unreadable", "bytes")
            if key in omitted
        },
        "warnings": [str(value) for value in warnings[:8]],
        "source": {
            key: source[key]
            for key in ("kind", "root", "tasks_root")
            if key in source
        },
        "source_paths": [str(value) for value in source_paths[:4]],
        "provenance": {
            "item_paths": [str(value) for value in item_paths[:12]],
        },
        "may_mutate_tasknotes": bool(facts.get("may_mutate_tasknotes", False)),
        "required_action_capabilities": [
            str(value) for value in required_action_capabilities
        ],
    }

    return compact


def _attach_tasknotes_read_context_to_prompt_package(package, context):
    tasknotes = _compact_tasknotes_read_context_for_prompt(context)
    if not tasknotes or not isinstance(package, dict):
        return package

    updated = dict(package)
    prompt_context = updated.get("context")
    prompt_context = dict(prompt_context) if isinstance(prompt_context, dict) else {}
    prompt_context["tasknotes_read_context"] = tasknotes
    updated["context"] = prompt_context
    return updated


if __name__ == "__main__":
    raise SystemExit(main())
