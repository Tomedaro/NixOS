import time

from ai_planner.io_utils import (
    atomic_write_json,
    atomic_write_text,
    now,
    now_iso,
    read_json,
    read_text,
    today,
)
from ai_system.interaction_lifecycle import clear_reason_for_active_nudge


def write_context_files(config, context, markdown):
    atomic_write_json(config.context_dir / "today.json", context)
    atomic_write_text(config.context_dir / "today.md", markdown)


def report_path_for_mode(config):
    mode = getattr(config, "planner_mode", "block-plan")

    if mode == "help-now":
        stamp = now(config).strftime("%Y-%m-%d-%H%M%S")
        return config.reports_help_now_dir / f"{stamp}.md"

    return config.reports_daily_dir / f"{today(config)}.md"


def write_markdown_outputs(config, result):
    mode = getattr(config, "planner_mode", "block-plan")
    report_path = report_path_for_mode(config)

    report = []
    report.append(f"# LLM Planner Report - {today(config)}")
    report.append("")
    report.append(f"Mode: `{mode}`")
    report.append(f"Generated at: {result.get('_metadata', {}).get('generated_at', now_iso(config))}")
    report.append(f"Model: `{result.get('_metadata', {}).get('model', config.ollama_model)}`")
    report.append("")
    report.append("## Summary")
    report.append("")
    report.append(result.get("summary", ""))
    report.append("")
    report.append("## Situation assessment")
    report.append("")
    report.append(result.get("situation_assessment", ""))
    report.append("")
    report.append("## Friction hypothesis")
    report.append("")
    report.append(result.get("friction_hypothesis", ""))
    report.append("")
    report.append("## Recommended next action")
    report.append("")
    report.append(result.get("recommended_next_action", ""))
    report.append("")
    report.append("## Phone nudge")
    report.append("")

    nudge = result.get("phone_nudge", {})
    report.append(f"Enabled: `{str(nudge.get('enabled', False)).lower()}`")
    report.append(f"Urgency: `{nudge.get('urgency', 'normal')}`")
    report.append(f"Message: {nudge.get('message', '')}")
    report.append("")
    report.append("## Proposed tasks")
    report.append("")

    tasks = result.get("proposed_tasks", [])
    if tasks:
        for task in tasks:
            report.append(f"- [ ] **{task.get('title', '')}**")
            report.append(f"  - Priority: {task.get('priority', '')}")
            report.append(f"  - Estimate: {task.get('estimated_minutes', '')} min")
            report.append(f"  - Project: {task.get('project', '')}")
            report.append(f"  - Reason: {task.get('reason', '')}")
    else:
        report.append("No proposed tasks.")

    report.append("")
    report.append("## Reflection questions")
    report.append("")

    questions = result.get("reflection_questions", [])
    if questions:
        for question in questions:
            report.append(f"- {question}")
    else:
        report.append("No reflection questions.")

    report.append("")
    report.append("## Question to ask user")
    report.append("")

    ask = result.get("ask_user", {})
    if ask.get("enabled"):
        report.append(f"Question: {ask.get('question', '')}")
        report.append("")
        report.append(f"Reason: {ask.get('reason', '')}")
        report.append("")
        report.append("Options:")
        for opt in ask.get("answer_options", []):
            report.append(f"- `{opt.get('id', '')}` — {opt.get('label', '')}")
    else:
        report.append("No immediate question recommended.")

    report.append("")
    report.append("## Intervention recommendation")
    report.append("")

    intervention = result.get("intervention_recommendation", {})
    report.append(f"Level: `{intervention.get('level', 1)}`")
    report.append(f"Reason: {intervention.get('reason', '')}")
    report.append("")
    report.append("## Risks / uncertainties")
    report.append("")

    risks = result.get("risks", [])
    if risks:
        for risk in risks:
            report.append(f"- {risk}")
    else:
        report.append("No major risks reported.")

    atomic_write_text(report_path, "\n".join(report))

    if mode != "help-now":
        proposed = []
        proposed.append(f"# Proposed Tasks - {today(config)}")
        proposed.append("")
        proposed.append("> These are proposals from the local planner. Review before turning them into real TaskNotes.")
        proposed.append("")

        for task in result.get("proposed_tasks", []):
            proposed.append(f"## {task.get('title', '')}")
            proposed.append("")
            proposed.append(f"Priority: {task.get('priority', '')}")
            proposed.append(f"Estimate: {task.get('estimated_minutes', '')} min")
            proposed.append(f"Project: {task.get('project', '')}")
            proposed.append("")
            proposed.append(f"Reason: {task.get('reason', '')}")
            proposed.append("")

        atomic_write_text(config.proposed_tasks_dir / f"{today(config)}.md", "\n".join(proposed))

    last_md = []
    last_md.append("# Last LLM Planner Output")
    last_md.append("")
    last_md.append(f"Mode: `{mode}`")
    last_md.append(f"Generated at: {result.get('_metadata', {}).get('generated_at', now_iso(config))}")
    last_md.append(f"Model: `{result.get('_metadata', {}).get('model', config.ollama_model)}`")
    last_md.append("")
    last_md.append("## Summary")
    last_md.append("")
    last_md.append(result.get("summary", ""))
    last_md.append("")
    last_md.append("## Recommended next action")
    last_md.append("")
    last_md.append(result.get("recommended_next_action", ""))
    last_md.append("")

    atomic_write_text(config.state_llm_dir / "last-output.md", "\n".join(last_md))


