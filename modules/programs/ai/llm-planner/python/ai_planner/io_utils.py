import json
from datetime import datetime
from pathlib import Path


def now(config):
    return datetime.now(config.timezone)


def now_iso(config):
    return now(config).isoformat(timespec="seconds")


def today(config):
    return now(config).strftime("%Y-%m-%d")


def ensure_dirs(config):
    for path in [
        config.context_dir,
        config.state_llm_dir,
        config.reports_daily_dir,
        config.proposed_tasks_dir,
        config.outbox_to_phone_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_text(path: Path, default=""):
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as error:
        return f"[error reading {path}: {error}]"
    return default


def read_text_limited(path: Path, max_chars: int, default=""):
    text = read_text(path, default)
    if len(text) <= max_chars:
        return text
    half = max(1, max_chars // 2)
    return text[:half] + "\n\n[...middle truncated...]\n\n" + text[-half:]


def read_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"error": f"error reading {path}: {error}"}
    return default


def tail_text(path: Path, max_chars: int):
    text = read_text(path, "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def read_jsonl_tail(path: Path, max_events: int):
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as error:
        return [{"error": f"error reading {path}: {error}"}]

    events = []
    for line in lines[-max_events:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            events.append({"malformed": line[:500]})

    return events


def safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def clamp_text(value, max_chars: int):
    text = safe_str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
