import re

from ai_planner.io_utils import clamp_text, safe_str


def fallback_result(reason, raw_content="", error_kind="planner_error"):
    return {
        "summary": "The planner could not produce a reliable plan.",
        "situation_assessment": "Planner failed before completing reasoning.",
        "friction_hypothesis": "Unknown because planner execution failed.",
        "recommended_next_action": "Inspect the planner error and rerun after fixing it.",
        "phone_nudge": {
            "enabled": False,
            "message": "",
            "urgency": "low",
        },
        "ask_user": {
            "enabled": True,
            "question": "The local planner failed. Inspect logs now?",
            "reason": str(reason),
            "answer_options": [
                {"id": "inspect", "label": "Inspect"},
                {"id": "later", "label": "Later"},
                {"id": "ignore", "label": "Ignore"},
            ],
            "free_text_allowed": True,
        },
        "proposed_tasks": [],
        "reflection_questions": [],
        "intervention_recommendation": {
            "level": 0,
            "reason": "No intervention recommended because planner failed.",
        },
        "risks": [
            f"{error_kind}: {reason}",
            clamp_text(raw_content, 1500),
        ],
    }


def normalize_urgency(value):
    value = safe_str(value, "normal").lower()
    if value not in {"low", "normal", "high"}:
        return "normal"
    return value


def normalize_priority(value):
    value = safe_str(value, "normal").lower()
    if value not in {"low", "normal", "medium", "high", "urgent"}:
        return "normal"
    return value


def normalize_answer_id(value):
    value = safe_str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = value.strip("_")
    return value or "other"


def normalize_result(result):
    if not isinstance(result, dict):
        result = fallback_result("Model response was not a JSON object.")

    normalized = {
        "summary": safe_str(result.get("summary"), "No summary provided."),
        "situation_assessment": safe_str(result.get("situation_assessment"), ""),
        "friction_hypothesis": safe_str(result.get("friction_hypothesis"), ""),
        "recommended_next_action": safe_str(result.get("recommended_next_action"), ""),
        "phone_nudge": {},
        "ask_user": {},
        "proposed_tasks": [],
        "reflection_questions": [],
        "intervention_recommendation": {},
        "risks": [],
    }

    nudge = result.get("phone_nudge", {})
    if not isinstance(nudge, dict):
        nudge = {}

    normalized["phone_nudge"] = {
        "enabled": bool(nudge.get("enabled", False)),
        "message": clamp_text(nudge.get("message", ""), 220),
        "urgency": normalize_urgency(nudge.get("urgency", "normal")),
    }

    ask = result.get("ask_user", {})
    if not isinstance(ask, dict):
        ask = {}

    options = []
    for opt in ask.get("answer_options", []) or []:
        if not isinstance(opt, dict):
            continue
        opt_id = normalize_answer_id(opt.get("id"))
        label = clamp_text(opt.get("label", opt_id), 40)
        if opt_id and label:
            options.append({"id": opt_id, "label": label})

    if not options:
        options = [
            {"id": "overwhelmed", "label": "Overwhelmed"},
            {"id": "tired", "label": "Tired"},
            {"id": "unclear", "label": "Cards unclear"},
        ]

    normalized["ask_user"] = {
        "enabled": bool(ask.get("enabled", False)),
        "question": clamp_text(ask.get("question", ""), 240),
        "reason": clamp_text(ask.get("reason", ""), 320),
        "answer_options": options[:3],
        "free_text_allowed": bool(ask.get("free_text_allowed", True)),
    }

    question_l = normalized["ask_user"]["question"].lower()
    if "scale" in question_l or "1 to 10" in question_l or "1-10" in question_l:
        normalized["ask_user"]["answer_options"] = [
            {"id": "energy_low", "label": "Low energy"},
            {"id": "energy_medium", "label": "Medium energy"},
            {"id": "energy_high", "label": "High energy"},
        ]

    if "energy" in question_l and any(
        opt["id"] in {"too_hard", "not_now"} for opt in normalized["ask_user"]["answer_options"]
    ):
        normalized["ask_user"]["answer_options"] = [
            {"id": "energy_low", "label": "Low energy"},
            {"id": "energy_medium", "label": "Medium energy"},
            {"id": "energy_high", "label": "High energy"},
        ]

    for task in result.get("proposed_tasks", []) or []:
        if not isinstance(task, dict):
            continue

        title = clamp_text(task.get("title", ""), 120)
        if not title:
            continue

        try:
            estimated = int(task.get("estimated_minutes", 10))
        except Exception:
            estimated = 10

        estimated = max(1, min(estimated, 120))

        normalized["proposed_tasks"].append({
            "title": title,
            "reason": clamp_text(task.get("reason", ""), 500),
            "priority": normalize_priority(task.get("priority", "normal")),
            "estimated_minutes": estimated,
            "project": clamp_text(task.get("project", "General"), 80),
        })

        if len(normalized["proposed_tasks"]) >= 3:
            break

    for question in result.get("reflection_questions", []) or []:
        question = clamp_text(question, 240)
        if question:
            normalized["reflection_questions"].append(question)
        if len(normalized["reflection_questions"]) >= 5:
            break

    intervention = result.get("intervention_recommendation", {})
    if not isinstance(intervention, dict):
        intervention = {}

    try:
        level = int(intervention.get("level", 1))
    except Exception:
        level = 1

    normalized["intervention_recommendation"] = {
        "level": max(0, min(level, 6)),
        "reason": clamp_text(intervention.get("reason", ""), 500),
    }

    for risk in result.get("risks", []) or []:
        risk = clamp_text(risk, 300)
        if risk:
            normalized["risks"].append(risk)
        if len(normalized["risks"]) >= 8:
            break

    return normalized
