#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "/home/daniil/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = ZoneInfo(os.environ.get("RECOVERY_MANAGER_TIMEZONE", "Europe/Paris"))

OPEN_GRACE_SECONDS = int(os.environ.get("RECOVERY_OPEN_GRACE_SECONDS", "30"))
NO_LAUNCH_EXPIRE_SECONDS = int(os.environ.get("RECOVERY_NO_LAUNCH_EXPIRE_SECONDS", "900"))
RAPID_ABORT_SECONDS = int(os.environ.get("RECOVERY_RAPID_ABORT_SECONDS", "90"))
SUCCESS_DWELL_SECONDS = int(os.environ.get("RECOVERY_SUCCESS_DWELL_SECONDS", "300"))

STATE_RECOVERY_DIR = AI_DIR / "state" / "recovery"
RECOVERY_CURRENT_JSON = STATE_RECOVERY_DIR / "current.json"
RECOVERY_STATUS_JSON = STATE_RECOVERY_DIR / "status.json"
RECOVERY_STATUS_MD = STATE_RECOVERY_DIR / "status.md"

EVENTS_PHONE_DIR = AI_DIR / "events" / "phone"
EVENTS_RECOVERY_DIR = AI_DIR / "events" / "recovery"


TARGET_EVENT_NAMES = {
    "anki": {
        "opened": {"opened_ankidroid"},
        "closed": {"closed_ankidroid"},
    },
}


TERMINAL_STATUSES = {
    "possible_success",
    "possible_abort",
    "expired",
    "cancelled",
    "completed",
}


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


def current_epoch():
    return int(time.time())


