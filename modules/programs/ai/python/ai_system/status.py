import json

from ai_system.io_utils import atomic_write_json, atomic_write_text


def write_status_pair(json_path, md_path, *, updated_at, status, message="", details=None, title="Status"):
    details = details or {}

    data = {
        "updated_at": updated_at,
        "status": status,
        "message": message,
        "details": details,
    }

    atomic_write_json(json_path, data)

    lines = [
        f"# {title}",
        "",
        f"Updated: {updated_at}",
        f"Status: `{status}`",
        f"Message: {message}",
        "",
    ]

    if details:
        lines.extend([
            "## Details",
            "",
            "```json",
            json.dumps(details, indent=2, ensure_ascii=False),
            "```",
            "",
        ])

    atomic_write_text(md_path, "\n".join(lines))