def _planner_mode(config):
    return getattr(config, "planner_mode", "block-plan")


def _new_interaction_id(prefix, config):
    return f"{prefix}-{today(config)}-{int(time.time())}"


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "active"}


def _as_options(value):
    if not isinstance(value, list):
        return []

    options = []
    for item in value:
        if not isinstance(item, dict):
            continue

        option_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()

        if not option_id and not label:
            continue

        options.append({
            "id": option_id or label.lower().replace(" ", "_"),
            "label": label or option_id,
        })

    return options


def _existing_active_question(config):
    existing = read_json(config.outbox_to_phone_dir / "current-question.json", {})
    if isinstance(existing, dict) and existing.get("status") == "active":
        return existing

    pending = read_json(config.state_llm_dir / "pending-question.json", {})
    if isinstance(pending, dict) and pending:
        return pending

    return {}


def _existing_active_nudge(config):
    existing = read_json(config.outbox_to_phone_dir / "current-nudge.json", {})
    if not isinstance(existing, dict):
        return {}

    if existing.get("status") != "active":
        return {}

    clear_reason = clear_reason_for_active_nudge({"active_nudge": existing})
    if clear_reason:
        print(f"expired active nudge ignored: {clear_reason}")
        return {}

    return existing


def current_question_is_active(config):
    question_json = read_json(config.outbox_to_phone_dir / "current-question.json", {})
    if isinstance(question_json, dict) and question_json.get("status") == "active":
        return True

    text = read_text(config.outbox_to_phone_dir / "current-question.md", "")
    return "Status: active" in text


def existing_pending_matches(config, question, reason):
    existing = read_json(config.state_llm_dir / "pending-question.json", {})
    if not isinstance(existing, dict) or not existing:
        return None

    if existing.get("question") == question and existing.get("reason") == reason and current_question_is_active(config):
        return existing.get("question_id")

    return None


def _build_question_payload(config, ask, generated_at):
    if not isinstance(ask, dict):
        ask = {}

    question = str(ask.get("question", "")).strip()
    reason = str(ask.get("reason", "")).strip()
    enabled = _as_bool(ask.get("enabled")) and bool(question)

    if not enabled:
        return {
            "schema_version": "phone_interaction.v1",
            "kind": "question",
            "status": "inactive",
            "updated_at": generated_at,
            "source": "llm-planner",
            "planner_mode": _planner_mode(config),
            "question": "",
            "answer_options": [],
            "free_text_allowed": True,
            "response_action": "answer_question",
        }

    existing = _existing_active_question(config)
    same_question = (
        existing.get("question") == question
        and existing.get("reason") == reason
        and current_question_is_active(config)
    )

    question_id = existing.get("question_id") if same_question else None
    question_id = question_id or _new_interaction_id("q", config)
    created_at = existing.get("created_at") if same_question else generated_at

    return {
        "schema_version": "phone_interaction.v1",
        "kind": "question",
        "status": "active",
        "question_id": question_id,
        "created_at": created_at,
        "updated_at": generated_at,
        "source": "llm-planner",
        "planner_mode": _planner_mode(config),
        "question": question,
        "reason": reason,
        "answer_options": _as_options(ask.get("answer_options", [])),
        "free_text_allowed": _as_bool(ask.get("free_text_allowed"), True),
        "response_action": "answer_question",
        "dismiss_action": "dismiss_question",
    }


