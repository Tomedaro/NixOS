#!/usr/bin/env python3
"""Tests for anki-safe-writer batch planning. Uses fake AnkiConnect, never touches real Anki."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Path to the dev source script
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "anki_safe_writer.py"

# Fake Anki state: two existing generated notes
FAKE_NOTES = [
    {
        "noteId": 1781115948589,
        "fields": {
            "Front": {"value": "What tag marks notes created by anki-safe-writer?"},
            "Back": {"value": "pi-generated"},
        },
        "tags": ["needs-human-review", "pi-generated"],
        "cards": [1781115948590],
    },
    {
        "noteId": 1781121362824,
        "fields": {
            "Front": {"value": "What tag marks notes that still need human review?"},
            "Back": {"value": "needs-human-review"},
        },
        "tags": ["needs-human-review", "pi-generated"],
        "cards": [1781121362826],
    },
]

FORBIDDEN_ACTIONS = {
    "addNote", "deleteNotes", "updateNoteFields", "addTags", "removeTags",
    "suspend", "unsuspend", "sync", "multi", "guiBrowse", "guiAddCards",
}


class FakeAnkiConnectHandler(BaseHTTPRequestHandler):
    """Minimal fake AnkiConnect server."""

    # Shared action list across handler instances
    server_actions = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._send({"result": None, "error": "bad request"})
            return

        action = req.get("action", "")
        params = req.get("params", {})
        FakeAnkiConnectHandler.server_actions.append(action)

        result = self._handle(action, params)
        self._send({"result": result, "error": None})

    def _handle(self, action, params):
        if action == "version":
            return 6
        elif action == "deckNames":
            return ["Pi Sandbox"]
        elif action == "modelNames":
            return ["Basic"]
        elif action == "modelFieldNames":
            return ["Front", "Back"]
        elif action == "findNotes":
            query = params.get("query", "")
            if "pi-generated" in query and "needs-human-review" in query:
                return [n["noteId"] for n in FAKE_NOTES]
            return []
        elif action == "notesInfo":
            return [n for n in FAKE_NOTES if n["noteId"] in params.get("notes", [])]
        elif action == "canAddNotes":
            notes = params.get("notes", [])
            return [True for _ in notes]
        else:
            return None

    def _send(self, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


class FakeAnkiConnectServer:
    """Context manager for a fake AnkiConnect server on a random port."""

    def __init__(self):
        self.server = None
        self.thread = None
        self.port = None

    def __enter__(self):
        FakeAnkiConnectHandler.server_actions = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeAnkiConnectHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        if self.server:
            self.server.shutdown()
            if self.thread:
                self.thread.join()
            self.server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    @property
    def actions(self):
        return FakeAnkiConnectHandler.server_actions.copy()

    def assert_forbidden_not_called(self, tc):
        """Assert no forbidden AnkiConnect actions were called."""
        called = set(self.actions)
        forbidden = called & FORBIDDEN_ACTIONS
        tc.assertEqual(set(), forbidden,
                       f"Forbidden action(s) called: {forbidden}")


class AnkiSafeWriterTest(unittest.TestCase):
    """Base class for anki-safe-writer tests."""

    def setUp(self):
        self.state_dir = tempfile.TemporaryDirectory(prefix="asw-test-")
        self.fake_anki = FakeAnkiConnectServer()
        self.fake_anki.__enter__()

    def tearDown(self):
        self.fake_anki.__exit__(None, None, None)
        self.state_dir.cleanup()

    def _env(self):
        return {
            **os.environ,
            "ANKI_SAFE_WRITER_STATE": self.state_dir.name,
            "ANKI_CONNECT_URL": self.fake_anki.url,
        }

    def _run(self, *args):
        """Run anki-safe-writer CLI as a subprocess."""
        cmd = [sys.executable, str(SOURCE)] + list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self._env())
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def _write_input(self, data):
        """Write a JSON input file inside the temp state dir and return the path."""
        path = Path(self.state_dir.name) / "input.json"
        path.write_text(json.dumps(data))
        return str(path)

    def _batch_dir(self):
        return Path(self.state_dir.name) / "batch-plans"

    def _batch_aborted_dir(self):
        return Path(self.state_dir.name) / "batch-aborted"

    def _find_batch_plan(self):
        """Return the first batch plan file path, or None."""
        bp = self._batch_dir()
        if not bp.exists():
            return None
        files = sorted(bp.iterdir())
        return str(files[0]) if files else None

    def _find_batch_aborted(self):
        """Return the first aborted batch plan path, or None."""
        ba = self._batch_aborted_dir()
        if not ba.exists():
            return None
        files = sorted(ba.iterdir())
        return str(files[0]) if files else None


# ── Tests ─────────────────────────────────────────────────────────────────

class TestCommandSurface(AnkiSafeWriterTest):
    """Test that --help shows expected batch commands and no approve/apply."""

    def test_help_includes_batch_commands(self):
        rc, out, _ = self._run("--help")
        self.assertEqual(0, rc)
        for cmd in ("plan-create-notes-batch", "inspect-batch-plan",
                    "abort-batch-plan", "list-batch-plans", "list-batch-aborted"):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, out)

    def test_help_excludes_batch_approve_apply(self):
        rc, out, _ = self._run("--help")
        self.assertEqual(0, rc)
        for cmd in ("approve-batch-plan", "apply-batch-plan",
                    "approve-batch", "apply-batch"):
            with self.subTest(cmd=cmd):
                self.assertNotIn(cmd, out)


class TestBatchLifecycle(AnkiSafeWriterTest):
    """Happy path: create, inspect, list, abort a batch plan."""

    def test_full_lifecycle(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "New note A", "back": "Answer A",
                 "tags": ["pi-generated", "needs-human-review"]},
                {"front": "New note B", "back": "Answer B",
                 "tags": ["pi-generated", "needs-human-review"]},
            ],
        })
        # Create
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertEqual(0, rc, f"create failed: {out}")
        result = json.loads(out)
        self.assertEqual("planned", result["status"])
        self.assertEqual(2, result["note_count"])
        self.assertFalse(result["apply_supported"])
        self.assertFalse(result["approval_supported"])

        bp_path = self._find_batch_plan()
        self.assertIsNotNone(bp_path)

        # Inspect
        rc, out, _ = self._run("inspect-batch-plan", bp_path)
        self.assertEqual(0, rc)
        plan = json.loads(out)
        self.assertEqual("anki-safe-writer.batch-plan.v1", plan["schema_version"])
        self.assertEqual("create-notes-batch", plan["plan_type"])
        self.assertEqual("planned", plan["status"])
        self.assertFalse(plan["approval_supported"])
        self.assertFalse(plan["apply_supported"])
        self.assertEqual(2, plan["proposed_note_count"])
        self.assertEqual(2, plan["live_generated_count_at_plan_time"])
        self.assertEqual(4, plan["estimated_live_generated_count_after_apply"])

        # List
        rc, out, _ = self._run("list-batch-plans")
        self.assertEqual(0, rc)
        listing = json.loads(out)
        self.assertTrue(listing["directory_exists"])
        self.assertEqual(1, len(listing["files"]))

        # Abort
        rc, out, _ = self._run("abort-batch-plan", bp_path)
        self.assertEqual(0, rc)

        # Verify moved
        self.assertIsNone(self._find_batch_plan())
        self.assertIsNotNone(self._find_batch_aborted())

        # No forbidden actions
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeDuplicateWithinBatch(AnkiSafeWriterTest):
    def test_duplicate_within_batch(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "Same", "back": "Same",
                 "tags": ["pi-generated", "needs-human-review"]},
                {"front": "Same", "back": "Same",
                 "tags": ["pi-generated", "needs-human-review"]},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("duplicate", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeDuplicateAgainstLive(AnkiSafeWriterTest):
    def test_duplicate_against_live(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "What tag marks notes created by anki-safe-writer?",
                 "back": "pi-generated",
                 "tags": ["pi-generated", "needs-human-review"]},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("duplicate", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeCapExceeded(AnkiSafeWriterTest):
    def test_cap_exceeded(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 1,
            "notes": [
                {"front": "New A", "back": "A",
                 "tags": ["pi-generated", "needs-human-review"]},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("max", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeMissingTag(AnkiSafeWriterTest):
    def test_missing_required_tag(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "Test", "back": "Test",
                 "tags": ["wrong-tag"]},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("tag", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeUnknownKeys(AnkiSafeWriterTest):
    def test_unknown_top_level_key(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "extra_key": "bad",
            "notes": [],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("unknown", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)

    def test_unknown_note_key(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "X", "back": "Y",
                 "tags": ["pi-generated", "needs-human-review"],
                 "bad_field": "nope"},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertNotEqual(0, rc)
        self.assertIn("unknown", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestNegativeBatchSize(AnkiSafeWriterTest):
    def test_batch_size_exceeded(self):
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": f"A{i}", "back": f"B{i}",
                 "tags": ["pi-generated", "needs-human-review"]}
                for i in range(3)
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "2")
        self.assertNotEqual(0, rc)
        self.assertIn("exceed", out.lower())
        self.assertIsNone(self._find_batch_plan())
        self.fake_anki.assert_forbidden_not_called(self)


class TestSingleNoteCommandsRefuseBatch(AnkiSafeWriterTest):
    """Single-note approve/apply must reject batch artifacts."""

    def test_approve_refuses_batch(self):
        # Create a batch plan first
        inp = self._write_input({
            "deck": "Pi Sandbox",
            "model": "Basic",
            "max_live_generated": 10,
            "notes": [
                {"front": "Batch note", "back": "Batch answer",
                 "tags": ["pi-generated", "needs-human-review"]},
            ],
        })
        rc, out, _ = self._run("plan-create-notes-batch",
                                "--input", inp, "--max-batch-size", "5")
        self.assertEqual(0, rc)
        bp_path = self._find_batch_plan()
        self.assertIsNotNone(bp_path)

        # approve-plan must refuse batch plan
        rc, out, _ = self._run("approve-plan", bp_path)
        self.assertNotEqual(0, rc)

        # apply-approved-plan must refuse batch plan
        rc, out, _ = self._run("apply-approved-plan", bp_path, "--apply")
        self.assertNotEqual(0, rc)

        # No forbidden actions called
        self.fake_anki.assert_forbidden_not_called(self)

        # Batch plan still in batch-plans/ (not moved to approved/)
        self.assertIsNotNone(self._find_batch_plan())


class TestPathGuard(AnkiSafeWriterTest):
    def test_inspect_refuses_outside_path(self):
        # Create a JSON file outside the temp state root
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write('{"test": true}')
            outside_path = f.name
        try:
            rc, out, _ = self._run("inspect-batch-plan", outside_path)
            self.assertNotEqual(0, rc)
            self.assertIn("resolve inside", out.lower())
        finally:
            os.unlink(outside_path)


if __name__ == "__main__":
    unittest.main()
