#!/usr/bin/env python3

from __future__ import annotations

import json
import stat
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "modules/programs/ai/python"))

from ai_system.io_utils import atomic_write_json, atomic_write_text  # noqa: E402
from ai_system.obsidian_contracts import (
    DIRECT_EXECUTION_FIELDS,
    PLANNER_EXECUTION_POLICY,
    PROPOSAL_EXECUTION_POLICY,
    bounded_line,
    bounded_list,
    bounded_text,
    contains_direct_execution,
    read_json_object,
    slug,
)


def test_bounds_are_stable() -> None:
    assert bounded_text("abc", max_len=10) == "abc"
    assert bounded_text("abcdefghij", max_len=8) == "abcdefgh"
    assert bounded_line("a\nb", max_len=10) == "a b"
    assert bounded_list(["a", "", "b"], max_items=3) == ["a", "b"]
    assert slug("Hello, Task!") == "hello-task"


def test_direct_execution_union_covers_task_and_llm_fields() -> None:
    expected = {
        "shell_command",
        "command",
        "exec",
        "executable",
        "desktop_command",
        "launch_task",
        "android_package",
        "uri_to_open",
        "url_to_open",
        "write_path",
        "delete_path",
        "move_path",
        "edits_obsidian_now",
        "writes_live_action_queue",
    }

    assert expected <= DIRECT_EXECUTION_FIELDS


def test_direct_execution_scanner_reports_paths() -> None:
    found = contains_direct_execution(
        {
            "safe": [{"label": "ok"}],
            "nested": {
                "suggested_actions": [
                    {"type": "draft_task"},
                    {"shell_command": "rm -rf /"},
                ]
            },
        }
    )

    assert found == ["nested.suggested_actions[1].shell_command"]


def test_empty_dict_policy_is_explicit() -> None:
    assert contains_direct_execution({"command": {}}) == ["command"]
    assert contains_direct_execution({"command": {}}, ignore_empty_dict=True) == []


def test_json_object_reader() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-obsidian-contracts-") as tmp:
        path = Path(tmp) / "payload.json"
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")

        assert read_json_object(path) == {"ok": True}
        assert read_json_object(Path(tmp) / "missing.json", missing_ok=True) == {}

        bad = Path(tmp) / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        try:
            read_json_object(bad, object_error="input must be a JSON object")
        except ValueError as exc:
            assert "input must be a JSON object" in str(exc)
        else:
            raise AssertionError("non-object JSON must fail")


def test_policy_constant() -> None:
    assert PROPOSAL_EXECUTION_POLICY == "proposal_only_no_direct_execution"


def test_planner_policy_constant() -> None:
    assert PLANNER_EXECUTION_POLICY == "planner_must_decide_no_direct_execution"


def test_atomic_write_text_replaces_existing_file_and_cleans_temp() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-atomic-write-") as tmp:
        path = Path(tmp) / "state" / "status.md"
        path.parent.mkdir(parents=True)
        path.write_text("old", encoding="utf-8")

        atomic_write_text(path, "new")
        assert path.read_text(encoding="utf-8") == "new"
        assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_atomic_write_json_replaces_existing_file() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-atomic-json-") as tmp:
        path = Path(tmp) / "state" / "status.json"
        atomic_write_json(path, {"ok": True})

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"ok": True}


def test_atomic_write_text_preserves_existing_file_mode() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-atomic-mode-") as tmp:
        path = Path(tmp) / "state" / "status.md"
        path.parent.mkdir(parents=True)
        path.write_text("old", encoding="utf-8")
        path.chmod(0o644)

        atomic_write_text(path, "new")

        assert path.read_text(encoding="utf-8") == "new"
        assert stat.S_IMODE(path.stat().st_mode) == 0o644


def run_all() -> None:
    tests = [
        test_bounds_are_stable,
        test_direct_execution_union_covers_task_and_llm_fields,
        test_direct_execution_scanner_reports_paths,
        test_empty_dict_policy_is_explicit,
        test_json_object_reader,
        test_policy_constant,
        test_planner_policy_constant,
        test_atomic_write_text_replaces_existing_file_and_cleans_temp,
        test_atomic_write_json_replaces_existing_file,
        test_atomic_write_text_preserves_existing_file_mode,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print("ALL PASS")


if __name__ == "__main__":
    run_all()
