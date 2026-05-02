#!/usr/bin/env python3

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TASKNOTES_DIR = Path(os.environ.get("TASKNOTES_DIR", "/home/daniil/Sync/Perseverance.Gu/TaskNotes")).expanduser()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
TIMEZONE = ZoneInfo(os.environ.get("LLM_PLANNER_TIMEZONE", "Europe/Paris"))

MAX_LOG_CHARS = int(os.environ.get("MAX_LOG_CHARS", "12000"))
MAX_JSONL_EVENTS = int(os.environ.get("MAX_JSONL_EVENTS", "120"))
MAX_TASKNOTES = int(os.environ.get("MAX_TASKNOTES", "30"))

CONTROL_DIR = AI_DIR / "control"
POLICY_DIR = AI_DIR / "policy"
STATE_DIR = AI_DIR / "state"
STATE_DESKTOP_DIR = STATE_DIR / "desktop"
STATE_PHONE_DIR = STATE_DIR / "phone"
STATE_LLM_DIR = STATE_DIR / "llm"

CONTEXT_DIR = AI_DIR / "context"
REPORTS_DAILY_DIR = AI_DIR / "reports" / "daily"
PROPOSED_TASKS_DIR = AI_DIR / "proposed-tasks"
OUTBOX_TO_PHONE_DIR = AI_DIR / "outbox" / "to-phone"

EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"
EVENTS_PHONE_DIR = AI_DIR / "events" / "phone"
LOGS_DESKTOP_DIR = AI_DIR / "logs" / "desktop"
LOGS_PHONE_DIR = AI_DIR / "logs" / "phone"
ANKI_DIR = AI_DIR / "anki"

TODAY_CONTEXT_MD = CONTEXT_DIR / "today.md"
TODAY_CONTEXT_JSON = CONTEXT_DIR / "today.json"

LAST_OUTPUT_JSON = STATE_LLM_DIR / "last-output.json"
LAST_OUTPUT_MD = STATE_LLM_DIR / "last-output.md"
PENDING_QUESTION_JSON = STATE_LLM_DIR / "pending-question.json"

