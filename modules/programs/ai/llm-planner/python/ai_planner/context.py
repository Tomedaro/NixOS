import json
from collections import Counter

from ai_planner.io_utils import (
    clamp_text,
    read_json,
    read_jsonl_tail,
    read_text_limited,
    safe_str,
    tail_text,
    today,
)


def event_timestamp(event):
    return (
        event.get("timestamp")
        or event.get("processed_at")
        or event.get("time")
        or str(event.get("timestamp_epoch", ""))
    )


def summarize_events(events, kind):
    event_counts = Counter()
    verdict_counts = Counter()
    app_counts = Counter()
    answer_counts = Counter()
    recent = []

    for event in events:
        event_name = safe_str(event.get("event") or event.get("type") or "unknown")
        verdict = safe_str(event.get("verdict"))
        app = safe_str(event.get("app"))
        answer = safe_str(event.get("answer") or event.get("answer_label"))

        if event_name:
            event_counts[event_name] += 1
        if verdict:
            verdict_counts[verdict] += 1
        if app:
            app_counts[app] += 1
        if answer:
            answer_counts[answer] += 1

        recent.append({
            "timestamp": event_timestamp(event),
            "event": event_name,
            "verdict": verdict,
            "app": clamp_text(app, 80),
            "title": clamp_text(event.get("title", ""), 120),
            "message": clamp_text(event.get("message", ""), 160),
            "answer": clamp_text(answer, 80),
            "reason": clamp_text(event.get("reason", ""), 160),
        })

    return {
        "kind": kind,
        "count": len(events),
        "event_counts": dict(event_counts.most_common(12)),
        "verdict_counts": dict(verdict_counts.most_common(8)),
        "app_counts": dict(app_counts.most_common(10)),
        "answer_counts": dict(answer_counts.most_common(8)),
        "recent": recent[-12:],
    }


def compact_anki(status_json):
    if not isinstance(status_json, dict):
        return {"available": False, "error": "Anki status is not an object"}

    totals = status_json.get("totals", {})
    decks = []

    for item in status_json.get("decks", []) or []:
        if not isinstance(item, dict):
            continue

        derived = item.get("derived", {}) or {}
        decks.append({
            "deck": item.get("deck", "unknown"),
            "due": derived.get("due", 0),
            "review_due": derived.get("review_due", 0),
            "learning": derived.get("learning", 0),
            "new": derived.get("new", 0),
            "reviewed_today": derived.get("reviewed_today", 0),
            "again_today": derived.get("again_today", 0),
            "priority": derived.get("priority", "unknown"),
            "suggested_goal": derived.get("suggested_goal", ""),
        })

    return {
        "available": status_json.get("available", False),
        "timestamp": status_json.get("timestamp", ""),
        "overall_priority": status_json.get("overall_priority", "unknown"),
        "totals": {
            "due": totals.get("due", 0),
            "review_due": totals.get("review_due", 0),
            "learning": totals.get("learning", 0),
            "new": totals.get("new", 0),
            "reviewed_today": totals.get("reviewed_today", 0),
            "again_today": totals.get("again_today", 0),
        },
        "decks": decks,
        "error": status_json.get("error", ""),
    }


def compact_tasknotes(config):
    if not config.tasknotes_dir.exists():
        return []

    try:
        paths = [p for p in config.tasknotes_dir.rglob("*.md") if p.is_file()]
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception as error:
        return [{"error": str(error)}]

    tasks = []
    for path in paths[: config.max_tasknotes]:
        try:
            rel = path.relative_to(config.tasknotes_dir)
            text = path.read_text(encoding="utf-8")
            tasks.append({
                "path": str(rel),
                "modified_epoch": int(path.stat().st_mtime),
                "snippet": text[: config.max_tasknote_chars],
            })
        except Exception as error:
            tasks.append({
                "path": str(path),
                "error": str(error),
            })

    return tasks


