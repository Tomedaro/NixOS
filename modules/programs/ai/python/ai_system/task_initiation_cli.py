"""Local JSON test and diagnostic harness for the task-initiation kernel.

Thin seven-command CLI: init, ingest-stuck, show, list-active, respond,
reconcile, check-db. Production uses real wall-clock time; tests inject
dependencies through the kernel constructor or the in-file --cli-driver.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai_system.task_initiation_kernel import (
    KernelPolicy,
    OperationResult,
    ResolutionInput,
    TaskInitiationKernel,
    load_resolution_input,
    wall_clock_epoch,
)
from ai_system.task_initiation_store import (
    KernelBusyError,
    KernelCorruptionError,
    KernelNotFoundError,
    KernelRefusalError,
    KernelStorageError,
    default_state_dir,
)

MAX_INPUT_BYTES = 65536
MAX_RESOLUTION_BYTES = 16384


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({
    "label",
    "summary",
    "instruction",
    "completion",
    "title",
    "task_label",
    "description",
    "task_description",
    "detail",
    "response",
    "response_record",
    "card",
    "context",
    "proposal",
    "blocker",
    "tiny_start",
    "actions",
    "dismiss_action",
    "disclosed_facts",
    "provenance",
    "message_reservations",
    "resolved_task",
    "revisions",
    "accepted_responses",
    "aggregate_json",
    "payload_json",
    "result_json",
})

_SENSITIVE_STRING_KEYS = frozenset({
    "label", "summary", "instruction", "completion", "title",
    "task_label", "description", "task_description", "detail",
})


def _redact(obj: Any) -> Any:
    """Recursively redact sensitive content from JSON-serializable data."""
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _SENSITIVE_STRING_KEYS and isinstance(v, str):
                result[k] = "[redacted]"
            elif k in _SENSITIVE_KEYS:
                result[k] = "[redacted]"
            else:
                result[k] = _redact(v)
        return result
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _redact_absolute_paths(obj: Any) -> Any:
    """Remove absolute paths from output."""
    if isinstance(obj, str) and obj.startswith("/"):
        return "[redacted path]"
    if isinstance(obj, dict):
        return {k: _redact_absolute_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_absolute_paths(item) for item in obj]
    return obj


def _redact_result(data: Any) -> Any:
    """Apply default redaction to output data."""
    data = _redact(data)
    data = _redact_absolute_paths(data)
    return data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_input(args: argparse.Namespace) -> bytes:
    """Read main input from file or stdin, capped at max_input_bytes."""
    if args.input == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            data = Path(args.input).read_bytes()
        except OSError as exc:
            raise SystemExit(_error(2, f"cannot read input: {exc}"))

    if len(data) > MAX_INPUT_BYTES:
        raise SystemExit(_error(2, f"input exceeds {MAX_INPUT_BYTES} bytes"))

    return data


def _parse_json(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SystemExit(_error(2, f"{label}: invalid JSON: {exc}"))


def _load_resolution(args: argparse.Namespace) -> ResolutionInput | None:
    if args.resolution_input is None:
        return None
    try:
        return load_resolution_input(
            Path(args.resolution_input), max_bytes=MAX_RESOLUTION_BYTES
        )
    except (KernelRefusalError, KernelStorageError) as exc:
        raise SystemExit(_error(2, str(exc)))


def _error(code: int, message: str) -> int:
    obj = {"ok": False, "error": str(message)}
    json.dump(obj, sys.stderr, sort_keys=True)
    sys.stderr.write("\n")
    sys.stderr.flush()
    return code


def _success(data: Any, args: argparse.Namespace) -> int:
    if not args.include_sensitive:
        data = _redact_result(data)
    json.dump(data, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _cmd_init(kernel: TaskInitiationKernel, args: argparse.Namespace) -> int:
    result = kernel.initialize()
    return _success(result, args)


def _cmd_ingest_stuck(
    kernel: TaskInitiationKernel, args: argparse.Namespace
) -> int:
    data = _read_input(args)
    stuck = _parse_json(data, "stuck")
    if not isinstance(stuck, dict):
        return _error(2, "stuck input must be a JSON object")

    resolution = _load_resolution(args)

    try:
        op = kernel.ingest_stuck(stuck, resolution=resolution)
    except (KernelRefusalError, KernelNotFoundError) as exc:
        return _error(4, str(exc))
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelBusyError:
        return _error(6, "database is locked")
    except KernelStorageError as exc:
        return _error(7, str(exc))

    output = {
        "ok": True,
        "replay": op.replay,
        "result": op.result,
    }
    return _success(output, args)


def _cmd_show(kernel: TaskInitiationKernel, args: argparse.Namespace) -> int:
    try:
        result = kernel.show(args.event_id, include_sensitive=args.include_sensitive)
    except KernelNotFoundError as exc:
        return _error(3, str(exc))
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelStorageError as exc:
        return _error(7, str(exc))

    return _success(result, args)


def _cmd_list_active(
    kernel: TaskInitiationKernel, args: argparse.Namespace
) -> int:
    try:
        results = kernel.list_active(include_sensitive=args.include_sensitive)
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelStorageError as exc:
        return _error(7, str(exc))

    return _success(results, args)


def _cmd_respond(kernel: TaskInitiationKernel, args: argparse.Namespace) -> int:
    data = _read_input(args)
    response = _parse_json(data, "response")
    if not isinstance(response, dict):
        return _error(2, "response input must be a JSON object")

    resolution = _load_resolution(args)

    try:
        op = kernel.respond(response, resolution=resolution)
    except (KernelRefusalError, KernelNotFoundError) as exc:
        return _error(4, str(exc))
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelBusyError:
        return _error(6, "database is locked")
    except KernelStorageError as exc:
        return _error(7, str(exc))

    output = {
        "ok": True,
        "replay": op.replay,
        "result": op.result,
    }
    return _success(output, args)


def _cmd_reconcile(kernel: TaskInitiationKernel, args: argparse.Namespace) -> int:
    try:
        result = kernel.reconcile()
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelBusyError:
        return _error(6, "database is locked")
    except KernelStorageError as exc:
        return _error(7, str(exc))

    return _success(result, args)


def _cmd_check_db(kernel: TaskInitiationKernel, args: argparse.Namespace) -> int:
    try:
        result = kernel.check_database()
    except KernelCorruptionError as exc:
        return _error(5, str(exc))
    except KernelStorageError as exc:
        return _error(7, str(exc))

    return _success(result, args)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ai_system.task_initiation_cli",
        description="Local task-initiation kernel test and diagnostic harness.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Absolute application state directory (default: XDG_STATE_HOME)",
    )
    parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Include sensitive task/response/context text in output",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create/migrate/validate the SQLite database")

    p = sub.add_parser("ingest-stuck", help="Execute atomic Stuck ingestion")
    p.add_argument("--input", type=str, required=True, help="JSON file or '-' for stdin")
    p.add_argument(
        "--resolution-input", type=str, default=None,
        help="Optional task resolution fixture JSON file",
    )

    p = sub.add_parser("show", help="Read-only redacted aggregate summary")
    p.add_argument("event_id", type=str, help="Event ID to show")

    sub.add_parser("list-active", help="Read-only redacted nonterminal summaries")

    p = sub.add_parser("respond", help="Execute atomic Response processing")
    p.add_argument("--input", type=str, required=True, help="JSON file or '-' for stdin")
    p.add_argument(
        "--resolution-input", type=str, default=None,
        help="Optional task resolution fixture JSON file",
    )

    sub.add_parser("reconcile", help="Advance all nonterminal interaction deadlines")

    sub.add_parser("check-db", help="Read-only PRAGMA structure/integrity checks")

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# State dir resolution
# ---------------------------------------------------------------------------


def resolve_cli_state_dir(cli_arg: Path | None) -> Path:
    if cli_arg is not None:
        if not cli_arg.is_absolute():
            sys.exit(_error(2, "--state-dir must be an absolute path"))
        return cli_arg
    return default_state_dir()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

RUNTIME_BUSY_TIMEOUT_SECONDS = 5.0

_COMMAND_MAP = {
    "init": _cmd_init,
    "ingest-stuck": _cmd_ingest_stuck,
    "show": _cmd_show,
    "list-active": _cmd_list_active,
    "respond": _cmd_respond,
    "reconcile": _cmd_reconcile,
    "check-db": _cmd_check_db,
}


def execute(args: argparse.Namespace, kernel: TaskInitiationKernel) -> int:
    handler = _COMMAND_MAP.get(args.command)
    if handler is None:
        return _error(2, f"unknown command: {args.command}")
    return handler(kernel, args)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    kernel = TaskInitiationKernel(
        state_dir=resolve_cli_state_dir(args.state_dir),
        clock=wall_clock_epoch,
        busy_timeout_seconds=RUNTIME_BUSY_TIMEOUT_SECONDS,
    )
    return execute(args, kernel)


if __name__ == "__main__":
    sys.exit(main())
