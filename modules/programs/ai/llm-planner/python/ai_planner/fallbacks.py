from ai_planner.io_utils import now_iso


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _last_answer(context):
    last_answer = context.get("state", {}).get("last_answer", {})
    if not isinstance(last_answer, dict):
        return "", ""

    answer = str(last_answer.get("answer", "")).strip().lower()
    label = str(last_answer.get("answer_label", "")).strip()

    return answer, label


def _anki_due(context):
    anki = context.get("anki", {})
    totals = anki.get("totals", {})
    return _safe_int(totals.get("due", 0)), _safe_int(totals.get("review_due", 0))


def _desktop_summary(context):
    desktop = context.get("state", {}).get("desktop_now", {})
    if not isinstance(desktop, dict):
        return "unknown", "", "", ""

    return (
        str(desktop.get("verdict", "unknown")),
        str(desktop.get("app", "")),
        str(desktop.get("title", "")),
        str(desktop.get("task", "")),
    )


def _session_context(context):
    session_block = context.get("session", {})
    session = session_block.get("current", {})
    policy = session_block.get("current_policy", {})

    if not isinstance(session, dict):
        session = {}
    if not isinstance(policy, dict):
        policy = {}

    status = str(session.get("status") or "").strip().lower()
    active = status == "active"

    if active:
        task = str(session.get("task") or policy.get("task") or "").strip()
        project = str(session.get("project") or policy.get("project") or "Current Task").strip()
        mode = str(session.get("mode") or policy.get("mode") or "").strip().lower()
    else:
        task = ""
        project = "Current Task"
        mode = ""

    return {
        "active": active,
        "status": status,
        "task": task,
        "project": project or "Current Task",
        "mode": mode,
    }


def _session_is_anki_target(session, due, review_due):
    text = " ".join([
        session.get("task", ""),
        session.get("project", ""),
        session.get("mode", ""),
    ]).lower()

    if "anki" in text:
        return True

    if session.get("active"):
        return False

    return due > 0 or review_due > 0


def _generic_current_task_result(config, context, reason, session, answer, label, verdict, app, title):
    task = session.get("task") or "the current task"
    project = session.get("project") or "Current Task"

    if answer in {"overwhelmed", "too_hard", "not_now"}:
        action = f"Work on the smallest visible part of '{task}' for 5 minutes only. Stop after the timer."
        nudge = "Overwhelmed mode: 5 minutes on the smallest visible step. Stop after that."
        estimate = 5
        task_title = "Tiny current-session step"
        friction = "The latest answer indicates overwhelm, so the current session should be reduced."
        level = 2
        priority = "high"
    elif answer == "tired":
        action = f"Do a 3-minute reset, then reopen '{task}'. Stop after the reset if energy is still low."
        nudge = "Tired mode: water, posture, reopen the task. 3 minutes."
        estimate = 3
        task_title = "Minimum-energy reset"
        friction = "The latest answer indicates tiredness, so the system should reduce energy demand."
        level = 1
        priority = "normal"
    elif answer == "unclear":
        action = f"Write one sentence defining the next concrete step for '{task}', then do 5 minutes."
        nudge = "Unclear mode: define the next visible step, then 5 minutes."
        estimate = 7
        task_title = "Clarify current-session step"
        friction = "The latest answer indicates unclear next action."
        level = 2
        priority = "normal"
    else:
        action = f"Work on '{task}' for 10 minutes, then reassess."
        nudge = "10 minutes on the current session task, then reassess."
        estimate = 10
        task_title = "Short current-session block"
        friction = "The current session is the best available target."
        level = 1
        priority = "normal"

    return {
        "summary": "Help-now fallback used. It respected the active session instead of defaulting to Anki.",
        "situation_assessment": (
            f"Desktop verdict is '{verdict}' with app '{app}'. "
            f"Current session mode is '{session.get('mode') or 'unknown'}'. "
            f"Latest answer was '{label or answer or 'none'}'."
        ),
        "friction_hypothesis": friction,
        "recommended_next_action": action,
        "phone_nudge": {
            "enabled": True,
            "message": nudge,
            "urgency": "normal",
        },
        "ask_user": {
            "enabled": False,
            "question": "",
            "reason": "Help-now fallback should avoid asking another immediate question.",
            "answer_options": [],
            "free_text_allowed": True,
        },
        "proposed_tasks": [
            {
                "title": task_title,
                "reason": friction,
                "priority": priority,
                "estimated_minutes": estimate,
                "project": project,
            }
        ],
        "reflection_questions": [],
        "intervention_recommendation": {
            "level": level,
            "reason": "Fast bounded intervention selected because LLM help-now failed or timed out.",
        },
        "risks": [
            "LLM help-now failed or timed out; deterministic fallback was used.",
            str(reason)[:500],
        ],
        "_metadata": {
            "generated_at": now_iso(config),
            "model": config.ollama_model,
            "planner_mode": "help-now",
            "fallback": "deterministic-help-now",
            "fallback_reason": str(reason)[:1000],
            "session_mode": session.get("mode", ""),
            "session_status": session.get("status", ""),
        },
    }