def derive_flags(context):
    flags = []

    anki = context.get("anki", {})
    totals = anki.get("totals", {})
    due = int(totals.get("due") or 0)
    reviewed_today = int(totals.get("reviewed_today") or 0)

    if due >= 300:
        flags.append("anki_backlog_urgent")
    elif due >= 100:
        flags.append("anki_backlog_high")
    elif due > 0:
        flags.append("anki_due_present")

    if reviewed_today > 0:
        flags.append("anki_progress_today")

    desktop_now = context.get("state", {}).get("desktop_now", {})
    verdict = desktop_now.get("verdict")
    if verdict:
        flags.append(f"desktop_verdict_{verdict}")

    session = context.get("session", {}).get("current", {})
    if isinstance(session, dict):
        session_status = session.get("status")
        session_mode = session.get("mode")
        if session_status:
            flags.append(f"session_status_{session_status}")
        if session_mode:
            flags.append(f"session_mode_{session_mode}")

    phone_recent = context.get("events", {}).get("phone_summary", {}).get("event_counts", {})
    desktop_recent = context.get("events", {}).get("desktop_summary", {}).get("event_counts", {})

    for name in ["too_hard", "stuck", "need_smaller_step", "manual_checkin", "question_answered"]:
        if phone_recent.get(name) or desktop_recent.get(name):
            flags.append(f"recent_{name}")

    phone_answers = context.get("events", {}).get("phone_summary", {}).get("answer_counts", {})
    desktop_answers = context.get("events", {}).get("desktop_summary", {}).get("answer_counts", {})

    for answer in list(phone_answers.keys()) + list(desktop_answers.keys()):
        if answer:
            flags.append(f"recent_answer_{answer}")

    return sorted(set(flags))


def build_context(config):
    date = today(config)

    desktop_events = read_jsonl_tail(config.events_desktop_dir / f"{date}.jsonl", config.max_jsonl_events)
    phone_events = read_jsonl_tail(config.events_phone_dir / f"{date}.jsonl", config.max_jsonl_events)
    anki_status = compact_anki(read_json(config.anki_dir / "status.json", {}))

    raw_session_current = read_json(config.state_session_dir / "current.json", {})
    if not isinstance(raw_session_current, dict):
        raw_session_current = {}

    raw_current_policy = read_json(config.state_session_dir / "current-policy.json", {})
    if not isinstance(raw_current_policy, dict):
        raw_current_policy = {}

    session_is_active = str(raw_session_current.get("status", "")).strip().lower() == "active"
    session_current = raw_session_current if session_is_active else {}
    session_last = {} if session_is_active else raw_session_current
    current_policy = raw_current_policy if session_is_active else {}

    if session_is_active:
        current_task_text = read_text_limited(config.control_dir / "current-task.md", config.max_control_chars)
        current_block_text = read_text_limited(config.control_dir / "current-block.md", config.max_control_chars)
        current_mode_text = read_text_limited(config.control_dir / "current-mode.md", config.max_control_chars)
        current_policy_markdown = read_text_limited(
            config.state_session_dir / "current-policy.md",
            config.max_policy_chars,
        )
    else:
        current_task_text = "No active session."
        current_block_text = "No active session."
        current_mode_text = "No active session."
        current_policy_markdown = ""

    context = {
        "generated_at": config.generated_at,
        "date": date,
        "paths": {
            "ai_dir": str(config.ai_dir),
            "tasknotes_dir": str(config.tasknotes_dir),
        },
        "control": {
            "current_task": current_task_text,
            "current_block": current_block_text,
            "current_mode": current_mode_text,
        },
        "policy": {
            "apps": read_text_limited(config.policy_dir / "apps.md", config.max_policy_chars),
            "domains": read_text_limited(config.policy_dir / "domains.md", config.max_policy_chars),
            "proof": read_text_limited(config.policy_dir / "proof.md", config.max_policy_chars),
            "retention": read_text_limited(config.policy_dir / "retention.md", config.max_policy_chars),
        },
        "state": {
            "desktop_now": read_json(config.state_desktop_dir / "now.json", {}),
            "phone_latest": read_json(config.state_phone_dir / "latest.json", {}),
            "last_answer": read_json(config.state_llm_dir / "last-answer.json", {}),
        },
        "session": {
            "has_active_session": session_is_active,
            "current": session_current,
            "last": session_last,
            "current_policy": current_policy,
            "current_policy_markdown": current_policy_markdown,
        },
        "anki": anki_status,
        "events": {
            "desktop_summary": summarize_events(desktop_events, "desktop"),
            "phone_summary": summarize_events(phone_events, "phone"),
        },
        "logs": {
            "desktop_tail": tail_text(config.logs_desktop_dir / f"{date}.md", config.max_log_chars),
            "phone_tail": tail_text(config.logs_phone_dir / f"{date}.md", config.max_log_chars),
        },
        "tasknotes": compact_tasknotes(config),
    }

    context["derived_flags"] = derive_flags(context)
    return context


