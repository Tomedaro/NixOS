# anki-safe-writer

A constrained Anki writer for Pi. It is **not** a general AnkiConnect passthrough. It does not use MCP for writes.

## Purpose

- Plan a single Basic note for the `Pi Sandbox` deck.
- Approve the plan.
- Apply the approved plan (add the note).
- Inspect the applied note.
- Plan a rollback for the applied note.
- Approve the rollback.
- Apply the rollback (delete the note).
- Rollback deletion is destructive. Anki is not Git. Full rollback for some future operations may require backup/export.

## Lifecycle state machine

```
plans/ → approved/ → applied/
                 ↘ failed/

applied/ → rollback-plans/ → rollback-approved/ → rollback-applied/
                                      ↘ failed/

plans/ → aborted/

batch-plans/ → batch-aborted/
```

## Safety invariants

- Target deck: **only** `Pi Sandbox`.
- Note type: **only** `Basic`.
- Fields: **only** `Front` and `Back`.
- Required tags always added: `pi-generated`, `needs-human-review`.
- **No sync calls** at any point.
- **No deck creation** — `Pi Sandbox` must be created manually in Anki Desktop.
- **No deck movement** (`changeDeck`).
- **No deck options changes** (`saveDeckConfig`).
- **No media** — neither write, retrieve, nor delete.
- **No model/template/CSS changes**.
- **No batch support** — max batch size is 1.
- **No `$AI_DIR` usage** — runtime state is `~/.local/state/anki-safe-writer/`.
- **No direct Anki profile-file writes**.
- **No sync-server writes**.

## Allowed AnkiConnect actions by workflow

| Workflow | Allowed actions |
|----------|----------------|
| Planning (`plan-create-note`) | `version`, `deckNames`, `modelNames`, `modelFieldNames`, `canAddNotes` |
| Apply (`apply-approved-plan`) | `version`, `deckNames`, `modelNames`, `modelFieldNames`, `canAddNotes`, `addNote` |
| Inspect / rollback planning | `version`, `notesInfo`, `findNotes` |
| Rollback apply (`apply-rollback-plan`) | `version`, `notesInfo`, `deleteNotes` |
| Status / list commands | **no AnkiConnect calls** |

## Commands

| Command | Description |
|---------|-------------|
| `status` | Show local state directory counts (no AnkiConnect) |
| `list-plans` | List JSON files in `plans/` with metadata |
| `list-approved` | List files in `approved/` |
| `list-applied` | List files in `applied/` |
| `list-rollback-plans` | List files in `rollback-plans/` |
| `list-rollback-approved` | List files in `rollback-approved/` |
| `list-rollback-applied` | List files in `rollback-applied/` |
| `plan-create-note` | Dry-run plan for a Basic note in Pi Sandbox |
| `inspect-plan` | Display a plan file |
| `approve-plan` | Approve a planned note for apply |
| `apply-approved-plan` | Apply an approved plan (add note) |
| `inspect-applied-note` | Inspect a note from an applied result |
| `abort-plan` | Move a plan to aborted/ |
| `plan-rollback-note` | Plan a rollback for an applied note |
| `approve-rollback-plan` | Approve a rollback plan for deletion |
| `apply-rollback-plan` | Apply an approved rollback plan (delete note) |
| `ledger-audit` | Reconcile local state artifacts (optional `--check-live`) |
| `preflight-create-note` | Read-only duplicate/limit check before planning |
| `plan-create-notes-batch` | Create a batch plan from JSON input (planning only) |
| `inspect-batch-plan` | Display a batch plan file |
| `abort-batch-plan` | Move a batch plan to batch-aborted/ |
| `list-batch-plans` | List files in batch-plans/ |
| `list-batch-aborted` | List files in batch-aborted/ |
| `plan-update-note` | Plan an update to an existing generated note (planning only) |
| `inspect-update-plan` | Display an update plan file |
| `abort-update-plan` | Move an update plan to update-aborted/ |
| `list-update-plans` | List files in update-plans/ |
| `list-update-aborted` | List files in update-aborted/ |

## Repeated single-note workflow

Zero live generated notes is no longer required after v1.2.
Future notes require a duplicate-aware preflight before planning.
Existing generated notes are allowed. Exact duplicate Front/Back is blocked.
A `--max-live-generated` cap is required (default: 10).

```bash
# Preflight checks before planning a new note:\anki-safe-writer preflight-create-note --front "..." --back "..."

# With custom max cap:\anki-safe-writer preflight-create-note --front "..." --back "..." --max-live-generated 5
```

`preflight-create-note` is read-only. It never:
- writes to Anki
- creates local plan files
- mutates local state
- calls `sync`

## Batch planning (v1.3.0)

Batch planning is **planning-only**. Batch plans cannot be approved or applied
in v1.3.0. No batch Anki writes exist.

### Lifecycle directories

- `batch-plans/` — created batch plan artifacts
- `batch-aborted/` — aborted batch plans

### Commands

