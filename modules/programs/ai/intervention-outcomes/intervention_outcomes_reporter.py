#!/usr/bin/env python3
"""Materialize deterministic intervention outcome summaries.

This component reads append-only event logs and writes derived review state.

Authority boundary:

    events are evidence
    ai_system.intervention_outcomes summarizes evidence
    this reporter writes derived state/status only

It does not propose, execute, launch apps, call an LLM, mutate recovery state,
or change policy.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from ai_system.intervention_outcomes import build_outcome_stats, summarize_interventions
from ai_system.io_utils import atomic_write_json, atomic_write_text, read_jsonl
from ai_system.time_utils import get_timezone, now as shared_now, now_iso as shared_now_iso


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = get_timezone(os.environ.get("INTERVENTION_OUTCOMES_TIMEZONE", "Europe/Paris"))

DEFAULT_DAYS = int(os.environ.get("INTERVENTION_OUTCOMES_DAYS", "7"))

EVENTS_INTERVENTIONS_DIR = AI_DIR / "events" / "interventions"
EVENTS_ACTIONS_DIR = AI_DIR / "events" / "actions"
EVENTS_RECOVERY_DIR = AI_DIR / "events" / "recovery"

STATE_INTERVENTIONS_DIR = AI_DIR / "state" / "interventions"
CURRENT_JSON = STATE_INTERVENTIONS_DIR / "current.json"
STATS_JSON = STATE_INTERVENTIONS_DIR / "stats.json"
STATUS_MD = STATE_INTERVENTIONS_DIR / "status.md"


def ensure_dirs() -> None:
    STATE_INTERVENTIONS_DIR.mkdir(parents=True, exist_ok=True)


def date_window(days: int) -> list[str]:
    days = max(1, int(days))
    today = shared_now(TIMEZONE).date()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days - 1, -1, -1)
    ]


def read_events_for_dates(directory: Path, dates: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for date in dates:
        events.extend(read_jsonl(directory / f"{date}.jsonl"))
    return events


def compact_latest(summaries: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    latest = list(reversed(summaries[-limit:]))
    out: list[dict[str, Any]] = []

    for item in latest:
        out.append({
            "intervention_id": item.get("intervention_id", ""),
            "intervention_kind": item.get("intervention_kind", ""),
            "target_id": item.get("target_id", ""),
            "target_name": item.get("target_name", ""),
            "outcome": item.get("outcome", ""),
            "reason": item.get("reason", ""),
            "nudge_written": bool(item.get("nudge_written")),
            "user_acted": bool(item.get("user_acted")),
            "recovery_started": bool(item.get("recovery_started")),
            "terminal_recovery": bool(item.get("terminal_recovery")),
            "last_event_epoch": item.get("last_event_epoch", 0),
        })

    return out


def build_report(days: int = DEFAULT_DAYS) -> dict[str, Any]:
    dates = date_window(days)

    intervention_events = read_events_for_dates(EVENTS_INTERVENTIONS_DIR, dates)
    action_events = read_events_for_dates(EVENTS_ACTIONS_DIR, dates)
    recovery_events = read_events_for_dates(EVENTS_RECOVERY_DIR, dates)

    summaries = summarize_interventions(
        intervention_events=intervention_events,
        action_events=action_events,
        recovery_events=recovery_events,
    )
    stats = build_outcome_stats(summaries)

    generated_at = shared_now_iso(TIMEZONE)

    return {
        "schema_version": "intervention_outcome_report.v1",
        "generated_at": generated_at,
        "source": "intervention-outcomes",
        "window": {
            "days": max(1, int(days)),
            "dates": dates,
        },
        "event_counts": {
            "interventions": len(intervention_events),
            "actions": len(action_events),
            "recovery": len(recovery_events),
        },
        "stats": stats,
        "latest": compact_latest(summaries),
        "summaries": summaries,
    }


def write_report(report: dict[str, Any]) -> None:
    ensure_dirs()

    stats = report.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}

    atomic_write_json(CURRENT_JSON, report)
    atomic_write_json(STATS_JSON, stats)

    lines = [
        "# Intervention Outcomes",
        "",
        f"Updated: {report.get('generated_at', '')}",
        f"Window days: `{report.get('window', {}).get('days', '')}`",
        f"Total interventions: `{stats.get('total', 0)}`",
        f"Shown: `{stats.get('shown_count', 0)}`",
        f"Acted: `{stats.get('acted_count', 0)}`",
        f"Started: `{stats.get('started_count', 0)}`",
        f"Terminal: `{stats.get('terminal_count', 0)}`",
        f"Success: `{stats.get('success_count', 0)}`",
        f"Action rate: `{stats.get('action_rate', 0.0)}`",
        f"Start rate: `{stats.get('start_rate', 0.0)}`",
        f"Terminal success rate: `{stats.get('terminal_success_rate', 0.0)}`",
        "",
        "## Outcomes",
        "",
    ]

    by_outcome = stats.get("by_outcome", {})
    if isinstance(by_outcome, dict) and by_outcome:
        for outcome, count in sorted(by_outcome.items()):
            lines.append(f"- `{outcome}`: {count}")
    else:
        lines.append("None.")

    lines.extend([
        "",
        "## Latest",
        "",
    ])

    latest = report.get("latest", [])
    if isinstance(latest, list) and latest:
        for item in latest:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- `{id}` target=`{target}` outcome=`{outcome}` acted=`{acted}` reason=`{reason}`".format(
                    id=item.get("intervention_id", ""),
                    target=item.get("target_id", ""),
                    outcome=item.get("outcome", ""),
                    acted=str(bool(item.get("user_acted"))).lower(),
                    reason=item.get("reason", ""),
                )
            )
    else:
        lines.append("None.")

    lines.extend([
        "",
        "## Stats JSON",
        "",
        "```json",
        json.dumps(stats, indent=2, ensure_ascii=False),
        "```",
        "",
    ])

    atomic_write_text(STATUS_MD, "\n".join(lines))


def run_once(*, days: int = DEFAULT_DAYS, write: bool = False) -> int:
    report = build_report(days)

    if write:
        write_report(report)
        print(json.dumps({
            "wrote": True,
            "current": str(CURRENT_JSON),
            "stats": str(STATS_JSON),
            "status": str(STATUS_MD),
            "total": report.get("stats", {}).get("total", 0),
            "by_outcome": report.get("stats", {}).get("by_outcome", {}),
        }, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "dry_run": True,
            "report": report,
        }, indent=2, ensure_ascii=False))

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize intervention outcomes from append-only event logs")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Number of recent days to read")
    parser.add_argument("--write", action="store_true", help="Write state/interventions/current.json, stats.json, and status.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(run_once(days=args.days, write=args.write))


if __name__ == "__main__":
    main()
