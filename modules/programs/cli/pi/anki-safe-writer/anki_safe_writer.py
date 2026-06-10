#!/usr/bin/env python3
"""anki-safe-writer: dry-run note planning for Pi Sandbox deck only."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

STATE_ROOT = Path(os.environ.get(
    "ANKI_SAFE_WRITER_STATE",
    Path.home() / ".local" / "state" / "anki-safe-writer"
))
PLANS_DIR = STATE_ROOT / "plans"
APPROVED_DIR = STATE_ROOT / "approved"
ABORTED_DIR = STATE_ROOT / "aborted"
APPLIED_DIR = STATE_ROOT / "applied"
FAILED_DIR = STATE_ROOT / "failed"
ROLLBACK_PLANS_DIR = STATE_ROOT / "rollback-plans"
ROLLBACK_APPROVED_DIR = STATE_ROOT / "rollback-approved"
ROLLBACK_APPLIED_DIR = STATE_ROOT / "rollback-applied"
BATCH_PLANS_DIR = STATE_ROOT / "batch-plans"
BATCH_ABORTED_DIR = STATE_ROOT / "batch-aborted"
ANKI_CONNECT_URL = os.environ.get(
    "ANKI_CONNECT_URL", "http://127.0.0.1:8765"
)

_ALLOWED_PLAN_DIRS = (PLANS_DIR, APPROVED_DIR, BATCH_PLANS_DIR, BATCH_ABORTED_DIR)

# All tracked state directories used by status and audit commands
_TRACKED_DIRS = {
    "plans": PLANS_DIR, "approved": APPROVED_DIR,
    "applied": APPLIED_DIR, "failed": FAILED_DIR,
    "aborted": ABORTED_DIR,
    "rollback-plans": ROLLBACK_PLANS_DIR,
    "rollback-approved": ROLLBACK_APPROVED_DIR,
    "rollback-applied": ROLLBACK_APPLIED_DIR,
    "batch-plans": BATCH_PLANS_DIR,
    "batch-aborted": BATCH_ABORTED_DIR,
}


def anki_request(action, params=None):
    payload = {"action": action, "version": 6}
    if params is not None:
        payload["params"] = params
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANKI_CONNECT_URL, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "anki-safe-writer/0.1"},
        method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    if parsed.get("error"):
        raise RuntimeError(
            f"AnkiConnect action {action} failed: {parsed['error']}")
    return parsed["result"]


def _resolve_plan(name_or_path, allowed_dirs=None):
    """Resolve a plan filename inside allowed dirs. Exits on error."""
    if allowed_dirs is None:
        allowed_dirs = _ALLOWED_PLAN_DIRS
    candidate = Path(name_or_path)
    if not candidate.is_absolute():
        candidate = PLANS_DIR / candidate.name
    candidate = candidate.resolve()
    for d in allowed_dirs:
        try:
            candidate.relative_to(d.resolve())
            break
        except ValueError:
            continue
    else:
        dirs_str = ", ".join(str(d) for d in allowed_dirs)
        print(json.dumps(
            {"error": f"Path must resolve inside {dirs_str}"},
            indent=2))
        sys.exit(1)
    if candidate.suffix != ".json":
        print(json.dumps({"error": "Plan file must have .json extension"},
                         indent=2))
        sys.exit(1)
    if not candidate.exists():
        print(json.dumps({"error": f"Plan not found: {candidate}"},
                         indent=2))
        sys.exit(1)
    return candidate


def cmd_plan_create_note(args):
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    actions_called = []
    errors = []

    anki_version = anki_request("version")
    actions_called.append("version")

    decks = anki_request("deckNames")
    actions_called.append("deckNames")
    deck_exists = "Pi Sandbox" in decks

    models = anki_request("modelNames")
    actions_called.append("modelNames")
    basic_exists = "Basic" in models

    fields = None
    fields_valid = False
    if basic_exists:
        fields = anki_request("modelFieldNames", {"modelName": "Basic"})
        actions_called.append("modelFieldNames")
        fields_valid = fields == ["Front", "Back"]

    if not deck_exists:
        errors.append("Deck 'Pi Sandbox' does not exist. "
                       "Create it manually in Anki Desktop.")
    if not basic_exists:
        errors.append("Note type 'Basic' not found.")
    if not fields_valid:
        errors.append(f"Basic model fields mismatch: "
                      f"expected ['Front','Back'], got {fields}")

    validation = {
        "deck_exists": deck_exists,
        "model_exists": basic_exists,
        "field_names": fields,
        "field_names_valid": fields_valid,
        "errors": errors,
    }

    if not errors:
        can_add = anki_request("canAddNotes", {
            "notes": [{
                "deckName": "Pi Sandbox",
                "modelName": "Basic",
                "fields": {"Front": args.front, "Back": args.back},
                "tags": ["pi-generated", "needs-human-review"],
            }]
        })
        actions_called.append("canAddNotes")
        addable = can_add[0] if can_add else False
        validation["can_add"] = addable
        validation["addable_note"] = addable
        if not addable:
            validation["not_addable_reason"] = (
                "not addable; exact reason not determined by canAddNotes")

    plan = {
        "schema_version": 1,
        "plan_type": "create-basic-note",
        "created_at": ts,
        "status": "blocked" if errors else "planned",
        "ready_for_apply": False,
        "anki": {
            "connect_url": ANKI_CONNECT_URL,
            "version": anki_version,
        },
        "policy": {
            "target_deck": "Pi Sandbox",
            "model_name": "Basic",
            "required_tags": ["pi-generated", "needs-human-review"],
            "max_batch_size": 1,
            "media_allowed": False,
            "sync_allowed": False,
        },
        "note": {
            "front": args.front,
            "back": args.back,
        },
        "validation": validation,
        "actions_called_during_planning": actions_called,
        "future_actions_if_apply_is_enabled": ["addNote"],
        "sync_will_be_called": False,
        "backup_required_before_apply": True,
        "integrity": {
            "schema_sha256": "not computed",
        },
    }

    plan_file = PLANS_DIR / f"plan-{ts}.json"
    plan_file.write_text(json.dumps(plan, indent=2))

    result = {"status": "blocked" if errors else "planned",
              "plan_file": str(plan_file)}
    if errors:
        result["errors"] = errors
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


def cmd_inspect_plan(args):
    path = _resolve_plan(args.plan_file)
    plan = json.loads(path.read_text())
    print(json.dumps(plan, indent=2))
    return 0


def cmd_abort_plan(args):
    path = _resolve_plan(args.plan_file, allowed_dirs=(PLANS_DIR,))
    ABORTED_DIR.mkdir(parents=True, exist_ok=True)
    dest = ABORTED_DIR / path.name
    path.rename(dest)
    print(json.dumps({"status": "aborted", "moved_to": str(dest)}, indent=2))
    return 0


def cmd_approve_plan(args):
    if not args.confirm_approve_pi_sandbox_note:
        print(json.dumps({
            "error": "Confirmation flag required: "
                     "--confirm-approve-pi-sandbox-note"}, indent=2))
        return 1

    path = _resolve_plan(args.plan_file, allowed_dirs=(PLANS_DIR,))
    plan = json.loads(path.read_text())
    errors = []

    if plan.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, "
                      f"got {plan.get('schema_version')}")
    if plan.get("plan_type") != "create-basic-note":
        errors.append(f"plan_type must be 'create-basic-note', "
                      f"got {plan.get('plan_type')}")
    if plan.get("policy", {}).get("target_deck") != "Pi Sandbox":
        errors.append("target_deck must be 'Pi Sandbox'")
    if plan.get("policy", {}).get("model_name") != "Basic":
        errors.append("model_name must be 'Basic'")
    fields = plan.get("note", {})
    if set(fields.keys()) != {"front", "back"}:
        errors.append("note fields must be exactly 'front' and 'back'")
    tags = plan.get("policy", {}).get("required_tags", [])
    if "pi-generated" not in tags:
        errors.append("required_tags must include 'pi-generated'")
    if "needs-human-review" not in tags:
        errors.append("required_tags must include 'needs-human-review'")
    if plan.get("sync_will_be_called") is not False:
        errors.append("sync_will_be_called must be false")
    if plan.get("ready_for_apply") is not False:
        errors.append("ready_for_apply must be false "
                      "(writes are still disabled)")

    if errors:
        print(json.dumps({"status": "approval_rejected",
                          "errors": errors}, indent=2))
        return 1

    now = datetime.now(timezone.utc).isoformat()
    plan["status"] = "approved"
    plan["approved_at"] = now
    plan["approved_for"] = "single-addNote-to-Pi-Sandbox"
    plan["writes_still_disabled"] = True

    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPROVED_DIR / path.name
    dest.write_text(json.dumps(plan, indent=2))
    path.unlink()

    print(json.dumps({
        "status": "approved",
        "approved_at": now,
        "approved_for": "single-addNote-to-Pi-Sandbox",
        "writes_still_disabled": True,
        "moved_to": str(dest),
    }, indent=2))
    return 0


def cmd_apply_approved_plan(args):
    if not args.apply:
        print(json.dumps({
            "error": "--apply flag is required"}, indent=2))
        return 1
    if not args.confirm_add_note_to_pi_sandbox:
        print(json.dumps({
            "error": "Confirmation flag required: "
                     "--confirm-add-note-to-pi-sandbox"}, indent=2))
        return 1

    path = _resolve_plan(args.plan_file, allowed_dirs=(APPROVED_DIR,))
    plan = json.loads(path.read_text())
    errors = []

    if plan.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, "
                      f"got {plan.get('schema_version')}")
    if plan.get("plan_type") != "create-basic-note":
        errors.append(f"plan_type must be 'create-basic-note', "
                      f"got {plan.get('plan_type')}")
    if plan.get("status") != "approved":
        errors.append(f"status must be 'approved', "
                      f"got {plan.get('status')}")
    if plan.get("approved_for") != "single-addNote-to-Pi-Sandbox":
        errors.append("approved_for must be "
                      "'single-addNote-to-Pi-Sandbox'")
    if plan.get("policy", {}).get("target_deck") != "Pi Sandbox":
        errors.append("target_deck must be 'Pi Sandbox'")
    if plan.get("policy", {}).get("model_name") != "Basic":
        errors.append("model_name must be 'Basic'")

    note = plan.get("note", {})
    if set(note.keys()) != {"front", "back"}:
        errors.append("note fields must be exactly 'front' and 'back'")
    else:
        front = (note.get("front") or "").strip()
        back = (note.get("back") or "").strip()
        if not front:
            errors.append("Front field is empty")
        if not back:
            errors.append("Back field is empty")

    tags = plan.get("policy", {}).get("required_tags", [])
    if "pi-generated" not in tags:
        errors.append("required_tags must include 'pi-generated'")
    if "needs-human-review" not in tags:
        errors.append("required_tags must include 'needs-human-review'")
    if plan.get("sync_will_be_called") is not False:
        errors.append("sync_will_be_called must be false")
    if plan.get("applied_at") is not None:
        errors.append("plan is already marked as applied")

    future = plan.get("future_actions_if_apply_is_enabled", [])
    forbidden = {"addNotes", "createDeck", "changeDeck", "saveDeckConfig",
                 "updateNoteFields", "deleteNotes", "addTags", "removeTags",
                 "replaceTags", "clearUnusedTags", "storeMediaFile",
                 "retrieveMediaFile", "deleteMediaFile", "createModel",
                 "updateModelStyling", "sync"}
    if forbidden.intersection(future):
        errors.append(f"plan contains forbidden future actions: "
                      f"{forbidden.intersection(future)}")

    if errors:
        print(json.dumps({"status": "apply_rejected",
                          "errors": errors}, indent=2))
        return 1

    actions = []
    try:
        anki_request("version")
        actions.append("version")

        decks = anki_request("deckNames")
        actions.append("deckNames")
        if "Pi Sandbox" not in decks:
            errors.append("Deck 'Pi Sandbox' no longer exists")

        models = anki_request("modelNames")
        actions.append("modelNames")
        if "Basic" not in models:
            errors.append("Note type 'Basic' no longer exists")

        fields = anki_request("modelFieldNames", {"modelName": "Basic"})
        actions.append("modelFieldNames")
        if fields != ["Front", "Back"]:
            errors.append(f"Basic fields mismatch: got {fields}")

        can_add = anki_request("canAddNotes", {
            "notes": [{
                "deckName": "Pi Sandbox",
                "modelName": "Basic",
                "fields": {"Front": front, "Back": back},
                "tags": ["pi-generated", "needs-human-review"],
            }]
        })
        actions.append("canAddNotes")
        addable = can_add[0] if can_add else False
        if not addable:
            errors.append("Note is not addable "
                          "(canAddNotes returned false)")
    except Exception as e:
        errors.append(f"AnkiConnect re-validation failed: {e}")

    if errors:
        print(json.dumps({"status": "apply_rejected",
                          "validation_actions": actions,
                          "errors": errors}, indent=2))
        return 1

    note_id = None
    try:
        result = anki_request("addNote", {
            "note": {
                "deckName": "Pi Sandbox",
                "modelName": "Basic",
                "fields": {"Front": front, "Back": back},
                "tags": ["pi-generated", "needs-human-review"],
            }
        })
        actions.append("addNote")
        note_id = result
    except Exception as e:
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        failed = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_plan": str(path),
            "status": "apply_failed",
            "error": str(e),
            "actions_called": actions,
            "sync_called": False,
        }
        failed_file = FAILED_DIR / f"failed-{path.stem}.json"
        failed_file.write_text(json.dumps(failed, indent=2))
        print(json.dumps(failed, indent=2))
        return 1

    APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    plan["status"] = "applied"
    plan["applied_at"] = now
    plan["note_id"] = note_id

    applied_file = APPLIED_DIR / path.name
    applied_file.write_text(json.dumps(plan, indent=2))

    result_json = {
        "schema_version": 1,
        "timestamp": now,
        "source_plan": path.name,
        "note_id": note_id,
        "status": "applied",
        "actions_called": actions,
        "sync_called": False,
        "target_deck": "Pi Sandbox",
        "model_name": "Basic",
        "tags": ["pi-generated", "needs-human-review"],
    }
    result_file = APPLIED_DIR / f"result-{path.stem}.json"
    result_file.write_text(json.dumps(result_json, indent=2))

    # Remove the approved plan only after successful bookkeeping
    try:
        path.unlink()
    except Exception as e:
        print(json.dumps({
            "status": "applied_with_bookkeeping_warning",
            "note_id": note_id,
            "result_file": str(result_file),
            "applied_file": str(applied_file),
            "warning": f"Approved plan not removed: {e}",
            "sync_called": False,
        }, indent=2))
        return 0

    print(json.dumps(result_json, indent=2))
    return 0


def cmd_inspect_applied_note(args):
    path = _resolve_plan(args.applied_result_file, allowed_dirs=(APPLIED_DIR,))
    result = json.loads(path.read_text())
    note_id = result.get("note_id")
    if not note_id:
        print(json.dumps({"error": "Applied result has no note_id"},
                         indent=2))
        return 1
    try:
        info = anki_request("notesInfo", {"notes": [note_id]})
    except Exception as e:
        print(json.dumps({"error": f"notesInfo failed: {e}"},
                         indent=2))
        return 1
    if not info:
        print(json.dumps({"error": f"Note {note_id} not found in Anki"},
                         indent=2))
        return 1
    note = info[0]
    tags = note.get("tags", [])
    report = {
        "note_id": note_id,
        "fields": {k: v.get("value", "") for k, v
                    in note.get("fields", {}).items()},
        "tags": tags,
        "cards": note.get("cards", []),
        "has_pi_generated": "pi-generated" in tags,
        "has_needs_human_review": "needs-human-review" in tags,
        "deploy_state": result.get("status"),
        "source_result": path.name,
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_plan_rollback_note(args):
    if not args.confirm_plan_rollback_pi_sandbox_note:
        print(json.dumps({
            "error": "Confirmation flag required: "
                     "--confirm-plan-rollback-pi-sandbox-note"},
            indent=2))
        return 1

    path = _resolve_plan(args.applied_result_file, allowed_dirs=(APPLIED_DIR,))
    result = json.loads(path.read_text())
    errors = []

    note_id = result.get("note_id")
    if not note_id:
        errors.append("Applied result has no note_id")

    if result.get("target_deck") != "Pi Sandbox":
        errors.append(f"target_deck must be 'Pi Sandbox', "
                      f"got {result.get('target_deck')}")
    if result.get("sync_called") is not False:
        errors.append("sync_called must be false")

    if errors:
        print(json.dumps({"status": "rollback_plan_rejected",
                          "errors": errors}, indent=2))
        return 1

    # Fetch live note info
    try:
        info = anki_request("notesInfo", {"notes": [note_id]})
    except Exception as e:
        print(json.dumps({"status": "rollback_plan_rejected",
                          "error": f"notesInfo failed: {e}"},
                         indent=2))
        return 1

    if not info:
        errors.append(f"Note {note_id} no longer exists in Anki")
    else:
        note = info[0]
        tags = note.get("tags", [])
        fields = note.get("fields", {})
        if "pi-generated" not in tags:
            errors.append("Note missing tag 'pi-generated'")
        if "needs-human-review" not in tags:
            errors.append("Note missing tag 'needs-human-review'")
        if "Front" not in fields or "Back" not in fields:
            errors.append("Note missing Front or Back fields")

    if errors:
        print(json.dumps({"status": "rollback_plan_rejected",
                          "errors": errors}, indent=2))
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rollback = {
        "schema_version": 1,
        "rollback_type": "delete-created-basic-note",
        "created_at": ts,
        "source_applied_result": path.name,
        "note_id": note_id,
        "captured_fields": {
            "Front": fields.get("Front", {}).get("value", ""),
            "Back": fields.get("Back", {}).get("value", ""),
        },
        "captured_tags": note.get("tags", []),
        "status": "rollback-planned",
        "future_action_if_enabled": "deleteNotes",
        "rollback_execution_enabled": False,
        "warning": "Deleting a note is destructive and permanent. "
                    "Ensure you have a backup before proceeding.",
    }

    ROLLBACK_PLANS_DIR.mkdir(parents=True, exist_ok=True)
    rollback_file = ROLLBACK_PLANS_DIR / f"rollback-{ts}.json"
    rollback_file.write_text(json.dumps(rollback, indent=2))

    print(json.dumps({
        "status": "rollback-planned",
        "note_id": note_id,
        "rollback_file": str(rollback_file),
        "rollback_execution_enabled": False,
    }, indent=2))
    return 0


def cmd_approve_rollback_plan(args):
    if not args.confirm_approve_delete_pi_sandbox_note:
        print(json.dumps({
            "error": "Confirmation flag required: "
                     "--confirm-approve-delete-pi-sandbox-note"},
            indent=2))
        return 1

    path = _resolve_plan(args.plan_file,
                          allowed_dirs=(ROLLBACK_PLANS_DIR,))
    plan = json.loads(path.read_text())
    errors = []

    if plan.get("rollback_type") != "delete-created-basic-note":
        errors.append(f"rollback_type must be 'delete-created-basic-note', "
                      f"got {plan.get('rollback_type')}")
    if plan.get("rollback_execution_enabled") is not False:
        errors.append("rollback_execution_enabled must be false")

    note_id = plan.get("note_id")
    if not note_id or not isinstance(note_id, int):
        errors.append("note_id must be a positive integer")

    captured_tags = plan.get("captured_tags", [])
    if "pi-generated" not in captured_tags:
        errors.append("captured_tags must include 'pi-generated'")
    if "needs-human-review" not in captured_tags:
        errors.append("captured_tags must include 'needs-human-review'")

    captured_fields = plan.get("captured_fields", {})
    if "Front" not in captured_fields or "Back" not in captured_fields:
        errors.append("captured_fields must include Front and Back")

    future = plan.get("future_action_if_enabled")
    if future and future != "deleteNotes":
        errors.append(f"future_action_if_enabled must be 'deleteNotes', "
                      f"got {future}")

    if errors:
        print(json.dumps({"status": "rollback_approval_rejected",
                          "errors": errors}, indent=2))
        return 1

    # Live note verification
    try:
        info = anki_request("notesInfo", {"notes": [note_id]})
    except Exception as e:
        print(json.dumps({"status": "rollback_approval_rejected",
                          "error": f"notesInfo failed: {e}"},
                         indent=2))
        return 1

    if not info:
        errors.append(f"Note {note_id} no longer exists in Anki")
        print(json.dumps({"status": "rollback_approval_rejected",
                          "errors": errors}, indent=2))
        return 1

    note = info[0]
    live_tags = note.get("tags", [])
    live_fields = note.get("fields", {})

    if "pi-generated" not in live_tags:
        errors.append("Live note missing tag 'pi-generated'")
    if "needs-human-review" not in live_tags:
        errors.append("Live note missing tag 'needs-human-review'")
    if "Front" not in live_fields or "Back" not in live_fields:
        errors.append("Live note missing Front or Back fields")

    live_front = live_fields.get("Front", {}).get("value", "")
    live_back = live_fields.get("Back", {}).get("value", "")
    if live_front != captured_fields.get("Front", ""):
        errors.append("Live Front field does not match captured plan")
    if live_back != captured_fields.get("Back", ""):
        errors.append("Live Back field does not match captured plan")

    if errors:
        print(json.dumps({"status": "rollback_approval_rejected",
                          "errors": errors}, indent=2))
        return 1

    now = datetime.now(timezone.utc).isoformat()
    plan["status"] = "rollback-approved"
    plan["rollback_approved_at"] = now
    plan["rollback_approved_for"] = "single-deleteNotes-from-Pi-Sandbox"
    plan["rollback_write_enabled"] = True

    ROLLBACK_APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    dest = ROLLBACK_APPROVED_DIR / path.name
    dest.write_text(json.dumps(plan, indent=2))
    path.unlink()

    print(json.dumps({
        "status": "rollback-approved",
        "rollback_approved_at": now,
        "rollback_approved_for": "single-deleteNotes-from-Pi-Sandbox",
        "rollback_write_enabled": True,
        "note_id": note_id,
        "moved_to": str(dest),
    }, indent=2))
    return 0


def cmd_apply_rollback_plan(args):
    if not args.apply:
        print(json.dumps({
            "error": "--apply flag is required"}, indent=2))
        return 1
    if not args.confirm_delete_pi_sandbox_note:
        print(json.dumps({
            "error": "Confirmation flag required: "
                     "--confirm-delete-pi-sandbox-note"}, indent=2))
        return 1

    path = _resolve_plan(args.plan_file,
                          allowed_dirs=(ROLLBACK_APPROVED_DIR,))
    plan = json.loads(path.read_text())
    errors = []

    # ── Plan validation ─────────────────────────────────────
    if plan.get("status") != "rollback-approved":
        errors.append(f"status must be 'rollback-approved', "
                      f"got {plan.get('status')}")
    if plan.get("rollback_type") != "delete-created-basic-note":
        errors.append(f"rollback_type must be 'delete-created-basic-note', "
                      f"got {plan.get('rollback_type')}")

    note_id = plan.get("note_id")
    if not note_id or not isinstance(note_id, int):
        errors.append("note_id must be a positive integer")

    captured_tags = plan.get("captured_tags", [])
    if "pi-generated" not in captured_tags:
        errors.append("captured_tags must include 'pi-generated'")
    if "needs-human-review" not in captured_tags:
        errors.append("captured_tags must include 'needs-human-review'")

    captured_fields = plan.get("captured_fields", {})
    if "Front" not in captured_fields or "Back" not in captured_fields:
        errors.append("captured_fields must include Front and Back")

    if errors:
        print(json.dumps({"status": "rollback_apply_rejected",
                          "errors": errors}, indent=2))
        return 1

    # ── Live re-validation ──────────────────────────────────
    actions = []
    try:
        anki_request("version")
        actions.append("version")

        info = anki_request("notesInfo", {"notes": [note_id]})
        actions.append("notesInfo")
        if not info:
            errors.append(f"Note {note_id} no longer exists")
        else:
            note = info[0]
            live_tags = note.get("tags", [])
            live_fields = note.get("fields", {})
            if "pi-generated" not in live_tags:
                errors.append("Live note missing tag 'pi-generated'")
            if "needs-human-review" not in live_tags:
                errors.append("Live note missing tag 'needs-human-review'")
            live_front = live_fields.get("Front", {}).get("value", "")
            live_back = live_fields.get("Back", {}).get("value", "")
            if live_front != captured_fields.get("Front", ""):
                errors.append("Live Front field does not match captured")
            if live_back != captured_fields.get("Back", ""):
                errors.append("Live Back field does not match captured")
    except Exception as e:
        errors.append(f"AnkiConnect re-validation failed: {e}")

    if errors:
        print(json.dumps({"status": "rollback_apply_rejected",
                          "validation_actions": actions,
                          "errors": errors}, indent=2))
        return 1

    # ── Live delete ─────────────────────────────────────────
    try:
        anki_request("deleteNotes", {"notes": [note_id]})
        actions.append("deleteNotes")
    except Exception as e:
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        failed = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_plan": str(path),
            "status": "rollback_delete_failed",
            "error": str(e),
            "actions_called": actions,
            "sync_called": False,
        }
        failed_file = FAILED_DIR / f"rollback-failed-{path.stem}.json"
        failed_file.write_text(json.dumps(failed, indent=2))
        print(json.dumps(failed, indent=2))
        return 1

    # ── Post-delete bookkeeping ─────────────────────────────
    ROLLBACK_APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    plan["status"] = "rollback-applied"
    plan["rollback_applied_at"] = now

    applied_file = ROLLBACK_APPLIED_DIR / path.name
    applied_file.write_text(json.dumps(plan, indent=2))

    result_json = {
        "schema_version": 1,
        "timestamp": now,
        "source_rollback_plan": path.name,
        "deleted_note_id": note_id,
        "status": "rollback-applied",
        "actions_called": actions,
        "sync_called": False,
        "captured_fields": captured_fields,
        "captured_tags": captured_tags,
    }
    result_file = ROLLBACK_APPLIED_DIR / f"result-{path.stem}.json"
    result_file.write_text(json.dumps(result_json, indent=2))

    try:
        path.unlink()
    except Exception as e:
        print(json.dumps({
            "status": "rollback_applied_with_warning",
            "deleted_note_id": note_id,
            "result_file": str(result_file),
            "applied_file": str(applied_file),
            "warning": f"Rollback-approved plan not removed: {e}",
            "sync_called": False,
        }, indent=2))
        return 0

    print(json.dumps(result_json, indent=2))
    return 0


def cmd_plan_create_notes_batch(args):
    """Create a batch plan artifact from a JSON input file. Planning-only."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(json.dumps({"status": "rejected",
                          "error": f"Input file not found: {input_path}"},
                         indent=2))
        return 1
    try:
        data = json.loads(input_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(json.dumps({"status": "rejected",
                          "error": f"Invalid JSON: {e}"},
                         indent=2))
        return 1
    if not isinstance(data, dict):
        print(json.dumps({"status": "rejected",
                          "error": "Input must be a JSON object, not an array"},
                         indent=2))
        return 1
    errors = []
    allowed_top_keys = {"deck", "model", "max_live_generated", "notes"}
    unknown_keys = set(data.keys()) - allowed_top_keys
    if unknown_keys:
        errors.append({"field": "(top-level)",
                       "error": f"Unknown key(s): {sorted(unknown_keys)}"})
    deck = data.get("deck", "")
    if not isinstance(deck, str) or not deck.strip():
        errors.append({"field": "deck", "error": "Must be a non-empty string"})
    model = data.get("model", "")
    if not isinstance(model, str) or not model.strip():
        errors.append({"field": "model", "error": "Must be a non-empty string"})
    max_live = data.get("max_live_generated")
    if not isinstance(max_live, int) or max_live < 1:
        errors.append({"field": "max_live_generated",
                       "error": "Must be a positive integer"})
    notes = data.get("notes", [])
    if not isinstance(notes, list) or len(notes) == 0:
        errors.append({"field": "notes",
                       "error": "Must be a non-empty list"})
    elif len(notes) > args.max_batch_size:
        errors.append({"field": "notes",
                       "error": f"Batch size {len(notes)} exceeds max {args.max_batch_size}"})
    allowed_note_keys = {"front", "back", "tags"}
    allowed_tags = {"pi-generated", "needs-human-review"}
    for i, note in enumerate(notes):
        if not isinstance(note, dict):
            errors.append({"field": f"notes[{i}]",
                           "error": "Must be a JSON object"})
            continue
        unknown_note_keys = set(note.keys()) - allowed_note_keys
        if unknown_note_keys:
            errors.append({"field": f"notes[{i}]",
                           "error": f"Unknown key(s): {sorted(unknown_note_keys)}"})
        front = note.get("front", "")
        if not isinstance(front, str) or not front.strip():
            errors.append({"field": f"notes[{i}].front",
                           "error": "Must be a non-empty string"})
        back = note.get("back", "")
        if not isinstance(back, str) or not back.strip():
            errors.append({"field": f"notes[{i}].back",
                           "error": "Must be a non-empty string"})
        tags = note.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            errors.append({"field": f"notes[{i}].tags",
                           "error": "Must be a list of strings"})
        elif set(tags) != allowed_tags:
            errors.append({"field": f"notes[{i}].tags",
                           "error": f"Tags must be exactly {sorted(allowed_tags)}, got {sorted(tags)}"})
    if errors:
        print(json.dumps({"status": "rejected", "errors": errors}, indent=2))
        return 1
    actions = []
    try:
        anki_request("version")
        actions.append("version")
        decks = anki_request("deckNames")
        actions.append("deckNames")
        if deck.strip() not in decks:
            print(json.dumps({"status": "rejected",
                              "errors": [{"field": "deck",
                                          "error": f"Deck '{deck.strip()}' does not exist"}]},
                             indent=2))
            return 1
        models = anki_request("modelNames")
        actions.append("modelNames")
        if model.strip() not in models:
            print(json.dumps({"status": "rejected",
                              "errors": [{"field": "model",
                                          "error": f"Model '{model.strip()}' not found"}]},
                             indent=2))
            return 1
        fields = anki_request("modelFieldNames", {"modelName": model.strip()})
        actions.append("modelFieldNames")
        if fields != ["Front", "Back"]:
            print(json.dumps({"status": "rejected",
                              "errors": [{"field": "model",
                                          "error": f"Model fields mismatch: expected ['Front','Back'], got {fields}"}]},
                             indent=2))
            return 1
        note_ids = anki_request("findNotes", {
            "query": 'deck:"Pi Sandbox" tag:pi-generated tag:needs-human-review'})
        actions.append("findNotes")
        live_count = len(note_ids)
        existing_notes = []
        if note_ids:
            info = anki_request("notesInfo", {"notes": note_ids})
            actions.append("notesInfo")
            for note in info:
                if note and note.get("fields"):
                    nid = note.get("noteId")
                    existing_notes.append({
                        "note_id": nid,
                        "front": note["fields"].get("Front", {}).get("value", "").strip(),
                        "back": note["fields"].get("Back", {}).get("value", "").strip(),
                    })
        if live_count + len(notes) > max_live:
            print(json.dumps({"status": "rejected",
                              "errors": [{"field": "max_live_generated",
                                          "error": f"live({live_count}) + batch({len(notes)}) = {live_count + len(notes)} > max({max_live})"}]},
                             indent=2))
            return 1
        proposed = []
        for i, note in enumerate(notes):
            front = note["front"].strip()
            back = note["back"].strip()
            dup_ids = []
            for en in existing_notes:
                if en["front"] == front and en["back"] == back:
                    dup_ids.append(en["note_id"])
            for j in range(i):
                if notes[j]["front"].strip() == front and notes[j]["back"].strip() == back:
                    print(json.dumps({"status": "rejected",
                                      "errors": [{"field": f"notes[{i}]",
                                                  "error": f"Duplicate within batch at index {j}"}]},
                                     indent=2))
                    return 1
            can_add_result = anki_request("canAddNotes", {
                "notes": [{
                    "deckName": deck.strip(),
                    "modelName": model.strip(),
                    "fields": {"Front": front, "Back": back},
                    "tags": ["pi-generated", "needs-human-review"],
                }]})
            actions.append("canAddNotes")
            addable = can_add_result[0] if can_add_result else False
            if dup_ids:
                print(json.dumps({"status": "rejected",
                                  "errors": [{"field": f"notes[{i}]",
                                              "error": f"Exact duplicate of existing note(s): {dup_ids}"}]},
                                 indent=2))
                return 1
            if not addable:
                print(json.dumps({"status": "rejected",
                                  "errors": [{"field": f"notes[{i}]",
                                              "error": "Note is not addable (canAddNotes returned false)"}]},
                                 indent=2))
                return 1
            proposed.append({
                "index": i + 1,
                "fields": {"Front": front, "Back": back},
                "tags": ["pi-generated", "needs-human-review"],
                "preflight": {"can_add": True,
                              "duplicate_found": False,
                              "duplicate_note_ids": []},
            })
    except Exception as e:
        print(json.dumps({"status": "rejected",
                          "error": f"AnkiConnect validation failed: {e}"},
                         indent=2))
        return 1
    BATCH_PLANS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_plan = {
        "schema_version": "anki-safe-writer.batch-plan.v1",
        "plan_type": "create-notes-batch",
        "status": "planned",
        "created_at_utc": ts,
        "deck": deck.strip(),
        "model": model.strip(),
        "required_tags": ["pi-generated", "needs-human-review"],
        "max_live_generated": max_live,
        "live_generated_count_at_plan_time": live_count,
        "proposed_note_count": len(notes),
        "estimated_live_generated_count_after_apply": live_count + len(notes),
        "apply_supported": False,
        "approval_supported": False,
        "anki_connect_actions_used": sorted(set(actions)),
        "notes": proposed,
    }
    batch_file = BATCH_PLANS_DIR / f"batch-plan-{ts}.json"
    batch_file.write_text(json.dumps(batch_plan, indent=2))
    print(json.dumps({"status": "planned",
                      "batch_plan_file": str(batch_file),
                      "note_count": len(proposed),
                      "apply_supported": False,
                      "approval_supported": False}, indent=2))
    return 0


def cmd_inspect_batch_plan(args):
    path = _resolve_plan(args.plan_file, allowed_dirs=(BATCH_PLANS_DIR,))
    plan = json.loads(path.read_text())
    print(json.dumps(plan, indent=2))
    return 0


def cmd_abort_batch_plan(args):
    path = _resolve_plan(args.plan_file, allowed_dirs=(BATCH_PLANS_DIR,))
    plan = json.loads(path.read_text())
    plan["status"] = "aborted"
    plan["aborted_at_utc"] = datetime.now(timezone.utc).isoformat()
    BATCH_ABORTED_DIR.mkdir(parents=True, exist_ok=True)
    dest = BATCH_ABORTED_DIR / path.name
    dest.write_text(json.dumps(plan, indent=2))
    path.unlink()
    print(json.dumps({"status": "aborted", "moved_to": str(dest)}, indent=2))
    return 0



def _safe_metadata(path):
    """Read key metadata from a plan JSON file without failing on errors."""
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    meta = {}
    for k in ("status", "plan_type", "rollback_type", "note_id",
              "deleted_note_id", "target_deck"):
        v = data.get(k)
        if v is not None:
            meta[k] = v
    if "note" in data and isinstance(data["note"], dict):
        meta["note_front"] = data["note"].get("front", "")[:60]
    if "policy" in data and isinstance(data["policy"], dict):
        meta["target_deck"] = data["policy"].get("target_deck")
    return meta


def _list_dir(dir_path):
    """List JSON files in a directory with metadata. No AnkiConnect calls."""
    if not dir_path.exists():
        return {"directory_exists": False, "files": []}
    files = []
    for f in sorted(dir_path.iterdir(), key=lambda x: x.name):
        if f.suffix != ".json":
            continue
        st = f.stat()
        entry = {
            "filename": f.name,
            "path": str(f),
            "size_bytes": st.st_size,
            "modified_time": datetime.fromtimestamp(
                st.st_mtime, tz=timezone.utc).isoformat(),
        }
        entry["metadata"] = _safe_metadata(f)
        files.append(entry)
    return {"directory_exists": True, "files": files}


def cmd_status(args):
    """Report local state directory counts. No AnkiConnect calls."""
    result = {"state_root": str(STATE_ROOT), "directories": {}}
    for name, d in _TRACKED_DIRS.items():
        listing = _list_dir(d)
        result["directories"][name] = {
            "exists": listing["directory_exists"],
            "file_count": len(listing["files"]),
        }
    print(json.dumps(result, indent=2))
    return 0


def _make_list_cmd(dir_path):
    """Factory for list-* commands."""
    def cmd(args):
        result = _list_dir(dir_path)
        print(json.dumps(result, indent=2))
        return 0
    return cmd


cmd_list_plans = _make_list_cmd(PLANS_DIR)
cmd_list_approved = _make_list_cmd(APPROVED_DIR)
cmd_list_applied = _make_list_cmd(APPLIED_DIR)
cmd_list_rollback_plans = _make_list_cmd(ROLLBACK_PLANS_DIR)
cmd_list_rollback_approved = _make_list_cmd(ROLLBACK_APPROVED_DIR)
cmd_list_batch_plans = _make_list_cmd(BATCH_PLANS_DIR)
cmd_list_batch_aborted = _make_list_cmd(BATCH_ABORTED_DIR)
def cmd_ledger_audit(args):
    """Reconcile local state artifacts. Optionally check live Anki."""
    report = {
        "state_root": str(STATE_ROOT),
        "mode": "local-only",
        "counts": {},
        "applied_records": [],
        "rollback_records": [],
        "linked_lifecycles": [],
        "unmatched_applied": [],
        "unmatched_rollback_applied": [],
        "pending_items": [],
        "anomalies": [],
        "live_check": "skipped",
    }

    # Read all state dirs
    all_data = {}
    for name, d in _TRACKED_DIRS.items():
        listing = _list_dir(d)
        report["counts"][name] = {
            "exists": listing["directory_exists"],
            "file_count": len(listing["files"]),
        }
        all_data[name] = [json.loads(Path(f["path"]).read_text())
                          for f in listing["files"]]

    # Applied records
    applied_ids = set()
    for f in all_data.get("applied", []):
        rec = {
            "filename": f.get("source_plan", "") or "unknown",
            "note_id": f.get("note_id"),
            "status": f.get("status"),
            "target_deck": f.get("target_deck"),
            "model_name": f.get("model_name"),
            "tags": f.get("tags"),
            "timestamp": f.get("timestamp"),
            "sync_called": f.get("sync_called"),
        }
        report["applied_records"].append(rec)
        nid = f.get("note_id")
        if nid:
            if nid in applied_ids:
                report["anomalies"].append(
                    f"Duplicate note_id {nid} across applied results")
            applied_ids.add(nid)
        else:
            report["anomalies"].append(
                f"Applied result missing note_id: {f.get('source_plan')}")

    # Rollback-applied records
    deleted_ids = set()
    for f in all_data.get("rollback-applied", []):
        rec = {
            "filename": f.get("source_rollback_plan", "") or "unknown",
            "deleted_note_id": f.get("deleted_note_id"),
            "status": f.get("status"),
            "timestamp": f.get("timestamp"),
            "captured_fields": f.get("captured_fields"),
            "captured_tags": f.get("captured_tags"),
            "sync_called": f.get("sync_called"),
        }
        report["rollback_records"].append(rec)
        did = f.get("deleted_note_id")
        if did:
            if did in deleted_ids:
                report["anomalies"].append(
                    f"Duplicate deleted_note_id {did} across rollback-applied")
            deleted_ids.add(did)
        else:
            report["anomalies"].append(
                "Rollback-applied missing deleted_note_id")

    # Link lifecycles
    for rec in report["applied_records"]:
        nid = rec.get("note_id")
        if not nid:
            continue
        match = [r for r in report["rollback_records"]
                 if r.get("deleted_note_id") == nid]
        if match:
            report["linked_lifecycles"].append({
                "note_id": nid,
                "applied_filename": rec.get("filename"),
                "rollback_filename": match[0].get("filename"),
                "match_method": "note_id",
                "weak": False,
            })
        else:
            report["unmatched_applied"].append({
                "note_id": nid,
                "filename": rec.get("filename"),
            })
            report["anomalies"].append(
                f"Applied note_id {nid} has no matching rollback-applied result")

    for rec in report["rollback_records"]:
        did = rec.get("deleted_note_id")
        if not did:
            continue
        match = [r for r in report["applied_records"]
                 if r.get("note_id") == did]
        if not match:
            report["unmatched_rollback_applied"].append({
                "deleted_note_id": did,
                "filename": rec.get("filename"),
            })
            report["anomalies"].append(
                f"Rollback-applied note_id {did} has no matching applied "
                "result (may be from earlier test)")

    # Pending items
    for name in ("plans", "approved"):
        for f in all_data.get(name, []):
            report["pending_items"].append({
                "source": name,
                "filename": f.get("source_plan", "") or "unknown",
                "status": f.get("status"),
            })

    # Failed artifacts
    if all_data.get("failed"):
        report["anomalies"].append(
            f"{len(all_data['failed'])} failed artifact(s) present")

    # Malformed JSON
    for name, d in _TRACKED_DIRS.items():
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix != ".json":
                continue
            try:
                json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                report["anomalies"].append(
                    f"Malformed JSON in {name}/{f.name}")

    # Live check
    if args.check_live:
        report["mode"] = "with-live-check"
        report["live_check"] = "running"
        try:
            anki_request("version")
        except Exception as e:
            report["live_check"] = f"error: {e}"
            print(json.dumps(report, indent=2))
            return 1

        for rec in report["applied_records"]:
            nid = rec.get("note_id")
            if not nid:
                rec["live_present"] = False
                rec["live_check_error"] = "no note_id"
                continue
            try:
                info = anki_request("notesInfo", {"notes": [nid]})
                if info and info[0].get("fields"):
                    note = info[0]
                    tags = note.get("tags", [])
                    rec["live_present"] = True
                    rec["live_fields"] = {
                        k: v.get("value", "") for k, v
                        in note.get("fields", {}).items()}
                    rec["live_tags"] = tags
                    rec["live_cards"] = note.get("cards", [])
                    rec["live_has_pi_generated"] = "pi-generated" in tags
                    rec["live_has_needs_human_review"] = (
                        "needs-human-review" in tags)
                else:
                    rec["live_present"] = False
                    rec["live_check_error"] = "note not found in Anki"
            except Exception as e:
                rec["live_present"] = False
                rec["live_check_error"] = str(e)

        # findNotes query for Pi Sandbox generated notes
        try:
            ids = anki_request("findNotes", {
                "query": 'deck:"Pi Sandbox" tag:pi-generated tag:needs-human-review'})
            report["pi_sandbox_generated_notes"] = {
                "count": len(ids),
                "note_ids": ids,
            }
        except Exception as e:
            report["pi_sandbox_generated_notes"] = {
                "count": -1,
                "error": str(e),
            }

        report["live_check"] = "completed"

    print(json.dumps(report, indent=2))
    return 0


def cmd_preflight_create_note(args):
    """Read-only preflight check before planning a note. No local state mutation."""
    front = (args.front or "").strip()
    back = (args.back or "").strip()
    max_live = max(args.max_live_generated, 1)

    report = {
        "status": "ok",
        "target_deck": "Pi Sandbox",
        "model_name": "Basic",
        "proposed_fields": {"Front": front, "Back": back},
        "live_generated_count": 0,
        "max_live_generated": max_live,
        "duplicate_found": False,
        "duplicate_note_ids": [],
        "existing_generated_notes": [],
        "allowed_to_plan": True,
        "errors": [],
    }

    try:
        anki_request("version")
    except Exception as e:
        report["status"] = "blocked"
        report["allowed_to_plan"] = False
        report["errors"].append(f"AnkiConnect version check failed: {e}")
        print(json.dumps(report, indent=2))
        return 1

    try:
        note_ids = anki_request("findNotes", {
            "query": 'deck:"Pi Sandbox" tag:pi-generated tag:needs-human-review'})
    except Exception as e:
        report["status"] = "blocked"
        report["allowed_to_plan"] = False
        report["errors"].append(f"findNotes failed: {e}")
        print(json.dumps(report, indent=2))
        return 1

    report["live_generated_count"] = len(note_ids)

    if note_ids:
        try:
            info = anki_request("notesInfo", {"notes": note_ids})
        except Exception as e:
            report["status"] = "blocked"
            report["allowed_to_plan"] = False
            report["errors"].append(f"notesInfo failed: {e}")
            print(json.dumps(report, indent=2))
            return 1

        for note in info:
            if not note or not note.get("fields"):
                continue
            nid = note.get("noteId")
            fields = note.get("fields", {})
            existing_front = fields.get("Front", {}).get("value", "").strip()
            existing_back = fields.get("Back", {}).get("value", "").strip()
            tags = note.get("tags", [])
            entry = {
                "note_id": nid,
                "front": existing_front,
                "back": existing_back,
                "tags": tags,
            }
            report["existing_generated_notes"].append(entry)

            if existing_front == front and existing_back == back:
                report["duplicate_found"] = True
                if nid:
                    report["duplicate_note_ids"].append(nid)

    if report["duplicate_found"]:
        report["status"] = "blocked"
        report["allowed_to_plan"] = False
        report["errors"].append(
            f"Exact duplicate Front/Back already exists in Pi Sandbox")

    if report["live_generated_count"] >= max_live:
        report["status"] = "blocked"
        report["allowed_to_plan"] = False
        report["errors"].append(
            f"Live generated note count ({report['live_generated_count']}) "
            f"meets or exceeds max ({max_live})")

    print(json.dumps(report, indent=2))
    return 0 if report["allowed_to_plan"] else 1


cmd_list_rollback_applied = _make_list_cmd(ROLLBACK_APPLIED_DIR)


def main():
    parser = argparse.ArgumentParser(
        description="anki-safe-writer: dry-run note planner for Pi Sandbox")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status",
                        help="Show local state directory status")

    p = sub.add_parser("ledger-audit",
                        help="Reconcile local state artifacts "
                             "(optional --check-live for read-only Anki check)")
    p.add_argument("--check-live", action="store_true",
                    help="Check live Anki for applied notes (read-only)")

    for cmd_name in ("list-plans", "list-approved", "list-applied",
                     "list-rollback-plans", "list-rollback-approved",
                     "list-rollback-applied",
                     "list-batch-plans", "list-batch-aborted"):
        p = sub.add_parser(cmd_name, help=f"List files in {cmd_name.split('-', 1)[1]}/")

    p = sub.add_parser("preflight-create-note",
                        help="Read-only check before planning a note "
                             "(no local mutation)")
    p.add_argument("--front", required=True)
    p.add_argument("--back", required=True)
    p.add_argument("--max-live-generated", type=int, default=10,
                    help="Max allowed live pi-generated notes (default: 10)")

    p = sub.add_parser("plan-create-notes-batch",
                        help="Create a batch plan from a JSON input file "
                             "(planning only)")
    p.add_argument("--input", required=True,
                    help="Path to JSON batch input file")
    p.add_argument("--max-batch-size", type=int, default=5,
                    help="Maximum number of notes per batch (default: 5)")

    p = sub.add_parser("inspect-batch-plan",
                        help="Display a batch plan file")
    p.add_argument("plan_file")

    p = sub.add_parser("abort-batch-plan",
                        help="Move a batch plan to batch-aborted/")
    p.add_argument("plan_file")

    p = sub.add_parser("plan-create-note",
                        help="Generate a dry-run plan")
    p.add_argument("--front", required=True)
    p.add_argument("--back", required=True)

    p = sub.add_parser("inspect-plan",
                        help="Display a plan file")
    p.add_argument("plan_file")

    p = sub.add_parser("approve-plan",
                        help="Approve a planned note for apply "
                             "(writes still disabled in this build)")
    p.add_argument("--confirm-approve-pi-sandbox-note",
                    action="store_true",
                    help="Confirm you want to approve this note")
    p.add_argument("plan_file")

    p = sub.add_parser("abort-plan",
                        help="Move a plan to aborted/")
    p.add_argument("plan_file")

    p = sub.add_parser("inspect-applied-note",
                        help="Inspect a note from an applied result")
    p.add_argument("applied_result_file")

    p = sub.add_parser("plan-rollback-note",
                        help="Plan a rollback for an applied note")
    p.add_argument("--confirm-plan-rollback-pi-sandbox-note",
                    action="store_true",
                    help="Confirm you want to plan a rollback")
    p.add_argument("applied_result_file")

    p = sub.add_parser("approve-rollback-plan",
                        help="Approve a rollback plan for deletion")
    p.add_argument("--confirm-approve-delete-pi-sandbox-note",
                    action="store_true",
                    help="Confirm you want to approve this rollback")
    p.add_argument("plan_file")

    p = sub.add_parser("apply-rollback-plan",
                        help="Apply an approved rollback plan to delete a note")
    p.add_argument("--apply", action="store_true",
                    help="Confirm intent to delete")
    p.add_argument("--confirm-delete-pi-sandbox-note",
                    action="store_true",
                    help="Confirm you want to delete this note")
    p.add_argument("plan_file", nargs="?", default=None)

    p = sub.add_parser("apply-approved-plan",
                        help="Apply an approved plan to Anki")
    p.add_argument("--apply", action="store_true",
                    help="Confirm intent to apply")
    p.add_argument("--confirm-add-note-to-pi-sandbox",
                    action="store_true",
                    help="Confirm you want to add this note to Pi Sandbox")
    p.add_argument("plan_file", nargs="?", default=None)

    args = parser.parse_args()
    commands = {
        "status": cmd_status,
        "preflight-create-note": cmd_preflight_create_note,
        "ledger-audit": cmd_ledger_audit,
        "list-plans": cmd_list_plans,
        "list-approved": cmd_list_approved,
        "list-applied": cmd_list_applied,
        "list-rollback-plans": cmd_list_rollback_plans,
        "list-rollback-approved": cmd_list_rollback_approved,
        "list-rollback-applied": cmd_list_rollback_applied,
        "list-batch-plans": cmd_list_batch_plans,
        "list-batch-aborted": cmd_list_batch_aborted,
        "plan-create-notes-batch": cmd_plan_create_notes_batch,
        "inspect-batch-plan": cmd_inspect_batch_plan,
        "abort-batch-plan": cmd_abort_batch_plan,
        "plan-create-note": cmd_plan_create_note,
        "inspect-plan": cmd_inspect_plan,
        "approve-plan": cmd_approve_plan,
        "abort-plan": cmd_abort_plan,
        "apply-approved-plan": cmd_apply_approved_plan,
        "inspect-applied-note": cmd_inspect_applied_note,
        "plan-rollback-note": cmd_plan_rollback_note,
        "approve-rollback-plan": cmd_approve_rollback_plan,
        "apply-rollback-plan": cmd_apply_rollback_plan,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
