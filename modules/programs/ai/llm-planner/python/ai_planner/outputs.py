from ai_planner.io_utils import (
    atomic_write_json,
    atomic_write_text,
    now_iso,
    read_json,
    read_text,
    today,
)


def write_context_files(config, context, markdown):
    atomic_write_json(config.context_dir / "today.json", context)
    atomic_write_text(config.context_dir / "today.md", markdown)


def write_markdown_outputs(config, result):
    date = today(config)

    report = []
    report.append(f"# Daily LLM Planner Report - {date}")
    report.append("")
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

    atomic_write_text(config.reports_daily_dir / f"{date}.md", "\n".join(report))

    proposed = []
    proposed.append(f"# Proposed Tasks - {date}")
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

    atomic_write_text(config.proposed_tasks_dir / f"{date}.md", "\n".join(proposed))

    last_md = []
    last_md.append("# Last LLM Planner Output")
    last_md.append("")
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


def current_question_is_active(config):
    text = read_text(config.outbox_to_phone_dir / "current-question.md", "")
    return "Status: active" in text


def existing_pending_matches(config, question, reason):
    existing = read_json(config.state_llm_dir / "pending-question.json", {})
    if not existing:
        return None

    if existing.get("question") == question and existing.get("reason") == reason and current_question_is_active(config):
        return existing.get("question_id")

    return None


def write_machine_outputs(config, result):
    atomic_write_json(config.state_llm_dir / "last-output.json", result)

    ask = result.get("ask_user", {})
    pending_path = config.state_llm_dir / "pending-question.json"
    current_question_path = config.outbox_to_phone_dir / "current-question.md"

    if ask.get("enabled"):
        question = ask.get("question", "")
        reason = ask.get("reason", "")
        existing_id = existing_pending_matches(config, question, reason)
        question_id = existing_id or f"q-{today(config)}-{int(__import__('time').time())}"

        pending = {
            "question_id": question_id,
            "created_at": now_iso(config),
            "question": question,
            "reason": reason,
            "answer_options": ask.get("answer_options", []),
            "free_text_allowed": ask.get("free_text_allowed", True),
            "source": "llm-planner",
        }

        atomic_write_json(pending_path, pending)

        q_md = []
        q_md.append("# Current Question")
        q_md.append("")
        q_md.append("Status: active")
        q_md.append(f"Question ID: {question_id}")
        q_md.append(f"Created: {pending['created_at']}")
        q_md.append("")
        q_md.append(f"Question: {pending['question']}")
        q_md.append("")
        q_md.append(f"Reason: {pending['reason']}")
        q_md.append("")
        q_md.append("Options:")
        for opt in pending["answer_options"]:
            q_md.append(f"- `{opt.get('id', '')}` — {opt.get('label', '')}")
        q_md.append("")
        q_md.append(f"Free text allowed: {str(pending['free_text_allowed']).lower()}")
        q_md.append("")

        atomic_write_text(current_question_path, "\n".join(q_md))
    else:
        if pending_path.exists():
            try:
                pending_path.unlink()
            except Exception:
                pass

        atomic_write_text(current_question_path, "# Current Question\n\nStatus: inactive\nQuestion: none\n")

    nudge = result.get("phone_nudge", {})
    current_nudge_path = config.outbox_to_phone_dir / "current-nudge.md"

    if nudge.get("enabled"):
        atomic_write_text(
            current_nudge_path,
            "\n".join([
                "# Current Nudge",
                "",
                "Status: active",
                f"Urgency: {nudge.get('urgency', 'normal')}",
                f"Message: {nudge.get('message', '')}",
                f"Recommended next action: {result.get('recommended_next_action', '')}",
                f"Updated: {now_iso(config)}",
                "",
            ]),
        )
    else:
        atomic_write_text(
            current_nudge_path,
            "\n".join([
                "# Current Nudge",
                "",
                "Status: inactive",
                "Message: No current nudge.",
                f"Updated: {now_iso(config)}",
                "",
            ]),
        )


def write_error_file(config, error):
    lines = [
        "# LLM Planner Error",
        "",
        f"Time: {now_iso(config)}",
        "",
        "```text",
        str(error),
        "```",
        "",
    ]

    atomic_write_text(config.state_llm_dir / "last-error.md", "\n".join(lines))
