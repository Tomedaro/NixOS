from datetime import datetime, timezone
from pathlib import Path

from ai_system.io_utils import append_jsonl


def parse_event_time(raw, source_file, tz):
    timestamp_epoch = raw.get("timestamp_epoch")

    if timestamp_epoch is not None:
        try:
            epoch = int(float(timestamp_epoch))
            dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(tz)
            return dt, epoch
        except Exception:
            pass

    timestamp = raw.get("timestamp") or raw.get("created_at") or raw.get("observed_at")
    if timestamp:
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).astimezone(tz)
            return dt, int(dt.timestamp())
        except Exception:
            pass

    epoch = int(Path(source_file).stat().st_mtime)
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(tz)
    return dt, epoch


def normalize_event(raw, *, source_file, ai_dir, tz, default_source, default_device, session=None):
    if not isinstance(raw, dict):
        raise ValueError("event JSON is not an object")

    dt, epoch = parse_event_time(raw, source_file, tz)
    event_type = str(raw.get("event") or raw.get("type") or "unknown").strip() or "unknown"

    event = dict(raw)
    event["schema_version"] = str(event.get("schema_version") or "event.v1")
    event["event"] = event_type
    event["event_type"] = event_type
    event["source"] = str(event.get("source") or default_source)
    event["device"] = str(event.get("device") or default_device)
    event["timestamp_epoch"] = epoch
    event["timestamp"] = dt.isoformat(timespec="seconds")
    event["date"] = dt.strftime("%Y-%m-%d")
    event["time"] = dt.strftime("%H:%M:%S")
    event["processed_at"] = datetime.now(tz).isoformat(timespec="seconds")

    try:
        event["raw_file"] = str(Path(source_file).relative_to(Path(ai_dir)))
    except Exception:
        event["raw_file"] = str(source_file)

    if not event.get("event_id"):
        event["event_id"] = f"{event['device']}-{event_type}-{epoch}-{Path(source_file).stem}"

    if isinstance(session, dict):
        for key in ["session_id", "mode", "task", "project"]:
            if key not in event and session.get(key):
                event[key] = session.get(key)

    return event


def append_event(events_dir, event):
    path = Path(events_dir) / f"{event['date']}.jsonl"
    append_jsonl(path, event)
    return path