def context_to_markdown(config, context):
    lines = []

    lines.append(f"# LLM Context Pack - {context['date']}")
    lines.append("")
    lines.append(f"Generated at: {context['generated_at']}")
    lines.append("")
    lines.append("## Planner objective")
    lines.append("")
    lines.append("Assess the current productivity situation, with Anki recovery as the first optimization target.")
    lines.append("Detect friction, ask one useful question if needed, propose at most three small tasks, and write a short phone nudge.")
    lines.append("")

    lines.append("## Derived flags")
    for flag in context.get("derived_flags", []):
        lines.append(f"- {flag}")
    lines.append("")

    lines.append("## Current state")
    lines.append("### Desktop now")
    lines.append("```json")
    lines.append(json.dumps(context["state"]["desktop_now"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("### Phone latest")
    lines.append("```json")
    lines.append(json.dumps(context["state"]["phone_latest"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("### Last explicit answer")
    lines.append("```json")
    lines.append(json.dumps(context["state"]["last_answer"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Anki compact status")
    lines.append("```json")
    lines.append(json.dumps(context["anki"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Current session")
    lines.append("### current.json")
    lines.append("```json")
    lines.append(json.dumps(context.get("session", {}).get("current", {}), indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("### current-policy.json")
    lines.append("```json")
    lines.append(json.dumps(context.get("session", {}).get("current_policy", {}), indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("### current-policy.md")
    lines.append("```markdown")
    lines.append(context.get("session", {}).get("current_policy_markdown", ""))
    lines.append("```")
    lines.append("")

    lines.append("## Control")
    for name, value in context["control"].items():
        lines.append(f"### {name}")
        lines.append("```markdown")
        lines.append(value)
        lines.append("```")
    lines.append("")

    lines.append("## Recent event summaries")
    lines.append("### Desktop")
    lines.append("```json")
    lines.append(json.dumps(context["events"]["desktop_summary"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("### Phone")
    lines.append("```json")
    lines.append(json.dumps(context["events"]["phone_summary"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Log tails")
    lines.append("### Desktop")
    lines.append("```markdown")
    lines.append(context["logs"]["desktop_tail"])
    lines.append("```")
    lines.append("### Phone")
    lines.append("```markdown")
    lines.append(context["logs"]["phone_tail"])
    lines.append("```")
    lines.append("")

    lines.append("## Recent TaskNotes snippets")
    for task in context["tasknotes"]:
        lines.append(f"### {task.get('path', 'unknown')}")
        if "error" in task:
            lines.append(f"Error: {task['error']}")
        else:
            lines.append("```markdown")
            lines.append(task.get("snippet", ""))
            lines.append("```")
        lines.append("")

    lines.append("## Policy hints")
    lines.append("### apps.md")
    lines.append("```markdown")
    lines.append(context["policy"]["apps"])
    lines.append("```")
    lines.append("### domains.md")
    lines.append("```markdown")
    lines.append(context["policy"]["domains"])
    lines.append("```")

    markdown = "\n".join(lines)

    if len(markdown) > config.max_context_chars:
        keep_head = config.max_context_chars // 3
        keep_tail = config.max_context_chars - keep_head
        markdown = (
            markdown[:keep_head]
            + "\n\n[...context truncated by planner to fit local model context...]\n\n"
            + markdown[-keep_tail:]
        )

    return markdown