CURRENT_NUDGE_MD = OUTBOX_TO_PHONE_DIR / "current-nudge.md"
CURRENT_QUESTION_MD = OUTBOX_TO_PHONE_DIR / "current-question.md"


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
                "urgency": {"type": "string", "enum": ["low", "normal", "high"]}
            },
            "required": ["enabled", "message", "urgency"]
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
                            "label": {"type": "string"}
                        },
                        "required": ["id", "label"]
                    }
                },
                "free_text_allowed": {"type": "boolean"}
            },
            "required": ["enabled", "question", "reason", "answer_options", "free_text_allowed"]
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
                    "project": {"type": "string"}
                },
                "required": ["title", "reason", "priority", "estimated_minutes", "project"]
            }
        },
        "reflection_questions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "intervention_recommendation": {
            "type": "object",
            "properties": {
                "level": {"type": "integer"},
                "reason": {"type": "string"}
            },
            "required": ["level", "reason"]
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"}
        }
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
        "risks"
    ]
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
- Treat backlog/depression/executive dysfunction as load-management problems.
- Prefer small executable next actions over ambitious catch-up fantasies.
- Avoid creating too many obligations.
- If the situation is unclear, ask one useful question.
- If Anki backlog is high, prefer repeated small recovery blocks.
- If the user appears stuck or avoidant, simplify the next task.
- Preserve agency: propose and nudge, but do not pretend completion happened.
- Do not recommend strict enforcement unless the evidence strongly supports it.
- Create at most 3 proposed tasks.
- Make the phone nudge short and actionable.
- Return only valid JSON matching the schema.
"""


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in [
        CONTEXT_DIR,
        STATE_LLM_DIR,
        REPORTS_DAILY_DIR,
        PROPOSED_TASKS_DIR,
        OUTBOX_TO_PHONE_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_text(path, default=""):
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as error:
        return f"[error reading {path}: {error}]"
    return default


def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"error": f"error reading {path}: {error}"}
    return default


def tail_text(path, max_chars):
    text = read_text(path, "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def read_jsonl_tail(path, max_events):
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as error:
        return [{"error": f"error reading {path}: {error}"}]

    events = []
    for line in lines[-max_events:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            events.append({"malformed": line[:500]})

    return events


def list_tasknotes():
    if not TASKNOTES_DIR.exists():
        return []

    files = []
    try:
        for path in TASKNOTES_DIR.rglob("*.md"):
            if len(files) >= MAX_TASKNOTES:
                break
            try:
                rel = path.relative_to(TASKNOTES_DIR)
                text = path.read_text(encoding="utf-8")
                snippet = text[:2500]
                files.append({
                    "path": str(rel),
                    "snippet": snippet,
                })
            except Exception as error:
                files.append({
                    "path": str(path),
                    "error": str(error),
                })
    except Exception as error:
        files.append({"error": str(error)})

    return files


def build_context():
    date = today()

    context = {
        "generated_at": now_iso(),
        "date": date,
        "paths": {
            "ai_dir": str(AI_DIR),
            "tasknotes_dir": str(TASKNOTES_DIR),
        },
        "control": {
            "current_task": read_text(CONTROL_DIR / "current-task.md"),
            "current_block": read_text(CONTROL_DIR / "current-block.md"),
            "current_mode": read_text(CONTROL_DIR / "current-mode.md"),
        },
        "policy": {
            "apps": read_text(POLICY_DIR / "apps.md"),
            "domains": read_text(POLICY_DIR / "domains.md"),
            "proof": read_text(POLICY_DIR / "proof.md"),
            "retention": read_text(POLICY_DIR / "retention.md"),
        },
        "state": {
            "desktop_now": read_json(STATE_DESKTOP_DIR / "now.json", {}),
            "phone_latest": read_json(STATE_PHONE_DIR / "latest.json", {}),
        },
        "anki": {
            "status_json": read_json(ANKI_DIR / "status.json", {}),
            "status_md": read_text(ANKI_DIR / "status.md"),
        },
        "events": {
            "desktop_recent": read_jsonl_tail(EVENTS_DESKTOP_DIR / f"{date}.jsonl", MAX_JSONL_EVENTS),
            "phone_recent": read_jsonl_tail(EVENTS_PHONE_DIR / f"{date}.jsonl", MAX_JSONL_EVENTS),
        },
        "logs": {
            "desktop_tail": tail_text(LOGS_DESKTOP_DIR / f"{date}.md", MAX_LOG_CHARS),
            "phone_tail": tail_text(LOGS_PHONE_DIR / f"{date}.md", MAX_LOG_CHARS),
        },
        "tasknotes": list_tasknotes(),
    }

    return context


def context_to_markdown(context):
    lines = []

    lines.append(f"# LLM Context Pack - {context['date']}")
    lines.append("")
    lines.append(f"Generated at: {context['generated_at']}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("Use this evidence to assess the current productivity situation, especially Anki recovery, friction, phone/desktop behavior, and next useful actions.")
    lines.append("")

    lines.append("## Current control files")
    lines.append("")
    lines.append("### current-task.md")
    lines.append("```markdown")
    lines.append(context["control"]["current_task"])
    lines.append("```")
    lines.append("")
    lines.append("### current-block.md")
    lines.append("```markdown")
    lines.append(context["control"]["current_block"])
    lines.append("```")
    lines.append("")
    lines.append("### current-mode.md")
    lines.append("```markdown")
    lines.append(context["control"]["current_mode"])
    lines.append("```")
    lines.append("")

    lines.append("## Current state")
    lines.append("")
    lines.append("### Desktop now")
    lines.append("```json")
    lines.append(json.dumps(context["state"]["desktop_now"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("### Phone latest")
    lines.append("```json")
    lines.append(json.dumps(context["state"]["phone_latest"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Anki")
    lines.append("")
    lines.append("### status.md")
    lines.append("```markdown")
    lines.append(context["anki"]["status_md"])
    lines.append("```")
    lines.append("")
    lines.append("### status.json")
    lines.append("```json")
    lines.append(json.dumps(context["anki"]["status_json"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Recent desktop events")
    lines.append("```json")
    lines.append(json.dumps(context["events"]["desktop_recent"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Recent phone events")
    lines.append("```json")
    lines.append(json.dumps(context["events"]["phone_recent"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## Desktop log tail")
    lines.append("```markdown")
    lines.append(context["logs"]["desktop_tail"])
    lines.append("```")
    lines.append("")

    lines.append("## Phone log tail")
    lines.append("```markdown")
    lines.append(context["logs"]["phone_tail"])
    lines.append("```")
    lines.append("")

    lines.append("## TaskNotes snippets")
    lines.append("")
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
    lines.append("")
    lines.append("### apps.md")
    lines.append("```markdown")
    lines.append(context["policy"]["apps"])
    lines.append("```")
    lines.append("")
    lines.append("### domains.md")
    lines.append("```markdown")
    lines.append(context["policy"]["domains"])
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def write_context(context, markdown):
    tmp_json = TODAY_CONTEXT_JSON.with_suffix(".tmp")
    tmp_json.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_json.replace(TODAY_CONTEXT_JSON)

    tmp_md = TODAY_CONTEXT_MD.with_suffix(".tmp")
    tmp_md.write_text(markdown, encoding="utf-8")
    tmp_md.replace(TODAY_CONTEXT_MD)


def call_ollama(context_markdown):
    user_prompt = f"""Analyze the following context pack.

