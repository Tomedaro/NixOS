import json
from pathlib import Path


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(str(text), encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_text(path, default=""):
    path = Path(path)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as error:
        return f"[error reading {path}: {error}]"
    return default


def read_json(path, default=None):
    path = Path(path)
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"error": f"error reading {path}: {error}"}
    return default


def append_jsonl(path, event):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
