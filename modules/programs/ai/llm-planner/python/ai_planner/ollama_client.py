import json
import re
import urllib.error
import urllib.request

from ai_planner.io_utils import now_iso
from ai_planner.result import fallback_result, normalize_result
from ai_planner.schema import RESPONSE_SCHEMA, RESPONSE_SHAPE, SYSTEM_PROMPT


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


def call_ollama(config, context_markdown):
    requested_shape = json.dumps(RESPONSE_SHAPE, indent=2, ensure_ascii=False)

    user_prompt = f"""Analyze the following compact context pack.

Return ONLY one valid JSON object. No Markdown, no code fence, no explanation outside JSON.

Required JSON shape:

{requested_shape}

Decide:
- what is happening now
- whether there is friction or avoidance
- whether to ask one clarifying question
- what the next smallest useful action is
- what short phone nudge should be shown
- what proposed tasks should be created, max 3, each small and concrete
- what reflection questions are useful

Prefer Anki recovery as the first optimization target.
Do not moralize. Do not shame. Prefer small recovery blocks.
The proposed task and recommended next action must agree. If the next action says 15 minutes, do not create a task that says 10 cards unless both are explicitly intended.

Context pack:

{context_markdown}
"""

    format_value = RESPONSE_SCHEMA if config.ollama_format == "schema" else "json"

    payload = {
        "model": config.ollama_model,
        "stream": False,
        "format": format_value,
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
            "User-Agent": "llm-planner/0.3",
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
        parsed = fallback_result(
            reason=f"Invalid JSON from model: {error}",
            raw_content=content,
            error_kind="invalid_model_json",
        )

    result = normalize_result(parsed)
    result["_metadata"] = {
        "generated_at": now_iso(config),
        "model": config.ollama_model,
        "ollama_url": config.ollama_url,
        "ollama_format": config.ollama_format,
        "num_ctx": config.ollama_num_ctx,
        "num_predict": config.ollama_num_predict,
        "prompt_chars": len(user_prompt),
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "eval_count": raw.get("eval_count"),
        "total_duration": raw.get("total_duration"),
        "done_reason": raw.get("done_reason"),
    }

    return result