You must return valid JSON matching the provided schema.

Decide:
- what is happening now
- whether there is friction/avoidance
- whether to ask user clarifying question
- what the next smallest useful action is
- what phone nudge should be shown
- what proposed tasks should be created, max 3
- what reflection questions are useful

Prefer Anki recovery as the first optimization target.
Do not moralize. Do not shame. Prefer small recovery blocks.

Context pack:

{context_markdown}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {
            "temperature": 0
        },
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "llm-planner/0.1",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=600) as response:
        raw = json.loads(response.read().decode("utf-8"))

    content = raw.get("message", {}).get("content", "")

    try:
        parsed = json.loads(content)
    except Exception as error:
        parsed = {
            "summary": "Planner returned invalid JSON.",
            "situation_assessment": "The local model response could not be parsed.",
            "friction_hypothesis": "Unknown.",
            "recommended_next_action": "Inspect AI/state/llm/last-output.md and AI/context/today.md.",
            "phone_nudge": {
                "enabled": False,
                "message": "",
                "urgency": "low"
            },
            "ask_user": {
                "enabled": True,
                "question": "The planner output was invalid. Should we inspect the context and model?",
                "reason": str(error),
                "answer_options": [
                    {"id": "inspect", "label": "Inspect"},
                    {"id": "ignore", "label": "Ignore"}
                ],
                "free_text_allowed": True
            },
            "proposed_tasks": [],
            "reflection_questions": [],
            "intervention_recommendation": {
                "level": 0,
                "reason": "Invalid output."
            },
            "risks": [
                f"Invalid JSON from model: {error}",
                content[:1000]
            ]
        }

    parsed["_metadata"] = {
        "generated_at": now_iso(),
        "model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_URL,
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "eval_count": raw.get("eval_count"),
        "total_duration": raw.get("total_duration"),
    }

    return parsed


