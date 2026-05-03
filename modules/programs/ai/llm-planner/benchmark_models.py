#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
TIMEZONE = ZoneInfo(os.environ.get("LLM_PLANNER_TIMEZONE", "Europe/Paris"))


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def stamp():
    return now().strftime("%Y%m%d-%H%M%S")


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def call_model(model, timeout, num_ctx, num_predict):
    prompt = """
Return only valid JSON with this exact shape:
{
  "summary": "one sentence",
  "recommended_next_action": "one tiny concrete action with a stop condition",
  "phone_nudge": "under 120 characters"
}

Context:
The user is in an Anki recovery session and answered "overwhelmed".
""".strip()

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": "2m",
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": 0.2,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "llm-planner-benchmark/0.1",
        },
        method="POST",
    )

    started = time.monotonic()

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")

    elapsed = time.monotonic() - started
    data = json.loads(raw)
    content = data.get("response", "")

    valid_json = False
    parsed = None
    parse_error = ""

    try:
        parsed = json.loads(content)
        valid_json = isinstance(parsed, dict)
    except Exception as error:
        parse_error = str(error)

    return {
        "model": model,
        "ok": True,
        "elapsed_seconds": round(elapsed, 3),
        "valid_json": valid_json,
        "parse_error": parse_error,
        "response": parsed if parsed is not None else content[:1000],
        "ollama_metadata": {
            "done": data.get("done"),
            "done_reason": data.get("done_reason"),
            "total_duration": data.get("total_duration"),
            "load_duration": data.get("load_duration"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            "eval_duration": data.get("eval_duration"),
        },
    }


def benchmark_model(model, timeout, num_ctx, num_predict):
    try:
        return call_model(model, timeout, num_ctx, num_predict)
    except urllib.error.HTTPError as error:
        try:
            body = error.read().decode("utf-8")
        except Exception:
            body = ""
        return {
            "model": model,
            "ok": False,
            "error": f"HTTP {error.code}: {body[:1000]}",
        }
    except Exception as error:
        return {
            "model": model,
            "ok": False,
            "error": str(error),
        }


def markdown_report(results):
    lines = []
    lines.append("# Ollama Model Benchmark")
    lines.append("")
    lines.append(f"Generated: {now_iso()}")
    lines.append(f"Ollama URL: `{OLLAMA_URL}`")
    lines.append("")
    lines.append("| Model | OK | Seconds | JSON | Eval count | Done reason |")
    lines.append("|---|---:|---:|---:|---:|---|")

    for item in results:
        meta = item.get("ollama_metadata", {})
        lines.append(
            "| "
            + " | ".join([
                str(item.get("model", "")),
                "yes" if item.get("ok") else "no",
                str(item.get("elapsed_seconds", "")),
                "yes" if item.get("valid_json") else "no",
                str(meta.get("eval_count", "")),
                str(meta.get("done_reason", "")),
            ])
            + " |"
        )

    lines.append("")
    lines.append("## Raw results")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(results, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark local Ollama models for help-now planning.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemma3:4b"],
        help="Ollama model names to benchmark.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--num-ctx", type=int, default=1024)
    parser.add_argument("--num-predict", type=int, default=120)
    return parser.parse_args()


def main():
    args = parse_args()

    results = []
    for model in args.models:
        print(f"benchmarking {model}...", flush=True)
        result = benchmark_model(model, args.timeout, args.num_ctx, args.num_predict)
        results.append(result)

        if result.get("ok"):
            print(
                f"  ok seconds={result.get('elapsed_seconds')} valid_json={result.get('valid_json')}",
                flush=True,
            )
        else:
            print(f"  failed: {result.get('error')}", flush=True)

    report_dir = AI_DIR / "reports" / "benchmarks"
    json_path = report_dir / f"ollama-models-{stamp()}.json"
    md_path = report_dir / f"ollama-models-{stamp()}.md"

    atomic_write_json(json_path, {
        "generated_at": now_iso(),
        "ollama_url": OLLAMA_URL,
        "results": results,
    })
    atomic_write_text(md_path, markdown_report(results))

    print("")
    print(f"json={json_path}")
    print(f"markdown={md_path}")


if __name__ == "__main__":
    main()
