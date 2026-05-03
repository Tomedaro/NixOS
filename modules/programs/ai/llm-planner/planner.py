#!/usr/bin/env python3

import sys

from ai_planner.config import PlannerConfig
from ai_planner.context import build_context, context_to_markdown
from ai_planner.io_utils import ensure_dirs, now_iso, today
from ai_planner.ollama_client import call_ollama
from ai_planner.outputs import (
    write_context_files,
    write_error_file,
    write_machine_outputs,
    write_markdown_outputs,
)
from ai_planner.result import fallback_result, normalize_result


def run_once():
    config = PlannerConfig.from_env()
    object.__setattr__(config, "generated_at", now_iso(config))

    ensure_dirs(config)

    context = build_context(config)
    context_md = context_to_markdown(config, context)
    write_context_files(config, context, context_md)

    try:
        result = call_ollama(config, context_md)
    except Exception as error:
        write_error_file(config, error)
        result = normalize_result(fallback_result(reason=error))
        result["_metadata"] = {
            "generated_at": now_iso(config),
            "model": config.ollama_model,
            "ollama_url": config.ollama_url,
            "ollama_format": config.ollama_format,
            "num_ctx": config.ollama_num_ctx,
            "num_predict": config.ollama_num_predict,
            "prompt_chars": len(context_md),
            "planner_error": str(error),
        }

    write_machine_outputs(config, result)
    write_markdown_outputs(config, result)

    print("llm-planner completed", flush=True)
    print(f"model={config.ollama_model}", flush=True)
    print(f"format={config.ollama_format}", flush=True)
    print(f"context={config.context_dir / 'today.md'}", flush=True)
    print(f"context_chars={len(context_md)}", flush=True)
    print(f"report={config.reports_daily_dir / (today(config) + '.md')}", flush=True)
    print(f"last_output={config.state_llm_dir / 'last-output.json'}", flush=True)


def main():
    try:
        run_once()
    except Exception as error:
        print(f"llm-planner failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
