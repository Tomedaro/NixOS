#!/usr/bin/env python3

import argparse
import sys
from dataclasses import replace

from ai_planner.config import PlannerConfig
from ai_planner.context import build_context, context_to_markdown
from ai_planner.fallbacks import help_now_fallback_result
from ai_planner.io_utils import ensure_dirs, now_iso, today
from ai_planner.ollama_client import call_ollama
from ai_planner.outputs import (
    write_context_files,
    write_error_file,
    write_machine_outputs,
    write_markdown_outputs,
    write_planner_status,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Local LLM productivity planner")
    parser.add_argument(
        "--mode",
        choices=["help-now", "block-plan", "daily-review"],
        default=None,
        help="Planner mode",
    )
    return parser.parse_args()


def apply_mode(config, mode):
    if mode is None:
        mode = config.planner_mode

    if mode == "help-now":
        return replace(
            config,
            planner_mode="help-now",
            max_context_chars=min(config.max_context_chars, 1200),
            max_log_chars=min(config.max_log_chars, 200),
            max_jsonl_events=min(config.max_jsonl_events, 5),
            max_tasknotes=min(config.max_tasknotes, 1),
            max_tasknote_chars=min(config.max_tasknote_chars, 300),
            max_policy_chars=min(config.max_policy_chars, 300),
            max_control_chars=min(config.max_control_chars, 700),
            ollama_num_predict=min(config.ollama_num_predict, 180),
            ollama_timeout_seconds=min(config.ollama_timeout_seconds, 45),
            enable_schema_retry=False,
        )

    if mode == "daily-review":
        return replace(
            config,
            planner_mode="daily-review",
            max_context_chars=max(config.max_context_chars, 7000),
            max_log_chars=max(config.max_log_chars, 2500),
            max_jsonl_events=max(config.max_jsonl_events, 80),
            max_tasknotes=max(config.max_tasknotes, 12),
            ollama_num_predict=max(config.ollama_num_predict, 1200),
            ollama_timeout_seconds=max(config.ollama_timeout_seconds, 900),
            enable_schema_retry=False,
        )

    return replace(config, planner_mode="block-plan", enable_schema_retry=False)


def status_warnings_from_result(config, result):
    warnings = []
    metadata = result.get("_metadata", {})

    eval_count = metadata.get("eval_count")
    prompt_eval_count = metadata.get("prompt_eval_count")
    done_reason = metadata.get("done_reason")

    for warning in metadata.get("quality_warnings", []) or []:
        warnings.append(str(warning))

    try:
        eval_count_int = int(eval_count) if eval_count is not None else None
    except Exception:
        eval_count_int = None

    try:
        prompt_eval_count_int = int(prompt_eval_count) if prompt_eval_count is not None else None
    except Exception:
        prompt_eval_count_int = None

    if eval_count_int is not None and eval_count_int < 50:
        warnings.append(
            f"Very short model output: eval_count={eval_count_int}. Output may be default-filled or low quality."
        )

    if prompt_eval_count_int is not None and prompt_eval_count_int >= config.ollama_num_ctx:
        warnings.append(
            f"Prompt likely hit context limit: prompt_eval_count={prompt_eval_count_int}, num_ctx={config.ollama_num_ctx}."
        )

    if done_reason and done_reason != "stop":
        warnings.append(f"Model ended with done_reason={done_reason}.")

    return sorted(set(warnings))


def run_once(mode=None):
    config = PlannerConfig.from_env()
    config = apply_mode(config, mode)
    config = replace(config, generated_at=now_iso(config))

    ensure_dirs(config)

    write_planner_status(
        config,
        status="running",
        metadata={
            "started_at": now_iso(config),
            "model": config.ollama_model,
            "planner_mode": config.planner_mode,
        },
    )

    context = build_context(config)
    context_md = context_to_markdown(config, context)
    write_context_files(config, context, context_md)

    try:
        result = call_ollama(config, context_md)
    except Exception as error:
        write_error_file(config, error)

        if config.planner_mode == "help-now":
            result = help_now_fallback_result(config, context, error)
            warnings = [
                "LLM help-now failed or timed out; deterministic fallback output was written.",
                str(error)[:500],
            ]

            write_machine_outputs(config, result)
            write_markdown_outputs(config, result)
            write_planner_status(
                config,
                status="completed_fallback",
                metadata=result.get("_metadata", {}),
                warnings=warnings,
            )

            print("llm-planner help-now used deterministic fallback", flush=True)
            print(f"mode={config.planner_mode}", flush=True)
            print(f"error={error}", flush=True)
            print(f"context={config.context_dir / 'today.md'}", flush=True)
            print(f"status={config.state_llm_dir / 'planner-status.md'}", flush=True)
            return

        write_planner_status(
            config,
            status="failed",
            metadata={
                "failed_at": now_iso(config),
                "model": config.ollama_model,
                "planner_mode": config.planner_mode,
                "ollama_format": config.ollama_format,
                "context_chars": len(context_md),
            },
            error=str(error),
        )

        print("llm-planner failed but preserved previous outputs", flush=True)
        print(f"mode={config.planner_mode}", flush=True)
        print(f"error={error}", flush=True)
        print(f"context={config.context_dir / 'today.md'}", flush=True)
        print(f"status={config.state_llm_dir / 'planner-status.md'}", flush=True)
        return

    warnings = status_warnings_from_result(config, result)

    write_machine_outputs(config, result)
    write_markdown_outputs(config, result)

    status = "completed_with_warning" if warnings else "completed"
    write_planner_status(
        config,
        status=status,
        metadata=result.get("_metadata", {}),
        warnings=warnings,
    )

    print("llm-planner completed", flush=True)
    print(f"mode={config.planner_mode}", flush=True)
    print(f"model={config.ollama_model}", flush=True)
    print(f"format={result.get('_metadata', {}).get('final_mode', config.ollama_format)}", flush=True)
    print(f"context={config.context_dir / 'today.md'}", flush=True)
    print(f"context_chars={len(context_md)}", flush=True)
    print(f"report={config.reports_daily_dir / (today(config) + '.md')}", flush=True)
    print(f"last_output={config.state_llm_dir / 'last-output.json'}", flush=True)


def main():
    args = parse_args()

    try:
        run_once(args.mode)
    except Exception as error:
        print(f"llm-planner crashed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
