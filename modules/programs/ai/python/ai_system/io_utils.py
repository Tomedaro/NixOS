import json
import os
import stat
import tempfile
from pathlib import Path


def _default_file_mode() -> int:
    """Return the normal creation mode for a regular file under current umask."""
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def _target_metadata(path: Path) -> tuple[int, int | None, int | None]:
    """Return mode/uid/gid to apply to an atomic-write temp file.

    Existing files keep their permission bits and ownership. New files use the
    regular process umask-derived file mode instead of mkstemp's private 0600.
    """
    try:
        current = path.stat()
    except FileNotFoundError:
        return _default_file_mode(), None, None

    return stat.S_IMODE(current.st_mode), current.st_uid, current.st_gid


def _try_fchown(fd: int, uid: int | None, gid: int | None) -> None:
    if uid is None or gid is None or os.name == "nt":
        return

    try:
        os.fchown(fd, uid, gid)
    except OSError:
        pass


def _fsync_parent_dir(path: Path) -> None:
    """Best-effort fsync for the directory entry after atomic replace.

    This matters for crash consistency on Unix-like filesystems. Some filesystems
    or platforms do not support directory fsync, so keep this non-fatal.
    """
    if os.name == "nt":
        return

    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode, uid, gid = _target_metadata(path)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            file_fd = handle.fileno()
            handle.write(str(text))
            handle.flush()
            _try_fchown(file_fd, uid, gid)
            os.fchmod(file_fd, mode)
            os.fsync(file_fd)

        os.replace(tmp, path)
        _fsync_parent_dir(path)
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


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


def read_jsonl(path):
    path = Path(path)

    if not path.exists():
        return []

    events = []

    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except Exception:
                continue

            if isinstance(item, dict):
                events.append(item)
    except Exception:
        return []

    return events
