#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


AI_DIR = Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser()
TIMEZONE = ZoneInfo(os.environ.get("AI_SESSION_TIMEZONE", "Europe/Paris"))

CONTROL_DIR = AI_DIR / "control"
STATE_DIR = AI_DIR / "state"
SESSION_DIR = STATE_DIR / "session"
EVENTS_DESKTOP_DIR = AI_DIR / "events" / "desktop"

CURRENT_SESSION_JSON = SESSION_DIR / "current.json"
CURRENT_POLICY_JSON = SESSION_DIR / "current-policy.json"
CURRENT_POLICY_MD = SESSION_DIR / "current-policy.md"

CURRENT_TASK_MD = CONTROL_DIR / "current-task.md"
CURRENT_MODE_MD = CONTROL_DIR / "current-mode.md"
CURRENT_BLOCK_MD = CONTROL_DIR / "current-block.md"


DEFAULT_POLICIES = {
    "study": {
        "allowed_apps": ["Anki", "Obsidian", "kitty", "zen-beta"],
        "allowed_title_keywords": ["Anki", "Obsidian", "TaskNotes", "Perseverance"],
        "allowed_domains": ["ankiweb.net", "wiktionary.org", "deepl.com", "translate.google.com"],
        "distracting_apps": ["steam", "org.telegram.desktop"],
        "distracting_title_keywords": ["YouTube Shorts", "Reddit", "X /", "TikTok", "Instagram"],
        "distracting_domains": ["reddit.com", "x.com", "twitter.com", "tiktok.com", "instagram.com", "youtube.com/shorts"],
        "proof": {"required": False, "types": ["manual", "activity"]},
        "reflection_questions": [
            "What was difficult?",
            "What is still unclear?",
            "What is the smallest next review step?"
        ],
        "language": {"level": 1, "style": "normal"},
        "intervention": {"level": 2, "cooldown_seconds": 600},
    },
    "anki": {
        "allowed_apps": ["Anki", "Obsidian", "kitty"],
        "allowed_title_keywords": ["Anki", "Programming", "Language", "General", "Obsidian", "Perseverance", "TaskNotes"],
        "allowed_domains": ["ankiweb.net", "wiktionary.org", "deepl.com"],
        "distracting_apps": ["zen-beta", "org.telegram.desktop", "steam"],
        "distracting_title_keywords": ["YouTube", "Reddit", "Telegram", "X /", "TikTok", "Instagram"],
        "distracting_domains": ["youtube.com", "reddit.com", "x.com", "twitter.com", "tiktok.com", "instagram.com"],
        "proof": {"required": False, "types": ["anki_delta", "manual"]},
        "reflection_questions": [
            "Which cards were difficult?",
            "Was the difficulty memory, wording, or concept?",
            "Should any cards be rewritten?"
        ],
        "language": {"level": 1, "style": "known-vocabulary"},
        "intervention": {"level": 2, "cooldown_seconds": 600},
    },
    "coding": {
        "allowed_apps": ["kitty", "neovim", "code", "zen-beta", "Obsidian"],
        "allowed_title_keywords": ["NixOS", "GitHub", "docs", "README", "error", "trace"],
        "allowed_domains": ["github.com", "nixos.org", "search.nixos.org", "wiki.nixos.org", "stackoverflow.com", "docs.python.org"],
        "distracting_apps": ["steam", "org.telegram.desktop"],
        "distracting_title_keywords": ["YouTube Shorts", "Reddit", "TikTok", "Instagram"],
        "distracting_domains": ["youtube.com/shorts", "reddit.com", "tiktok.com", "instagram.com"],
        "proof": {"required": False, "types": ["git_diff", "file_changed", "manual"]},
        "reflection_questions": [
            "What changed?",
            "What remains broken?",
            "What is the next test command?"
        ],
        "language": {"level": 1, "style": "technical"},
        "intervention": {"level": 2, "cooldown_seconds": 600},
    },
    "writing": {
        "allowed_apps": ["Obsidian", "kitty", "zen-beta"],
        "allowed_title_keywords": ["Obsidian", "Perseverance", ".md"],
        "allowed_domains": ["deepl.com", "wiktionary.org", "dictionary.cambridge.org", "thesaurus.com"],
        "distracting_apps": ["steam"],
        "distracting_title_keywords": ["YouTube Shorts", "Reddit", "TikTok"],
        "distracting_domains": ["youtube.com/shorts", "reddit.com", "tiktok.com"],
        "proof": {"required": False, "types": ["note_changed", "manual"]},
        "reflection_questions": [
            "What did I write?",
            "What idea needs development?",
            "What wording felt weak?"
        ],
        "language": {"level": 2, "style": "elevated-english-french-optional"},
        "intervention": {"level": 2, "cooldown_seconds": 600},
    },
    "reading": {
        "allowed_apps": ["Obsidian", "zen-beta", "org.pwmt.zathura", "kitty"],
        "allowed_title_keywords": ["PDF", "Obsidian", "book", "paper", "article"],
        "allowed_domains": ["wikipedia.org", "archive.org", "jstor.org", "arxiv.org", "scholar.google.com"],
        "distracting_apps": ["steam"],
        "distracting_title_keywords": ["YouTube Shorts", "Reddit", "TikTok"],
        "distracting_domains": ["youtube.com/shorts", "reddit.com", "tiktok.com"],
        "proof": {"required": False, "types": ["note_created", "manual"]},
        "reflection_questions": [
            "What is the core claim?",
            "What did I learn?",
            "What should I remember?"
        ],
        "language": {"level": 2, "style": "elevated-english"},
        "intervention": {"level": 1, "cooldown_seconds": 900},
    },
    "learning-video": {
        "allowed_apps": ["zen-beta", "Obsidian", "kitty"],
        "allowed_title_keywords": ["YouTube", "lecture", "talk", "course", "design", "tutorial"],
        "allowed_domains": ["youtube.com", "youtu.be", "piped.video", "nebula.tv", "coursera.org", "edx.org"],
        "distracting_apps": ["steam"],
        "distracting_title_keywords": ["YouTube Shorts", "music video", "official video", "lyrics"],
        "distracting_domains": ["youtube.com/shorts", "reddit.com", "tiktok.com", "instagram.com"],
        "proof": {"required": False, "types": ["reflection_note", "manual"]},
        "reflection_questions": [
            "What was the main idea?",
            "What can I apply?",
            "What should I research next?"
        ],
        "language": {"level": 2, "style": "reflective"},
        "intervention": {"level": 1, "cooldown_seconds": 900},
    },
    "admin": {
        "allowed_apps": ["zen-beta", "Obsidian", "kitty"],
        "allowed_title_keywords": ["bank", "email", "form", "document", "application"],
        "allowed_domains": [],
        "distracting_apps": ["steam"],
        "distracting_title_keywords": ["YouTube Shorts", "Reddit", "TikTok"],
        "distracting_domains": ["youtube.com/shorts", "reddit.com", "tiktok.com"],
        "proof": {"required": False, "types": ["file_saved", "manual"]},
        "reflection_questions": [
            "What was completed?",
            "What is the next admin step?"
        ],
        "language": {"level": 0, "style": "simple"},
        "intervention": {"level": 2, "cooldown_seconds": 600},
    },
    "free": {
        "allowed_apps": [],
        "allowed_title_keywords": [],
        "allowed_domains": [],
        "distracting_apps": [],
        "distracting_title_keywords": ["YouTube Shorts"],
        "distracting_domains": ["youtube.com/shorts"],
        "proof": {"required": False, "types": ["none"]},
        "reflection_questions": [
            "Was this actually restful?",
            "Did I discover something worth saving?"
        ],
        "language": {"level": 1, "style": "light"},
        "intervention": {"level": 0, "cooldown_seconds": 1800},
    },
}