| Command | Description |
|---------|-------------|
| `plan-create-notes-batch` | Create a batch plan from JSON input |
| `inspect-batch-plan` | Display a batch plan file |
| `abort-batch-plan` | Move a batch plan to batch-aborted/ |
| `list-batch-plans` | List files in batch-plans/ |
| `list-batch-aborted` | List files in batch-aborted/ |

### Input schema

```json
{
  "deck": "Pi Sandbox",
  "model": "Basic",
  "max_live_generated": 10,
  "notes": [
    {
      "front": "Example front",
      "back": "Example back",
      "tags": ["pi-generated", "needs-human-review"]
    }
  ]
}
```

Only these keys are accepted. Unknown keys are rejected.

### CLI flags

- `--input PATH` — path to JSON input file (required)
- `--max-batch-size N` — max notes per batch (default: 5)

### Safety invariants

- **No batch Anki writes** in v1.3.0 (`apply_supported: false`, `approval_supported: false`)
- Cap rule: `current_live_generated + batch_size <= max_live_generated`
- Duplicate rules:
  - block duplicates against live generated notes
  - block duplicates within the batch
- Tags must be exactly `pi-generated` and `needs-human-review`
- Only `Pi Sandbox` deck and `Basic` model
- Only `Front` and `Back` fields

## Update planning (planning-only)

Update planning allows creating local plans for updating existing `pi-generated` notes.
**Updates are not applied.** `updateNoteFields` is never called by this version.

### Lifecycle directories

- `update-plans/` — created update plan artifacts
- `update-aborted/` — aborted update plans

### Commands

| Command | Description |
|---------|-------------|
| `plan-update-note` | Plan an update to an existing generated note |
| `inspect-update-plan` | Display an update plan file |
| `abort-update-plan` | Move an update plan to update-aborted/ |
| `list-update-plans` | List files in update-plans/ |
| `list-update-aborted` | List files in update-aborted/ |

### Eligibility requirements

- The note must have an applied record in the local ledger.
- The note must be live in Anki (`notesInfo` returns fields).
- The note must be in `Pi Sandbox` with `Basic` model.
- The note must have tags `pi-generated` and `needs-human-review`.
- The note must not have been rolled back.
- Only `Front` and `Back` can be updated.
- At least one field must differ from the current live value (no-op rejected).
- The after-state must not duplicate another existing generated note.

### Allowed AnkiConnect actions

- planning: `version`, `notesInfo`, `findNotes`
- No write actions are called.

## Test harness

The test file `test_anki_safe_writer.py` validates batch-planning safety behavior without
touching real Anki.

### How to run

```bash
PYTHONWARNINGS=default python3 modules/programs/cli/pi/anki-safe-writer/test_anki_safe_writer.py
```

Expected result: `12 tests pass with zero warnings`.

### What the tests cover

- batch command surface (all five batch-planning commands present)
- absence of batch approve/apply commands
- valid batch plan create/inspect/list/abort lifecycle
- negative schema validation (unknown keys, missing tags, batch size limits)
- duplicate-within-batch rejection
- duplicate-against-existing-live-note rejection using fake data
- max-live-generated cap rejection
- single-note approve/apply refusal for batch artifacts
- outside-path guard for batch inspection

### Safety properties

- Tests use a temporary `ANKI_SAFE_WRITER_STATE`.
- Tests use a fake local `ANKI_CONNECT_URL` on a random port.
- Tests do not contact real AnkiConnect (port 8765).
- Tests assert that forbidden write/sync actions are never called.
- Tests do not write to real Anki.
- Tests do not touch the real `~/.local/state/anki-safe-writer/` state root.

### Limitations

- The direct script runner is the supported invocation.
- The `python3 -m unittest` module-path form is not supported because the
  directory name contains a hyphen.
- The fake AnkiConnect server is intentionally minimal and does not model all
  real AnkiConnect behavior.

## Ledger audit

- `ledger-audit` — local-only. Reads all state directories, links applied records to
  rollback-applied records by `note_id`, reports anomalies, pending items, and unmatched entries.
  Makes zero AnkiConnect calls.
- `ledger-audit --check-live` — same local audit, then calls `notesInfo` for each applied note
  and `findNotes` for `Pi Sandbox` generated notes. Read-only against AnkiConnect. Never writes.
- Helps reconcile applied and rollback-applied artifacts. Historical artifacts from test runs are
  expected and reported as informational anomalies (e.g., duplicate note_id from the two-file
  applied structure, rollback plan file without `deleted_note_id`).

## Manual gates before live add

1. AnkiDroid has no conflict, failed sync, or one-way-sync prompt.
2. Desktop Anki is on the `Programming` profile.
3. A recent backup/export exists.
4. `Pi Sandbox` deck exists.
5. Human reviewed the approved plan.

## Manual gates before rollback delete

1. Human reviewed the rollback plan.
2. Note is confirmed `pi-generated`.
3. Note is in `Pi Sandbox`.
4. Human approves deletion.

## Runtime state root

```
~/.local/state/anki-safe-writer/
```

Configurable via `$ANKI_SAFE_WRITER_STATE` environment variable.
