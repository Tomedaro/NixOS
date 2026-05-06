"""Capture explicit Obsidian proposal decisions without executing them.

This module is the approval boundary after Obsidian intent planning. It writes
bounded, auditable proposal decisions to a dedicated Obsidian inbox, not to the
live action bridge queue.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_system.io_utils import atomic_write_json, atomic_write_text

DEFAULT_AI_DIR = Path(
    os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")
).expanduser()

ALLOWED_DECISIONS = {
    "approve_proposal",
    "reject_proposal",
    "revise_proposal",
}

MAX_TEXT = 2000
MAX_ID = 160
MAX_KIND = 80
MAX_REASON_CODES = 12


def now_iso_and_epoch() -> tuple[str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat(), int(now.timestamp())


def bounded_text(value: Any, *, max_len: int = MAX_TEXT) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def bounded_list(values: Any, *, max_items: int = MAX_REASON_CODES) -> list[str]:
    if not isinstance(values, list):
        return []

    out: list[str] = []
    for value in values[:max_items]:
        text = bounded_text(value, max_len=120)
        if text:
            out.append(text)
    return out


def slug(value: Any) -> str:
    text = bounded_text(value, max_len=MAX_ID).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or "proposal"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def normalize_proposal_action(payload: dict[str, Any]) -> dict[str, Any]:
    timestamp, epoch = now_iso_and_epoch()

    decision = bounded_text(
        payload.get("decision") or payload.get("action"), max_len=80
    )
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(
            f"unsupported proposal decision {decision!r}; expected one of "
            f"{sorted(ALLOWED_DECISIONS)}"
        )

    proposal_id = bounded_text(payload.get("proposal_id"), max_len=MAX_ID)
    if not proposal_id:
        raise ValueError("proposal_id is required")

    proposal_kind = bounded_text(
        payload.get("proposal_kind") or "unknown", max_len=MAX_KIND
    )

    return {
        "schema_version": "obsidian_proposal_action.v1",
        "timestamp": timestamp,
        "timestamp_epoch": epoch,
        "source": "obsidian",
        "surface": bounded_text(payload.get("surface") or "obsidian", max_len=80),
        "decision": decision,
        "proposal_id": proposal_id,
        "proposal_kind": proposal_kind,
        "approved": decision == "approve_proposal",
        "rejected": decision == "reject_proposal",
        "revision_requested": decision == "revise_proposal",
        "user_message_preview": bounded_text(
            payload.get("message") or payload.get("user_message")
        ),
        "reason_codes": bounded_list(payload.get("reason_codes")),
        "requested_changes": bounded_text(payload.get("requested_changes")),
        "proposal_summary": bounded_text(payload.get("proposal_summary")),
        "origin_intent_id": bounded_text(
            payload.get("origin_intent_id"), max_len=MAX_ID
        ),
        "executes_now": False,
        "writes_live_action_queue": False,
        "requires_downstream_bridge": decision == "approve_proposal",
    }


def status_markdown(action: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Obsidian Proposal Action",
            "",
            f"Updated: {action['timestamp']}",
            f"Decision: `{action['decision']}`",
            f"Proposal ID: `{action['proposal_id']}`",
            f"Proposal kind: `{action['proposal_kind']}`",
            f"Approved: `{str(action['approved']).lower()}`",
            f"Executes now: `{str(action['executes_now']).lower()}`",
            f"Writes live action queue: `{str(action['writes_live_action_queue']).lower()}`",
            "",
            "## User message preview",
            "",
            action.get("user_message_preview") or "_none_",
            "",
        ]
    )


def write_proposal_action(
    payload: dict[str, Any],
    *,
    ai_dir: str | Path | None = None,
) -> dict[str, Any]:
    ai_root = Path(ai_dir or DEFAULT_AI_DIR).expanduser()
    action = normalize_proposal_action(payload)

    inbox = ai_root / "inbox" / "obsidian" / "actions"
    filename = (
        f"{action['timestamp_epoch']}_{action['decision']}_"
        f"{slug(action['proposal_id'])}.json"
    )

    action_path = inbox / filename
    latest_json = ai_root / "state" / "obsidian" / "latest-proposal-action.json"
    latest_md = ai_root / "state" / "obsidian" / "latest-proposal-action.md"

    atomic_write_json(action_path, action)
    atomic_write_json(latest_json, action)
    atomic_write_text(latest_md, status_markdown(action))

    return {
        **action,
        "written_path": str(action_path),
        "latest_json_path": str(latest_json),
        "latest_markdown_path": str(latest_md),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record an explicit Obsidian proposal decision"
    )
    parser.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    parser.add_argument("--input", required=True, help="JSON payload file")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = read_json(Path(args.input))

    if args.write:
        result = write_proposal_action(payload, ai_dir=args.ai_dir)
    else:
        result = normalize_proposal_action(payload)

    if args.dry_run or not args.write:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