def _build_nudge_payload(config, result, generated_at):
    nudge = result.get("phone_nudge", {})
    if not isinstance(nudge, dict):
        nudge = {}

    message = str(nudge.get("message", "")).strip()
    recommended_next_action = str(result.get("recommended_next_action", "")).strip()
    urgency = str(nudge.get("urgency", "normal") or "normal").strip().lower()

    if urgency not in {"low", "normal", "high"}:
        urgency = "normal"

    enabled = _as_bool(nudge.get("enabled")) and bool(message)

    if not enabled:
        return {
            "schema_version": "phone_interaction.v1",
            "kind": "nudge",
            "status": "inactive",
            "updated_at": generated_at,
            "source": "llm-planner",
            "planner_mode": _planner_mode(config),
            "urgency": "normal",
            "message": "",
            "recommended_next_action": recommended_next_action,
            "actions": [],
        }

    existing = _existing_active_nudge(config)
    same_nudge = (
        existing.get("message") == message
        and existing.get("recommended_next_action") == recommended_next_action
        and existing.get("urgency") == urgency
    )

    nudge_id = existing.get("nudge_id") if same_nudge else None
    nudge_id = nudge_id or _new_interaction_id("n", config)
    created_at = existing.get("created_at") if same_nudge else generated_at

    return {
        "schema_version": "phone_interaction.v1",
        "kind": "nudge",
        "status": "active",
        "nudge_id": nudge_id,
        "created_at": created_at,
        "updated_at": generated_at,
        "source": "llm-planner",
        "planner_mode": _planner_mode(config),
        "urgency": urgency,
        "message": message,
        "recommended_next_action": recommended_next_action,
        "actions": [
            {
                "action": "ack_nudge",
                "label": "Done",
            },
            {
                "action": "snooze_nudge",
                "label": "Not now",
                "snooze_minutes": 15,
            },
        ],
    }


def _write_question_outputs(config, payload):
    pending_path = config.state_llm_dir / "pending-question.json"
    current_question_json_path = config.outbox_to_phone_dir / "current-question.json"
    current_question_md_path = config.outbox_to_phone_dir / "current-question.md"

    atomic_write_json(current_question_json_path, payload)

    if payload.get("status") == "active":
        pending = {
            "schema_version": "pending_question.v1",
            "question_id": payload.get("question_id", ""),
            "created_at": payload.get("created_at", payload.get("updated_at", now_iso(config))),
            "updated_at": payload.get("updated_at", now_iso(config)),
            "question": payload.get("question", ""),
            "reason": payload.get("reason", ""),
            "answer_options": payload.get("answer_options", []),
            "free_text_allowed": payload.get("free_text_allowed", True),
            "source": payload.get("source", "llm-planner"),
            "planner_mode": payload.get("planner_mode", _planner_mode(config)),
        }

        atomic_write_json(pending_path, pending)

        q_md = []
        q_md.append("# Current Question")
        q_md.append("")
        q_md.append("Status: active")
        q_md.append(f"Question ID: {payload.get('question_id', '')}")
        q_md.append(f"Created: {payload.get('created_at', '')}")
        q_md.append(f"Updated: {payload.get('updated_at', '')}")
        q_md.append("")
        q_md.append(f"Question: {payload.get('question', '')}")
        q_md.append("")
        q_md.append(f"Reason: {payload.get('reason', '')}")
        q_md.append("")
        q_md.append("Options:")

        for opt in payload.get("answer_options", []):
            q_md.append(f"- `{opt.get('id', '')}` — {opt.get('label', '')}")

        q_md.append("")
        q_md.append(f"Free text allowed: {str(payload.get('free_text_allowed', True)).lower()}")
        q_md.append("")
        q_md.append("Response action: `answer_question`")
        q_md.append("Dismiss action: `dismiss_question`")
        q_md.append("")

        atomic_write_text(current_question_md_path, "\n".join(q_md))
        return

    if pending_path.exists():
        try:
            pending_path.unlink()
        except Exception:
            pass

    atomic_write_text(
        current_question_md_path,
        "\n".join([
            "# Current Question",
            "",
            "Status: inactive",
            "Question: none",
            f"Updated: {payload.get('updated_at', now_iso(config))}",
            "",
        ]),
    )


def _write_nudge_outputs(config, payload):
    current_nudge_json_path = config.outbox_to_phone_dir / "current-nudge.json"
    current_nudge_md_path = config.outbox_to_phone_dir / "current-nudge.md"

    atomic_write_json(current_nudge_json_path, payload)

    if payload.get("status") == "active":
        atomic_write_text(
            current_nudge_md_path,
            "\n".join([
                "# Current Nudge",
                "",
                "Status: active",
                f"Nudge ID: {payload.get('nudge_id', '')}",
                f"Urgency: {payload.get('urgency', 'normal')}",
                f"Message: {payload.get('message', '')}",
                f"Recommended next action: {payload.get('recommended_next_action', '')}",
                f"Updated: {payload.get('updated_at', now_iso(config))}",
                f"Planner mode: {payload.get('planner_mode', _planner_mode(config))}",
                "Ack action: `ack_nudge`",
                "Snooze action: `snooze_nudge`",
                "",
            ]),
        )
        return

    atomic_write_text(
        current_nudge_md_path,
        "\n".join([
            "# Current Nudge",
            "",
            "Status: inactive",
            "Message: No current nudge.",
            f"Recommended next action: {payload.get('recommended_next_action', '')}",
            f"Updated: {payload.get('updated_at', now_iso(config))}",
            f"Planner mode: {payload.get('planner_mode', _planner_mode(config))}",
            "",
        ]),
    )


