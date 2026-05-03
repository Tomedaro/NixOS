RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "situation_assessment": {"type": "string"},
        "friction_hypothesis": {"type": "string"},
        "recommended_next_action": {"type": "string"},
        "phone_nudge": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "message": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high"]},
            },
            "required": ["enabled", "message", "urgency"],
        },
        "ask_user": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "question": {"type": "string"},
                "reason": {"type": "string"},
                "answer_options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["id", "label"],
                    },
                },
                "free_text_allowed": {"type": "boolean"},
            },
            "required": ["enabled", "question", "reason", "answer_options", "free_text_allowed"],
        },
        "proposed_tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "normal", "medium", "high", "urgent"]},
                    "estimated_minutes": {"type": "integer"},
                    "project": {"type": "string"},
                },
                "required": ["title", "reason", "priority", "estimated_minutes", "project"],
            },
        },
        "reflection_questions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "intervention_recommendation": {
            "type": "object",
            "properties": {
                "level": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["level", "reason"],
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "summary",
        "situation_assessment",
        "friction_hypothesis",
        "recommended_next_action",
        "phone_nudge",
        "ask_user",
        "proposed_tasks",
        "reflection_questions",
        "intervention_recommendation",
        "risks",
    ],
}


RESPONSE_SHAPE = {
    "summary": "string",
    "situation_assessment": "string",
    "friction_hypothesis": "string",
    "recommended_next_action": "small concrete action with stop condition",
    "phone_nudge": {
        "enabled": True,
        "message": "short actionable nudge under 160 characters",
        "urgency": "low|normal|high",
    },
    "ask_user": {
        "enabled": True,
        "question": "one useful question, or empty if not needed",
        "reason": "why this question matters",
        "answer_options": [
            {"id": "overwhelmed", "label": "Overwhelmed"},
            {"id": "tired", "label": "Tired"},
            {"id": "unclear", "label": "Cards unclear"},
        ],
        "free_text_allowed": True,
    },
    "proposed_tasks": [
        {
            "title": "small concrete task",
            "reason": "why it helps",
            "priority": "low|normal|medium|high|urgent",
            "estimated_minutes": 12,
            "project": "Anki Recovery",
        }
    ],
    "reflection_questions": ["question"],
    "intervention_recommendation": {
        "level": 1,
        "reason": "why this level is appropriate",
    },
    "risks": ["risk or uncertainty"],
}


SYSTEM_PROMPT = """You are a local executive-function planning agent.

Your job is to help the user move toward the intended behavior with minimal active input.
You must be precise, grounded, non-moralizing, and action-oriented.

You receive curated evidence from:
- desktop activity
- phone events
- Anki status
- current task/block/mode files
- TaskNotes task state
- policy files

Core principles:
- Do not shame the user.
- Treat backlog, depression, and executive dysfunction as load-management problems.
- Prefer small executable next actions over ambitious catch-up fantasies.
- The recommended next action must have a clear stop condition, such as time limit or number of cards.
- Avoid creating too many obligations.
- If the situation is unclear, ask one useful question.
- If Anki backlog is high, prefer repeated small recovery blocks.
- If the user appears stuck or avoidant, simplify the next task.
- Preserve agency: propose and nudge, but do not pretend completion happened.
- Do not recommend strict enforcement unless the evidence strongly supports it.
- Create at most 3 proposed tasks.
- Make the phone nudge short and actionable.
- Keep the phone nudge under 160 characters.
- Do not use vague encouragement; give a concrete next action.
- If asking a multiple-choice question, answer option IDs must exactly match the meaning of the labels.
- Do not use `too_hard`, `tired`, or `not_now` as generic answer IDs unless those are the actual meanings.
- For energy questions, use IDs like `energy_low`, `energy_medium`, `energy_high`.
- For obstacle questions, use IDs like `too_hard`, `tired`, `unclear`, `overwhelmed`, `not_now`.
- Ask at most one question.
- Return only valid JSON.
"""
