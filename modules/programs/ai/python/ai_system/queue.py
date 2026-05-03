import shutil
import time
from pathlib import Path


def is_stable(path, stability_seconds):
    path = Path(path)
    try:
        return time.time() - path.stat().st_mtime >= stability_seconds
    except FileNotFoundError:
        return False


def unique_destination(path):
    path = Path(path)

    if not path.exists():
        return path

    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"could not find unique destination for {path}")


def move_unique(source, destination_dir, prefix=""):
    source = Path(source)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    name = f"{prefix}{source.name}" if prefix else source.name
    destination = unique_destination(destination_dir / name)
    shutil.move(str(source), str(destination))
    return destination
