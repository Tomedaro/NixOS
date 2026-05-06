"""Shared Obsidian agent contracts and safety helpers.

This module is deliberately small and pure: no writes, no subprocesses, no
Obsidian edits, no live action queue writes.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_AI_DIR = Path(
    os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")
).expanduser()

PROPOSAL_EXECUTION_POLICY = "proposal_only_no_direct_execution"

TRUNCATED_SUFFIX = "...[truncated]"

DIRECT_EXECUTION_FIELDS = {
    "shell_command",
    "command",
    "exec",
    "executable",
    "desktop_command",
    "launch_task",
    "android_package",
    "uri_to_open",
    "url_to_open",
    "write_path",
    "delete_path",
    "move_path",
    "edits_obsidian_now",
    "writes_live_action_queue",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso_and_epoch() -> tuple[str, int]:
    now = utc_now()
    return now.isoformat(), int(now.timestamp())


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def bounded_text(
    value: Any,
    *,
    max_len: int = 2000,
    suffix: str = TRUNCATED_SUFFIX,
    normalize_newlines: bool = True,
) -> str:
    text = str(value or "").replace("\x00", "")
    if normalize_newlines:
        text = text.replace("\r\n", "\n")
    text = text.strip()

    if len(text) <= max_len:
        return text

    if max_len <= len(suffix):
        return text[:max_len]

    return text[: max_len - len(suffix)].rstrip() + suffix


def bounded_line(value: Any, *, max_len: int = 220) -> str:
    return bounded_text(value, max_len=max_len).replace("\n", " ").strip()


def bounded_list(
    values: Any,
    *,
    max_items: int = 12,
    max_len: int = 160,
) -> list[str]:
    if not isinstance(values, list):
        return []

    out: list[str] = []
    for value in values[:max_items]:
        text = bounded_line(value, max_len=max_len)
        if text:
            out.append(text)
    return out


def slug(value: Any, *, max_len: int = 160, fallback: str = "item") -> str:
    text = bounded_line(value, max_len=max_len).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def read_json_object(
    path: str | Path,
    *,
    missing_ok: bool = False,
    default: dict[str, Any] | None = None,
    object_error: str | None = None,
) -> dict[str, Any]:
    path = Path(path)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if missing_ok:
            return default or {}
        raise
    except Exception:
        if missing_ok:
            return default or {}
        raise

    if not isinstance(data, dict):
        raise ValueError(object_error or f"{path} must contain a JSON object")

    return data


def contains_direct_execution(
    value: Any,
    *,
    fields: set[str] | None = None,
    max_items: int = 16,
    ignore_empty_dict: bool = False,
) -> list[str]:
    forbidden = fields or DIRECT_EXECUTION_FIELDS
    found: list[str] = []

    empty_values: tuple[Any, ...]
    if ignore_empty_dict:
        empty_values = (None, "", [], {})
    else:
        empty_values = (None, "", [])

    def walk(item: Any, prefix: str = "") -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                path = f"{prefix}.{key_text}" if prefix else key_text
                if key_text in forbidden and child not in empty_values:
                    found.append(path)
                walk(child, path)
        elif isinstance(item, list):
            for index, child in enumerate(item[:max_items]):
                walk(child, f"{prefix}[{index}]")

    walk(value)
    return found
