import json
import re
import urllib.error
import urllib.request

from ai_planner.io_utils import now_iso
from ai_planner.result import normalize_result
from ai_planner.schema import RESPONSE_SCHEMA, RESPONSE_SHAPE, SYSTEM_PROMPT


class PlannerOutputQualityError(RuntimeError):
    pass


def strip_json_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(text):
    text = strip_json_fences(text)

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("No JSON object found in model response")


def build_user_prompt(config, context_markdown):
    requested_shape = json.dumps(RESPONSE_SHAPE, indent=2, ensure_ascii=False)
    mode = getattr(config, "planner_mode", "block-plan")

    if mode == "help-now":
        mode_instruction = """Mode: help-now.

You are responding immediately after a user answer or check-in.
The goal is NOT a full plan. The goal is one fast adaptation.

Rules for help-now:
- Prefer one tiny next action.
- If the latest answer says overwhelmed, tired, unclear, too_hard, or not_now, reduce task size.
- For Anki, prefer "5 cards or 5 minutes, whichever comes first" or "10 cards or 10 minutes, whichever comes first".
- Usually do not ask a new question immediately after the user just answered one.
- Do not create more than one proposed task.
- Make the phone nudge highly concrete and under 140 characters.
- If desktop state is on_task, do not treat the user as avoidant merely because AFK status is stale.
"""
    elif mode == "daily-review":
        mode_instruction = """Mode: daily-review.

Create a higher-level review of patterns, friction, and suggested changes.
Do not overfocus on a single moment unless it is clearly important.
"""
    else:
        mode_instruction = """Mode: block-plan.

Create a practical next block plan.
Prefer Anki recovery as the first optimization target.
Do not moralize. Do not shame. Prefer small recovery blocks.
For Anki, prefer limits like "10-20 cards" or "15 minutes, whichever comes first"; avoid large card counts such as 50 unless the context strongly supports it.
"""

    return f"""Analyze the following compact context pack.

Return ONLY one valid JSON object. No Markdown, no code fence, no explanation outside JSON.

Required JSON shape:

{requested_shape}

{mode_instruction}

Decide:
- what is happening now
- whether there is friction or avoidance
- whether to ask one clarifying question
- what the next smallest useful action is
- what short phone nudge should be shown
- what proposed tasks should be created, max 3, each small and concrete
- what reflection questions are useful

The proposed task and recommended next action must agree. If the next action says 15 minutes, do not create a task that says 10 cards unless both are explicitly intended.

Context pack:

{context_markdown}
"""


def quality_warnings(result, raw):
    warnings = []

    metadata_eval_count = raw.get("eval_count")
    try:
        eval_count = int(metadata_eval_count) if metadata_eval_count is not None else None
    except Exception:
        eval_count = None

    summary = str(result.get("summary", "")).strip()
    next_action = str(result.get("recommended_next_action", "")).strip()

    if eval_count is not None and eval_count < 50:
        warnings.append(f"very_short_output: eval_count={eval_count}")

    if len(summary) < 20:
        warnings.append("missing_or_too_short_summary")

    if len(next_action) < 10:
        warnings.append("missing_or_too_short_recommended_next_action")

    return warnings


def is_critical_quality_failure(warnings):
    critical_prefixes = [
        "very_short_output",
        "missing_or_too_short_summary",
        "missing_or_too_short_recommended_next_action",
    ]

    for warning in warnings:
        if any(warning.startswith(prefix) for prefix in critical_prefixes):
            return True

    return False


def format_value_for_mode(mode):
    if mode == "schema":
        return RESPONSE_SCHEMA
    return "json"


def call_ollama_once(config, context_markdown, mode, retry_history):
    user_prompt = build_user_prompt(config, context_markdown)

    payload = {
        "model": config.ollama_model,
        "stream": False,
        "format": format_value_for_mode(mode),
        "keep_alive": config.ollama_keep_alive,
        "options": {
            "temperature": 0,
            "num_ctx": config.ollama_num_ctx,
            "num_predict": config.ollama_num_predict,
        },
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{config.ollama_url}/api/chat",
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "llm-planner/0.5",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=config.ollama_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {error.code}: {body}") from error
    except Exception as error:
        raise RuntimeError(f"Ollama request failed: {error}") from error

    try:
        raw = json.loads(body)
    except Exception as error:
        raise RuntimeError(f"Ollama returned non-JSON HTTP body: {body[:2000]}") from error

    content = raw.get("message", {}).get("content", "")

    if not content:
        raise RuntimeError(f"Ollama response had no message.content: {json.dumps(raw, ensure_ascii=False)[:2000]}")

    try:
        parsed = extract_json_object(content)
    except Exception as error:
        raise PlannerOutputQualityError(
            "Invalid JSON from model.\n"
            f"mode={mode}\n"
            f"error={error}\n"
            f"content={content[:2000]}"
        ) from error

    result = normalize_result(parsed)
    warnings = quality_warnings(result, raw)

    result["_metadata"] = {
        "generated_at": now_iso(config),
        "model": config.ollama_model,
        "ollama_url": config.ollama_url,
        "planner_mode": getattr(config, "planner_mode", "block-plan"),
        "ollama_format": mode,
        "configured_ollama_format": config.ollama_format,
        "num_ctx": config.ollama_num_ctx,
        "num_predict": config.ollama_num_predict,
        "prompt_chars": len(user_prompt),
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "eval_count": raw.get("eval_count"),
        "total_duration": raw.get("total_duration"),
        "done_reason": raw.get("done_reason"),
        "quality_warnings": warnings,
        "retry_history": retry_history,
    }

    if is_critical_quality_failure(warnings):
        raise PlannerOutputQualityError(
            "Low-quality planner output.\n"
            f"mode={mode}\n"
            f"warnings={warnings}\n"
            f"content={content[:2000]}"
        )

    return result


def call_ollama(config, context_markdown):
    first_mode = config.ollama_format if config.ollama_format in {"json", "schema"} else "json"

    attempts = [first_mode]

    # Schema mode is opt-in. On the current CPU-only setup, schema retry can be slow.
    if getattr(config, "enable_schema_retry", False):
        second_mode = "schema" if first_mode == "json" else "json"
        if second_mode not in attempts:
            attempts.append(second_mode)

    retry_history = []
    last_error = None

    for index, mode in enumerate(attempts, start=1):
        try:
            result = call_ollama_once(config, context_markdown, mode, retry_history)
            result["_metadata"]["attempt"] = index
            result["_metadata"]["final_mode"] = mode
            result["_metadata"]["schema_retry_enabled"] = getattr(config, "enable_schema_retry", False)
            return result
        except Exception as error:
            last_error = error
            retry_history.append({
                "attempt": index,
                "mode": mode,
                "error": str(error)[:2000],
            })

    raise PlannerOutputQualityError(
        "Planner attempt failed or produced low-quality output.\n"
        + json.dumps(retry_history, indent=2, ensure_ascii=False)
    ) from last_error