def write_markdown_outputs(result):
    date = today()

    report = []
    report.append(f"# Daily LLM Planner Report - {date}")
    report.append("")
    report.append(f"Generated at: {result.get('_metadata', {}).get('generated_at', now_iso())}")
    report.append(f"Model: `{result.get('_metadata', {}).get('model', OLLAMA_MODEL)}`")
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
    report.append("## Proposed tasks")
    report.append("")
    for task in result.get("proposed_tasks", []):
        report.append(f"- [ ] **{task.get('title', '')}**")
        report.append(f"  - Priority: {task.get('priority', '')}")
        report.append(f"  - Estimate: {task.get('estimated_minutes', '')} min")
        report.append(f"  - Project: {task.get('project', '')}")
        report.append(f"  - Reason: {task.get('reason', '')}")
    report.append("")
    report.append("## Reflection questions")
    report.append("")
    for q in result.get("reflection_questions", []):
        report.append(f"- {q}")
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
    report.append("## Risks")
    report.append("")
    for risk in result.get("risks", []):
        report.append(f"- {risk}")
    report.append("")

    report_path = REPORTS_DAILY_DIR / f"{date}.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

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
    proposed_path = PROPOSED_TASKS_DIR / f"{date}.md"
    proposed_path.write_text("\n".join(proposed), encoding="utf-8")

    last_md = []
    last_md.append("# Last LLM Planner Output")
    last_md.append("")
    last_md.append(f"Generated at: {result.get('_metadata', {}).get('generated_at', now_iso())}")
    last_md.append("")
    last_md.append("## Summary")
    last_md.append("")
    last_md.append(result.get("summary", ""))
    last_md.append("")
    last_md.append("## Recommended next action")
    last_md.append("")
    last_md.append(result.get("recommended_next_action", ""))
    last_md.append("")
    LAST_OUTPUT_MD.write_text("\n".join(last_md), encoding="utf-8")


def write_machine_outputs(result):
    tmp = LAST_OUTPUT_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LAST_OUTPUT_JSON)

    ask = result.get("ask_user", {})
    if ask.get("enabled"):
        question_id = f"q-{today()}-{int(time.time())}"

        pending = {
            "question_id": question_id,
            "created_at": now_iso(),
            "question": ask.get("question", ""),
            "reason": ask.get("reason", ""),
            "answer_options": ask.get("answer_options", []),
            "free_text_allowed": ask.get("free_text_allowed", True),
            "source": "llm-planner",
        }

        tmp_q = PENDING_QUESTION_JSON.with_suffix(".tmp")
        tmp_q.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_q.replace(PENDING_QUESTION_JSON)

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
        CURRENT_QUESTION_MD.write_text("\n".join(q_md), encoding="utf-8")
    else:
        CURRENT_QUESTION_MD.write_text(
            "# Current Question\n\nStatus: inactive\nQuestion: none\n",
            encoding="utf-8",
        )

    nudge = result.get("phone_nudge", {})
    if nudge.get("enabled"):
        CURRENT_NUDGE_MD.write_text(
            "\n".join([
                "# Current Nudge",
                "",
                "Status: active",
                f"Urgency: {nudge.get('urgency', 'normal')}",
                f"Message: {nudge.get('message', '')}",
                f"Recommended next action: {result.get('recommended_next_action', '')}",
                f"Updated: {now_iso()}",
                "",
            ]),
            encoding="utf-8",
        )
    else:
        CURRENT_NUDGE_MD.write_text(
            "\n".join([
                "# Current Nudge",
                "",
                "Status: inactive",
                "Message: No current nudge.",
                f"Updated: {now_iso()}",
                "",
            ]),
            encoding="utf-8",
        )


def run_once():
    ensure_dirs()

    context = build_context()
    context_md = context_to_markdown(context)
    write_context(context, context_md)

    result = call_ollama(context_md)

    write_machine_outputs(result)
    write_markdown_outputs(result)

    print("llm-planner completed", flush=True)
    print(f"model={OLLAMA_MODEL}", flush=True)
    print(f"context={TODAY_CONTEXT_MD}", flush=True)
    print(f"report={REPORTS_DAILY_DIR / (today() + '.md')}", flush=True)
    print(f"last_output={LAST_OUTPUT_JSON}", flush=True)


def main():
    try:
        run_once()
    except Exception as error:
        print(f"llm-planner failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