def _compact_question(payload):
    if payload.get("status") != "active":
        return None

    return {
        "question_id": payload.get("question_id", ""),
        "status": payload.get("status", "active"),
        "question": payload.get("question", ""),
        "answer_options": payload.get("answer_options", []),
        "free_text_allowed": payload.get("free_text_allowed", True),
        "response_action": payload.get("response_action", "answer_question"),
        "dismiss_action": payload.get("dismiss_action", "dismiss_question"),
    }


def _compact_nudge(payload):
    if payload.get("status") != "active":
        return None

    return {
        "schema_version": payload.get("schema_version", "phone_interaction.v1"),
        "kind": "nudge",
        "nudge_id": payload.get("nudge_id", ""),
        "status": payload.get("status", "active"),
        "created_at": payload.get("created_at", ""),
        "updated_at": payload.get("updated_at", ""),
        "source": payload.get("source", "llm-planner"),
        "planner_mode": payload.get("planner_mode", "block-plan"),
        "urgency": payload.get("urgency", "normal"),
        "message": payload.get("message", ""),
        "recommended_next_action": payload.get("recommended_next_action", ""),
        "target_id": payload.get("target_id", ""),
        "target_name": payload.get("target_name", ""),
        "actions": payload.get("actions", []),
    }


def _write_interaction_state(config, question_payload, nudge_payload, generated_at):
    state = {
        "schema_version": "phone_interaction_state.v1",
        "updated_at": generated_at,
        "source": "llm-planner",
        "planner_mode": _planner_mode(config),
        "active_nudge": _compact_nudge(nudge_payload),
        "active_question": _compact_question(question_payload),
    }

    atomic_write_json(config.outbox_to_phone_dir / "interaction-state.json", state)


def write_machine_outputs(config, result):
    atomic_write_json(config.state_llm_dir / "last-output.json", result)

    metadata = result.get("_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    generated_at = metadata.get("generated_at") or now_iso(config)

    ask = result.get("ask_user", {})
    question_payload = _build_question_payload(config, ask, generated_at)
    _write_question_outputs(config, question_payload)

    nudge_payload = _build_nudge_payload(config, result, generated_at)
    _write_nudge_outputs(config, nudge_payload)

    _write_interaction_state(config, question_payload, nudge_payload, generated_at)


def write_error_file(config, error):
    lines = [
        "# LLM Planner Error",
        "",
        f"Time: {now_iso(config)}",
        f"Mode: `{getattr(config, 'planner_mode', 'block-plan')}`",
        "",
        "```text",
        str(error),
        "```",
        "",
    ]

    atomic_write_text(config.state_llm_dir / "last-error.md", "\n".join(lines))


def write_planner_status(config, status, metadata=None, warnings=None, error=""):
    metadata = metadata or {}
    warnings = warnings or []

    data = {
        "updated_at": now_iso(config),
        "status": status,
        "model": config.ollama_model,
        "planner_mode": getattr(config, "planner_mode", "block-plan"),
        "ollama_format": config.ollama_format,
        "metadata": metadata,
        "warnings": warnings,
        "error": error,
    }

    atomic_write_json(config.state_llm_dir / "planner-status.json", data)

    lines = []
    lines.append("# LLM Planner Status")
    lines.append("")
    lines.append(f"Updated: {data['updated_at']}")
    lines.append(f"Status: `{status}`")
    lines.append(f"Mode: `{data['planner_mode']}`")
    lines.append(f"Model: `{config.ollama_model}`")
    lines.append(f"Format: `{config.ollama_format}`")
    lines.append("")

    if metadata:
        lines.append("## Metadata")
        lines.append("")
        for key, value in metadata.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if error:
        lines.append("## Error")
        lines.append("")
        lines.append("```text")
        lines.append(error)
        lines.append("```")
        lines.append("")

    atomic_write_text(config.state_llm_dir / "planner-status.md", "\n".join(lines))