def _anki_result(config, context, reason, session, answer, label, due, review_due, verdict, app, title):
    project = session.get("project") or "Anki Recovery"

    if answer in {"overwhelmed", "too_hard", "not_now"}:
        action = "Open Anki and do 5 cards or 5 minutes, whichever comes first. Stop immediately after."
        nudge = "Overwhelmed mode: 5 Anki cards or 5 minutes. Stop after that."
        estimate = 5
        task_title = "Tiny Anki recovery step"
        friction = "The latest answer indicates overwhelm, so the Anki task must become smaller."
        priority = "high"
        level = 2
    elif answer == "tired":
        action = "Open Anki and do 3 easy cards or 3 minutes. The goal is restart, not volume."
        nudge = "Tired mode: 3 easy Anki cards or 3 minutes."
        estimate = 3
        task_title = "Minimum-energy Anki step"
        friction = "The latest answer indicates tiredness, so the system should reduce energy demand."
        priority = "normal"
        level = 2
    elif answer == "unclear":
        action = "Review 5 Anki cards slowly. If a card feels unclear, mark it for later instead of fighting it."
        nudge = "Unclear mode: 5 slow cards. Mark confusing ones for later."
        estimate = 7
        task_title = "Clarify Anki friction"
        friction = "The latest answer indicates unclear material or unclear next step."
        priority = "normal"
        level = 2
    else:
        action = "Do 10 Anki cards or 10 minutes, whichever comes first."
        nudge = "Do 10 Anki cards or 10 minutes. Stop when one limit hits."
        estimate = 10
        task_title = "Small Anki recovery block"
        friction = "Anki is the active target and backlog is present; a small bounded block is appropriate."
        priority = "normal"
        level = 1

    return {
        "summary": f"Help-now fallback used. Anki is the active recovery target with about {due} due cards.",
        "situation_assessment": (
            f"Desktop verdict is '{verdict}' with app '{app}'. "
            f"Latest answer was '{label or answer or 'none'}'."
        ),
        "friction_hypothesis": friction,
        "recommended_next_action": action,
        "phone_nudge": {
            "enabled": True,
            "message": nudge,
            "urgency": "normal",
        },
        "ask_user": {
            "enabled": False,
            "question": "",
            "reason": "Help-now fallback should avoid asking another immediate question.",
            "answer_options": [],
            "free_text_allowed": True,
        },
        "proposed_tasks": [
            {
                "title": task_title,
                "reason": friction,
                "priority": priority,
                "estimated_minutes": estimate,
                "project": project,
            }
        ],
        "reflection_questions": [],
        "intervention_recommendation": {
            "level": level,
            "reason": "Fast bounded intervention selected because LLM help-now failed or timed out.",
        },
        "risks": [
            "LLM help-now failed or timed out; deterministic fallback was used.",
            str(reason)[:500],
        ],
        "_metadata": {
            "generated_at": now_iso(config),
            "model": config.ollama_model,
            "planner_mode": "help-now",
            "fallback": "deterministic-help-now",
            "fallback_reason": str(reason)[:1000],
            "session_mode": session.get("mode", ""),
            "session_status": session.get("status", ""),
        },
    }


def help_now_fallback_result(config, context, reason):
    answer, label = _last_answer(context)
    due, review_due = _anki_due(context)
    verdict, app, title, desktop_task = _desktop_summary(context)
    session = _session_context(context)

    if not session.get("task") and desktop_task:
        session["task"] = desktop_task

    if _session_is_anki_target(session, due, review_due):
        return _anki_result(
            config,
            context,
            reason,
            session,
            answer,
            label,
            due,
            review_due,
            verdict,
            app,
            title,
        )

    return _generic_current_task_result(
        config,
        context,
        reason,
        session,
        answer,
        label,
        verdict,
        app,
        title,
    )