def ensure_dirs():
    for path in [
        STATE_RECOVERY_DIR,
        EVENTS_RECOVERY_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(str(text), encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path, default=None):
    if default is None:
        default = {}

    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
    except Exception as error:
        return {"error": f"error reading {path}: {error}"}

    return default


def append_jsonl(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def read_jsonl(path):
    if not path.exists():
        return []

    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                out.append(item)
    except Exception as error:
        print(f"failed to read {path}: {error}", file=sys.stderr, flush=True)

    return out


def parse_epoch_from_iso(value):
    if not value:
        return 0

    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def event_epoch(event):
    try:
        return int(float(event.get("timestamp_epoch")))
    except Exception:
        pass

    return parse_epoch_from_iso(event.get("timestamp") or event.get("processed_at"))


def event_name(event):
    return str(event.get("event") or event.get("event_type") or event.get("type") or "").strip()


def compact_event(event):
    if not isinstance(event, dict):
        return {}

    return {
        "event": event_name(event),
        "timestamp": event.get("timestamp", ""),
        "timestamp_epoch": event_epoch(event),
        "time": event.get("time", ""),
        "raw_file": event.get("raw_file", ""),
        "message": event.get("message", ""),
    }


def recovery_start_epoch(recovery):
    last_event = recovery.get("last_event", {})
    if isinstance(last_event, dict):
        epoch = event_epoch(last_event)
        if epoch:
            return epoch

    return parse_epoch_from_iso(recovery.get("started_at"))


def target_id_for(recovery):
    target = recovery.get("target", {})
    if not isinstance(target, dict):
        target = {}
    return str(target.get("target_id") or "").strip().lower()


def target_event_names(target_id):
    return TARGET_EVENT_NAMES.get(target_id, {"opened": set(), "closed": set()})


def phone_events_for_dates(start_epoch, end_epoch=None):
    if start_epoch <= 0:
        return []

    if end_epoch is None:
        end_epoch = current_epoch()

    start_date = datetime.fromtimestamp(start_epoch, tz=TIMEZONE).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(end_epoch, tz=TIMEZONE).strftime("%Y-%m-%d")
    dates = sorted({start_date, end_date, today()})

    events = []
    for date in dates:
        events.extend(read_jsonl(EVENTS_PHONE_DIR / f"{date}.jsonl"))

    events = [
        event for event in events
        if start_epoch - 5 <= event_epoch(event) <= end_epoch
    ]
    events.sort(key=event_epoch)
    return events


def relevant_events(recovery):
    target_id = target_id_for(recovery)
    names = target_event_names(target_id)
    wanted = set(names.get("opened", set())) | set(names.get("closed", set()))
    start_epoch = recovery_start_epoch(recovery)

    observation_end = min(current_epoch(), start_epoch + NO_LAUNCH_EXPIRE_SECONDS)

    events = []
    for event in phone_events_for_dates(start_epoch, observation_end):
        if event_name(event) in wanted:
            events.append(event)

    return events


def build_dwell(events, opened_names, closed_names, start_epoch):
    intervals = []
    open_start = None
    last_open_event = None
    last_close_event = None
    flapping_count = 0

    for event in events:
        name = event_name(event)
        epoch = event_epoch(event)

        if epoch < start_epoch:
            continue

        if name in opened_names:
            if open_start is None:
                open_start = epoch
                last_open_event = event
            elif last_close_event is not None:
                close_epoch = event_epoch(last_close_event)
                if epoch - close_epoch <= OPEN_GRACE_SECONDS:
                    flapping_count += 1
                else:
                    intervals.append({
                        "start": open_start,
                        "end": close_epoch,
                        "duration_seconds": max(0, close_epoch - open_start),
                        "opened_event": compact_event(last_open_event),
                        "closed_event": compact_event(last_close_event),
                    })
                    open_start = epoch
                    last_open_event = event
                last_close_event = None
            else:
                flapping_count += 1

        elif name in closed_names:
            if open_start is not None:
                last_close_event = event
            else:
                flapping_count += 1

    if open_start is not None:
        if last_close_event is not None:
            close_epoch = event_epoch(last_close_event)
            intervals.append({
                "start": open_start,
                "end": close_epoch,
                "duration_seconds": max(0, close_epoch - open_start),
                "opened_event": compact_event(last_open_event),
                "closed_event": compact_event(last_close_event),
            })
        else:
            intervals.append({
                "start": open_start,
                "end": current_epoch(),
                "duration_seconds": max(0, current_epoch() - open_start),
                "opened_event": compact_event(last_open_event),
                "closed_event": {},
                "still_open": True,
            })

    total_dwell = sum(int(item.get("duration_seconds", 0)) for item in intervals)
    longest_dwell = max([int(item.get("duration_seconds", 0)) for item in intervals] or [0])

    return {
        "intervals": intervals,
        "total_observed_dwell_seconds": total_dwell,
        "longest_observed_dwell_seconds": longest_dwell,
        "flapping_count": flapping_count,
        "event_count": len(events),
        "first_open_event": compact_event(next((e for e in events if event_name(e) in opened_names), {})),
        "last_event": compact_event(events[-1]) if events else {},
    }


def classify(recovery):
    old_status = str(recovery.get("status") or "").strip().lower()

    if old_status in TERMINAL_STATUSES:
        return recovery, None, "terminal_status_unchanged"

    start_epoch = recovery_start_epoch(recovery)
    if start_epoch <= 0:
        return recovery, None, "missing_start_time"

    target_id = target_id_for(recovery)
    names = target_event_names(target_id)
    opened_names = set(names.get("opened", set()))
    closed_names = set(names.get("closed", set()))

    if not opened_names:
        return recovery, None, f"unknown_recovery_target:{target_id}"

    events = relevant_events(recovery)
    dwell = build_dwell(events, opened_names, closed_names, start_epoch)

    age = current_epoch() - start_epoch
    saw_open = bool(dwell.get("first_open_event", {}).get("event"))
    total_dwell = int(dwell.get("total_observed_dwell_seconds", 0))
    longest_dwell = int(dwell.get("longest_observed_dwell_seconds", 0))
    event_count = int(dwell.get("event_count", 0))
    flapping_count = int(dwell.get("flapping_count", 0))

    rapid_exit_detected = bool(saw_open and total_dwell < RAPID_ABORT_SECONDS and age >= RAPID_ABORT_SECONDS)

    if saw_open and total_dwell >= SUCCESS_DWELL_SECONDS:
        new_status = "possible_success"
        reason = "observed_target_dwell_reached_success_threshold"
    elif not saw_open and age >= NO_LAUNCH_EXPIRE_SECONDS:
        new_status = "expired"
        reason = "no_target_open_observed_before_expiry"
    elif saw_open and age >= NO_LAUNCH_EXPIRE_SECONDS:
        new_status = "possible_abort"
        reason = "observation_window_ended_with_insufficient_target_dwell"
    elif saw_open:
        new_status = "observing"
        if rapid_exit_detected:
            reason = "rapid_exit_seen_but_waiting_until_observation_window_ends"
        else:
            reason = "target_seen_waiting_for_more_evidence"
    else:
        new_status = "active"
        reason = "waiting_for_target_open"

    if flapping_count >= 2:
        evidence_quality = "weak_flapping"
    elif event_count == 0:
        evidence_quality = "none_yet"
    else:
        evidence_quality = "normal"

    lifecycle = {
        "target_id": target_id,
        "target_opened": saw_open,
        "event_count": event_count,
        "flapping_count": flapping_count,
        "evidence_quality": evidence_quality,
        "rapid_exit_detected": rapid_exit_detected,
        "rapid_exit_threshold_seconds": RAPID_ABORT_SECONDS,
        "total_observed_dwell_seconds": total_dwell,
        "longest_observed_dwell_seconds": longest_dwell,
        "open_grace_seconds": OPEN_GRACE_SECONDS,
        "observation_window_seconds": NO_LAUNCH_EXPIRE_SECONDS,
        "observation_end_epoch": start_epoch + NO_LAUNCH_EXPIRE_SECONDS,
        "first_open_event": dwell.get("first_open_event", {}),
        "last_event": dwell.get("last_event", {}),
        "intervals": dwell.get("intervals", []),
    }

    recovery["lifecycle"] = lifecycle
    recovery["updated_at"] = now_iso()

    status_changed = new_status != old_status
    recovery["status"] = new_status
    recovery["classification"] = {
        "status": new_status,
        "previous_status": old_status,
        "reason": reason,
        "classified_at": recovery["updated_at"],
        "thresholds": {
            "open_grace_seconds": OPEN_GRACE_SECONDS,
            "no_launch_expire_seconds": NO_LAUNCH_EXPIRE_SECONDS,
            "rapid_abort_seconds": RAPID_ABORT_SECONDS,
            "success_dwell_seconds": SUCCESS_DWELL_SECONDS,
        },
    }

    if not status_changed:
        return recovery, None, reason

    target = recovery.get("target", {})
    if not isinstance(target, dict):
        target = {}

    event = {
        "schema_version": "event.v1",
        "source": "recovery-manager",
        "device": "local",
        "event": f"recovery_{new_status}",
        "event_type": f"recovery_{new_status}",
        "timestamp": recovery["updated_at"],
        "timestamp_epoch": current_epoch(),
        "date": today(),
        "time": now().strftime("%H:%M:%S"),
        "processed_at": recovery["updated_at"],
        "recovery_id": recovery.get("recovery_id", ""),
        "target_id": target_id,
        "target_name": target.get("name", ""),
        "previous_status": old_status,
        "status": new_status,
        "reason": reason,
        "evidence_quality": evidence_quality,
        "total_observed_dwell_seconds": total_dwell,
        "longest_observed_dwell_seconds": longest_dwell,
        "event_count": event_count,
        "flapping_count": flapping_count,
        "rapid_exit_detected": rapid_exit_detected,
    }

    recovery["last_lifecycle_event"] = event
    return recovery, event, reason


def write_status(recovery, message):
    data = {
        "updated_at": now_iso(),
        "status": recovery.get("status", "missing"),
        "message": message,
        "recovery_id": recovery.get("recovery_id", ""),
        "target": recovery.get("target", {}),
        "goal": recovery.get("goal", {}),
        "classification": recovery.get("classification", {}),
        "lifecycle": recovery.get("lifecycle", {}),
    }

    atomic_write_json(RECOVERY_STATUS_JSON, data)

    target = data.get("target", {})
    goal = data.get("goal", {})
    classification = data.get("classification", {})
    lifecycle = data.get("lifecycle", {})

    lines = [
        "# Recovery Status",
        "",
        f"Updated: {data['updated_at']}",
        f"Status: `{data['status']}`",
        f"Message: {message}",
        f"Recovery ID: `{data.get('recovery_id', '')}`",
        f"Target: {target.get('name') or target.get('target_id', '')}",
        f"Goal: {goal.get('text', '')}",
        "",
    ]

    if classification:
        lines.extend([
            "## Classification",
            "",
            f"Previous status: `{classification.get('previous_status', '')}`",
            f"Reason: `{classification.get('reason', '')}`",
            "",
        ])

    if lifecycle:
        lines.extend([
            "## Lifecycle",
            "",
            f"Evidence quality: `{lifecycle.get('evidence_quality', '')}`",
            f"Event count: `{lifecycle.get('event_count', 0)}`",
            f"Flapping count: `{lifecycle.get('flapping_count', 0)}`",
            f"Total observed dwell seconds: `{lifecycle.get('total_observed_dwell_seconds', 0)}`",
            f"Longest observed dwell seconds: `{lifecycle.get('longest_observed_dwell_seconds', 0)}`",
            "",
            "```json",
            json.dumps(lifecycle, indent=2, ensure_ascii=False),
            "```",
            "",
        ])

    atomic_write_text(RECOVERY_STATUS_MD, "\n".join(lines))


def run_once(dry_run=False):
    ensure_dirs()

    recovery = read_json(RECOVERY_CURRENT_JSON, {})
    if not recovery:
        write_status({}, "no recovery state")
        print("no recovery state")
        return 0

    updated, event, reason = classify(recovery)

    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "reason": reason,
            "event": event,
            "recovery": updated,
        }, indent=2, ensure_ascii=False))
        return 0

    if event is None and reason == "terminal_status_unchanged":
        print("no lifecycle status change: terminal_status_unchanged")
        return 0

    atomic_write_json(RECOVERY_CURRENT_JSON, updated)

    if event:
        append_jsonl(EVENTS_RECOVERY_DIR / f"{today()}.jsonl", event)
        write_status(updated, f"classified: {event['event_type']}")
        print(f"classified recovery: {event['event_type']} reason={reason}")
        return 1

    write_status(updated, reason)
    print(f"no lifecycle status change: {reason}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Recovery lifecycle classifier")
    parser.add_argument("--once", action="store_true", help="Run one lifecycle classification pass")
    parser.add_argument("--dry-run", action="store_true", help="Print result without writing files")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.once and not args.dry_run:
        args.once = True

    try:
        run_once(dry_run=args.dry_run)
    except Exception as error:
        print(f"recovery-manager failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