def now():
    return datetime.now(TIMEZONE)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in [CONTROL_DIR, SESSION_DIR, EVENTS_DESKTOP_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def append_jsonl(path: Path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def split_csv(values):
    out = []
    for value in values or []:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                out.append(item)
    return out


def uniq(items):
    result = []
    seen = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def compile_policy(args):
    mode = args.mode
    base = json.loads(json.dumps(DEFAULT_POLICIES.get(mode, DEFAULT_POLICIES["study"])))

    base["allowed_apps"] = uniq(base.get("allowed_apps", []) + split_csv(args.allow_app))
    base["distracting_apps"] = uniq(base.get("distracting_apps", []) + split_csv(args.distract_app))
    base["allowed_domains"] = uniq(base.get("allowed_domains", []) + split_csv(args.allow_domain))
    base["distracting_domains"] = uniq(base.get("distracting_domains", []) + split_csv(args.distract_domain))
    base["allowed_title_keywords"] = uniq(base.get("allowed_title_keywords", []) + split_csv(args.allow_title))
    base["distracting_title_keywords"] = uniq(base.get("distracting_title_keywords", []) + split_csv(args.distract_title))

    if args.strictness is not None:
        base["intervention"]["level"] = args.strictness

    if args.language_level is not None:
        base["language"]["level"] = args.language_level

    if args.proof:
        base["proof"]["required"] = True
        base["proof"]["types"] = split_csv([args.proof])

    base["compiled_at"] = now_iso()
    base["compiler"] = "session-manager-v0"
    base["mode"] = mode
    base["task"] = args.task
    base["project"] = args.project or ""

    return base


def policy_to_markdown(policy):
    lines = []
    lines.append("# Current Session Policy")
    lines.append("")
    lines.append(f"Compiled: {policy.get('compiled_at', '')}")
    lines.append(f"Mode: `{policy.get('mode', '')}`")
    lines.append(f"Task: {policy.get('task', '')}")
    if policy.get("project"):
        lines.append(f"Project: {policy.get('project', '')}")
    lines.append("")
    lines.append("## Apps")
    lines.append("")
    lines.append("### Allowed")
    for item in policy.get("allowed_apps", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Distracting")
    for item in policy.get("distracting_apps", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Domains")
    lines.append("")
    lines.append("### Allowed")
    for item in policy.get("allowed_domains", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Distracting")
    for item in policy.get("distracting_domains", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Title keywords")
    lines.append("")
    lines.append("### Allowed")
    for item in policy.get("allowed_title_keywords", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Distracting")
    for item in policy.get("distracting_title_keywords", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Proof")
    lines.append("")
    proof = policy.get("proof", {})
    lines.append(f"Required: `{str(proof.get('required', False)).lower()}`")
    lines.append("Types:")
    for item in proof.get("types", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Intervention")
    lines.append("")
    intervention = policy.get("intervention", {})
    lines.append(f"Level: `{intervention.get('level', 0)}`")
    lines.append(f"Cooldown seconds: `{intervention.get('cooldown_seconds', 600)}`")
    lines.append("")
    lines.append("## Language")
    lines.append("")
    language = policy.get("language", {})
    lines.append(f"Level: `{language.get('level', 0)}`")
    lines.append(f"Style: `{language.get('style', 'normal')}`")
    lines.append("")
    lines.append("## Reflection questions")
    lines.append("")
    for item in policy.get("reflection_questions", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_control_files(session, policy):
    task = session["task"]
    mode = session["mode"]

    lines = []
    lines.append("# Current Task")
    lines.append("")
    lines.append(f"Task: {task}")
    lines.append(f"Mode: {mode}")
    if session.get("project"):
        lines.append(f"Project: {session['project']}")
    lines.append(f"Session ID: {session['session_id']}")
    lines.append(f"Started: {session['started_at']}")
    if session.get("planned_end_at"):
        lines.append(f"Planned end: {session['planned_end_at']}")
    lines.append("")
    lines.append("## Allowed apps")
    for item in policy.get("allowed_apps", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Distracting apps")
    for item in policy.get("distracting_apps", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Allowed title keywords")
    for item in policy.get("allowed_title_keywords", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Distracting title keywords")
    for item in policy.get("distracting_title_keywords", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Allowed domains")
    for item in policy.get("allowed_domains", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Distracting domains")
    for item in policy.get("distracting_domains", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Proof")
    proof = policy.get("proof", {})
    lines.append(f"Required: {str(proof.get('required', False)).lower()}")
    lines.append("Types:")
    for item in proof.get("types", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Reflection questions")
    for item in policy.get("reflection_questions", []):
        lines.append(f"- {item}")
    lines.append("")

    atomic_write_text(CURRENT_TASK_MD, "\n".join(lines))
    atomic_write_text(CURRENT_MODE_MD, f"# Current Mode\n\nMode: {mode}\nStrictness: {policy.get('intervention', {}).get('level', 0)}\nLanguage level: {policy.get('language', {}).get('level', 0)}\n")
    atomic_write_text(CURRENT_BLOCK_MD, f"# Current Block\n\nSession ID: {session['session_id']}\nTask: {task}\nStarted: {session['started_at']}\nPlanned end: {session.get('planned_end_at', '')}\nStatus: {session['status']}\n")


def event(kind, payload):
    data = {
        "source": "session-manager",
        "device": "desktop",
        "event": kind,
        "timestamp": now_iso(),
        "timestamp_epoch": int(time.time()),
        "date": today(),
        "time": now().strftime("%H:%M:%S"),
    }
    data.update(payload)
    append_jsonl(EVENTS_DESKTOP_DIR / f"{today()}.jsonl", data)


def start_session(args):
    ensure_dirs()

    duration = args.duration
    started_at = now()
    planned_end = started_at + timedelta(minutes=duration) if duration else None

    session_id = f"session-{started_at.strftime('%Y%m%d-%H%M%S')}"

    session = {
        "session_id": session_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "planned_end_at": planned_end.isoformat(timespec="seconds") if planned_end else "",
        "source": args.source,
        "task": args.task,
        "project": args.project or "",
        "mode": args.mode,
        "status": "active",
        "duration_minutes": duration,
        "policy_path": str(CURRENT_POLICY_JSON),
    }

    policy = compile_policy(args)

    atomic_write_json(CURRENT_SESSION_JSON, session)
    atomic_write_json(CURRENT_POLICY_JSON, policy)
    atomic_write_text(CURRENT_POLICY_MD, policy_to_markdown(policy))
    write_control_files(session, policy)

    event("session_started", {"session": session, "policy": policy})

    print(f"started session: {session_id}")
    print(f"task={args.task}")
    print(f"mode={args.mode}")
    print(f"policy={CURRENT_POLICY_JSON}")
    print(f"current_task={CURRENT_TASK_MD}")


def load_session():
    if not CURRENT_SESSION_JSON.exists():
        return None
    return json.loads(CURRENT_SESSION_JSON.read_text(encoding="utf-8"))


def status_session(_args):
    ensure_dirs()
    session = load_session()
    if not session:
        print("no active session")
        return

    print(json.dumps(session, indent=2, ensure_ascii=False))
    if CURRENT_POLICY_MD.exists():
        print("")
        print(CURRENT_POLICY_MD.read_text(encoding="utf-8"))


def end_session(args):
    ensure_dirs()
    session = load_session()

    if not session:
        print("no active session")
        return

    session["status"] = args.status
    session["ended_at"] = now_iso()
    session["end_reason"] = args.reason or ""

    archive_dir = SESSION_DIR / "archive" / today()
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{session['session_id']}.json"
    atomic_write_json(archive_path, session)

    atomic_write_json(CURRENT_SESSION_JSON, session)
    atomic_write_text(CURRENT_BLOCK_MD, f"# Current Block\n\nSession ID: {session['session_id']}\nTask: {session['task']}\nStarted: {session['started_at']}\nEnded: {session['ended_at']}\nStatus: {session['status']}\nReason: {session['end_reason']}\n")

    event("session_ended", {"session": session})

    print(f"ended session: {session['session_id']}")
    print(f"status={session['status']}")
    print(f"archive={archive_path}")


def list_modes(_args):
    for mode in sorted(DEFAULT_POLICIES.keys()):
        print(mode)


def build_parser():
    parser = argparse.ArgumentParser(description="AI productivity session manager")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="start a new session")
    start.add_argument("--task", required=True)
    start.add_argument("--mode", default="study", choices=sorted(DEFAULT_POLICIES.keys()))
    start.add_argument("--project", default="")
    start.add_argument("--duration", type=int, default=25)
    start.add_argument("--source", default="manual")
    start.add_argument("--strictness", type=int, choices=range(0, 7), default=None)
    start.add_argument("--language-level", type=int, choices=range(0, 5), default=None)
    start.add_argument("--proof", default="")
    start.add_argument("--allow-app", action="append", default=[])
    start.add_argument("--distract-app", action="append", default=[])
    start.add_argument("--allow-domain", action="append", default=[])
    start.add_argument("--distract-domain", action="append", default=[])
    start.add_argument("--allow-title", action="append", default=[])
    start.add_argument("--distract-title", action="append", default=[])
    start.set_defaults(func=start_session)

    status = sub.add_parser("status", help="show current session")
    status.set_defaults(func=status_session)

    end = sub.add_parser("end", help="end current session")
    end.add_argument("--status", default="completed", choices=["completed", "abandoned", "paused", "interrupted"])
    end.add_argument("--reason", default="")
    end.set_defaults(func=end_session)

    modes = sub.add_parser("modes", help="list available modes")
    modes.set_defaults(func=list_modes)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except Exception as error:
        print(f"ai-session failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
