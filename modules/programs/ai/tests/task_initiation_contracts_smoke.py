"""Adversarial smoke test for Milestone 1 task-initiation contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import Any, Callable, Mapping

from ai_system import task_initiation_contracts as c

PASSED = 0
FAILED = 0
NOW = 1_700_000_000


def check(description: str, condition: bool) -> None:
    global PASSED, FAILED
    PASSED += 1
    if not condition:
        FAILED += 1
        print(f"FAIL {description}")


def raises(code: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except c.TaskInitiationContractError as exc:
        check(f"{fn.__name__} raises {code}", exc.code == code)
    else:
        check(f"{fn.__name__} raises {code}", False)


def uid() -> str:
    return str(uuid.uuid4())


def stuck(**updates: Any) -> dict[str, Any]:
    value = {
        "schema_version": c.SCHEMA_STUCK,
        "event_id": uid(),
        "source": "tasker",
        "occurred_at_epoch": NOW,
        "task_ref": None,
        "task_description": "Write the first paragraph",
    }
    value.update(updates)
    return value


def task(revision: str | None = None, *, label: str = "Write the first paragraph") -> dict[str, Any]:
    return {
        "source": "explicit_task_ref",
        "task_ref": "Tasks/paper.md",
        "label": label,
        "source_revision": revision or hashlib.sha256(b"revision-1").hexdigest(),
    }


def proposal(**updates: Any) -> dict[str, Any]:
    value = {
        "schema_version": c.SCHEMA_PROPOSAL,
        "blocker": {"category": "too_big", "summary": "The paragraph feels large"},
        "tiny_start": {
            "kind": "digital",
            "instruction": "Write one rough sentence",
            "estimated_minutes": 3,
            "completion_signal": "One sentence exists",
        },
    }
    value.update(updates)
    return value


def card(
    interaction_id: str,
    revision: int = 1,
    *,
    base_epoch: int | None = None,
    proposal_value: Mapping[str, Any] | None = None,
    **updates: Any,
) -> dict[str, Any]:
    base = base_epoch if base_epoch is not None else NOW + revision * 100
    semantic = c.validate_proposal(proposal_value or proposal())
    value = {
        "schema_version": c.SCHEMA_CARD,
        "card_id": uid(),
        "interaction_id": interaction_id,
        "revision": revision,
        "issued_at_epoch": base + 4,
        "expires_at_epoch": base + 500,
        "title": "Start gently",
        "task_label": "Write the first paragraph",
        "blocker": semantic["blocker"],
        "tiny_start": semantic["tiny_start"],
        "start_countdown_seconds": 180,
        "actions": [
            {"id": "start", "label": "Start"},
            {"id": "shrink", "label": "Shrink"},
            {"id": "blocked", "label": "Blocked"},
            {"id": "defer", "label": "Defer"},
        ],
        "dismiss_action": "dismiss",
    }
    value.update(updates)
    return value


def response(
    card_value: Mapping[str, Any], action: str = "start", **updates: Any
) -> dict[str, Any]:
    value = {
        "schema_version": c.SCHEMA_RESPONSE,
        "response_id": uid(),
        "card_id": card_value["card_id"],
        "action": action,
        "detail": "Make it smaller" if action in {"shrink", "blocked"} else None,
        "occurred_at_epoch": card_value["issued_at_epoch"] + 10,
    }
    value.update(updates)
    return value


def receipt(card_value: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    value = {
        "schema_version": "task_initiation_card_receipt.v1",
        "receipt_id": uid(),
        "card_id": card_value["card_id"],
        "posted_at_epoch": card_value["issued_at_epoch"] + 2,
    }
    value.update(updates)
    return value


def context(
    *,
    interaction_id: str,
    revision: int,
    resolved: Mapping[str, Any],
    base_epoch: int,
    facts_updates: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    **updates: Any,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "task": {"label": resolved["label"]},
        "followup": None,
        "project_summary": None,
        "session_capsule": None,
        "recent_interactions": [],
        "helper_material": [],
    }
    if facts_updates:
        facts.update(copy.deepcopy(dict(facts_updates)))
    payload = c.api_payload_from_context({"disclosed_facts": facts}, policy=policy)
    value = {
        "schema_version": c.SCHEMA_CONTEXT,
        "context_id": uid(),
        "interaction_id": interaction_id,
        "revision": revision,
        "task_fingerprint": c.task_fingerprint(resolved),
        "policy_version": c.CONTEXT_POLICY_VERSION,
        "generated_at_epoch": base_epoch + 1,
        "expires_at_epoch": base_epoch + 500,
        "privacy_class": "sensitive_personal",
        "disclosed_facts": facts,
        "provenance": [],
        "omissions": [],
        "model_content_sha256": c._payload_sha256(payload),
    }
    value.update(updates)
    return value


def new_resolved_state(
    *, event: Mapping[str, Any] | None = None, received_at_epoch: int = NOW + 1
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_event = c.validate_stuck_event(event or stuck())
    resolved = task()
    state = c._new_interaction(raw_event, received_at_epoch=received_at_epoch)
    state = c._attach_resolved_task(state, resolved, now_epoch=received_at_epoch + 1)
    return state, resolved


def prepare_and_publish(
    state: dict[str, Any],
    resolved: dict[str, Any],
    *,
    revision: int | None = None,
    interaction_id: str | None = None,
    base_epoch: int | None = None,
    context_policy: Mapping[str, Any] | None = None,
    proposal_policy: Mapping[str, Any] | None = None,
    card_policy: Mapping[str, Any] | None = None,
    proposal_value: Mapping[str, Any] | None = None,
    card_updates: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rev = revision or ((state.get("current_revision") or 0) + 1)
    ident = interaction_id or state.get("interaction_id") or uid()
    base = base_epoch if base_epoch is not None else NOW + rev * 100
    manifest = context(
        interaction_id=ident,
        revision=rev,
        resolved=resolved,
        base_epoch=base,
        policy=context_policy,
    )
    state = c._record_context_prepared(
        state,
        manifest,
        resolved,
        now_epoch=base + 2,
        policy=context_policy,
    )
    semantic = c.validate_proposal(proposal_value or proposal())
    state = c._record_proposal_validated(
        state,
        semantic,
        now_epoch=base + 3,
        policy=proposal_policy,
    )
    raw_card = card(
        ident,
        rev,
        base_epoch=base,
        proposal_value=semantic,
        **dict(card_updates or {}),
    )
    state = c._record_card_published(
        state,
        raw_card,
        now_epoch=raw_card["issued_at_epoch"],
        resolved_task=resolved,
        policy=card_policy,
    )
    return state, c.validate_card(raw_card)


print("=== inventory and structural validation ===")
check("five frozen schemas", len(c.ALL_SCHEMA_VERSIONS) == 5)
for schema in (
    c.SCHEMA_STUCK,
    c.SCHEMA_CARD,
    c.SCHEMA_RESPONSE,
    c.SCHEMA_CONTEXT,
    c.SCHEMA_PROPOSAL,
):
    check(f"{schema} frozen", schema in c.ALL_SCHEMA_VERSIONS)
check("receipt remains provisional", "task_initiation_card_receipt.v1" not in c.ALL_SCHEMA_VERSIONS)
check("outcome remains absent", not hasattr(c, "validate_outcome"))

raw_card = card(uid())
check("Card validates", c.validate_card(raw_card)["revision"] == 1)
raises("invalid_schema", c.validate_card, {**raw_card, "blocker": {**raw_card["blocker"], "extra": 1}})
raises("invalid_schema", c.validate_card, {**raw_card, "tiny_start": {**raw_card["tiny_start"], "extra": 1}})
raw_proposal = proposal()
check("Proposal validates", c.validate_proposal(raw_proposal)["tiny_start"]["estimated_minutes"] == 3)
raises("invalid_schema", c.validate_proposal, {**raw_proposal, "tiny_start": {**raw_proposal["tiny_start"], "extra": 1}})
raises(
    "proposal_unsafe",
    c.validate_proposal,
    {**raw_proposal, "blocker": {"category": "too_big", "summary": "x", "shell_command": "forbidden-test-payload"}},
)
check("Card structural validator does not freeze trial cap", c.validate_card({**raw_card, "start_countdown_seconds": 601})["start_countdown_seconds"] == 601)
raises("policy_rejected", c._validate_card_policy, {**raw_card, "start_countdown_seconds": 601})
check("Proposal structural validator does not freeze trial cap", c.validate_proposal({**raw_proposal, "tiny_start": {**raw_proposal["tiny_start"], "estimated_minutes": 11}})["tiny_start"]["estimated_minutes"] == 11)
raises("policy_rejected", c._validate_proposal_policy, {**raw_proposal, "tiny_start": {**raw_proposal["tiny_start"], "estimated_minutes": 11}})

print("=== disclosure boundary ===")
resolved = task()
raw_context = context(interaction_id=uid(), revision=1, resolved=resolved, base_epoch=NOW + 100)
validated_context = c.validate_context(raw_context)
model_payload = c.api_payload_from_context(validated_context)
check("model hash matches exact payload", validated_context["model_content_sha256"] == c._payload_sha256(model_payload))
raises("content_hash_mismatch", c.validate_context, {**raw_context, "model_content_sha256": hashlib.sha256(b"wrong").hexdigest()})
raises("invalid_schema", c.validate_context, {**raw_context, "policy_version": ""})
raw_leak = {"disclosed_facts": {**raw_context["disclosed_facts"], "task": {"label": resolved["label"], "secret": "LEAK"}}}
raises("invalid_schema", c.api_payload_from_context, raw_leak)
for local_path in (
    "Read /home/user/private.md",
    "Read /secret",
    "Read /nix/store/abc-secret/file",
    "Read /workspace/project/secret",
    "Read file:///home/user/private.md",
    "Read ~/.config/private.md",
    "Read C:\\Users\\Daniil\\secret.txt",
):
    path_context = copy.deepcopy(raw_context)
    path_context["disclosed_facts"]["helper_material"] = [
        {"label": "source", "excerpt": local_path}
    ]
    raises("privacy_rejected", c.validate_context, path_context)

bounded_facts = {
    "helper_material": [
        {"label": "a", "excerpt": "one"},
        {"label": "b", "excerpt": "two"},
    ]
}
custom_policy = {"max_helper_material": 1}
over_context = context(
    interaction_id=uid(),
    revision=1,
    resolved=resolved,
    base_epoch=NOW + 100,
    facts_updates=bounded_facts,
)
check("default context policy accepts two helper items", len(c.validate_context(over_context)["disclosed_facts"]["helper_material"]) == 2)
raises("policy_rejected", c.validate_context, over_context, policy=custom_policy)

print("=== required preparation lifecycle and binding ===")
state, resolved = new_resolved_state()
interaction_id = uid()
direct_card = card(interaction_id)
raises("context_required", c._record_card_published, state, direct_card, now_epoch=direct_card["issued_at_epoch"], resolved_task=resolved)
manifest = context(interaction_id=interaction_id, revision=1, resolved=resolved, base_epoch=NOW + 100)
state_with_context = c._record_context_prepared(state, manifest, resolved, now_epoch=NOW + 102)
raises("proposal_required", c._record_card_published, state_with_context, direct_card, now_epoch=direct_card["issued_at_epoch"], resolved_task=resolved)
state_with_proposal = c._record_proposal_validated(state_with_context, proposal(), now_epoch=NOW + 103)
published = c._record_card_published(state_with_proposal, direct_card, now_epoch=direct_card["issued_at_epoch"], resolved_task=resolved)
check("full preparation lifecycle publishes Card", published["phase"] == "awaiting_response")
check("revision binds Context", published["revisions"][0]["context_id"] == manifest["context_id"])
check("revision binds Proposal", published["revisions"][0]["proposal"] == c.validate_proposal(proposal()))

state, resolved = new_resolved_state()
wrong_context = context(interaction_id=uid(), revision=1, resolved=resolved, base_epoch=NOW + 100, facts_updates={"task": {"label": "Different task"}})
raises("task_mismatch", c._record_context_prepared, state, wrong_context, resolved, now_epoch=NOW + 102)
state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
check("Card label is bound to resolved task", current["task_label"] == resolved["label"])

state, resolved = new_resolved_state()
ident = uid()
manifest = context(interaction_id=ident, revision=1, resolved=resolved, base_epoch=NOW + 100)
state = c._record_context_prepared(state, manifest, resolved, now_epoch=NOW + 102)
semantic = proposal()
state = c._record_proposal_validated(state, semantic, now_epoch=NOW + 103)
wrong_label_card = card(ident, proposal_value=semantic, task_label="Different task")
raises("task_mismatch", c._record_card_published, state, wrong_label_card, now_epoch=wrong_label_card["issued_at_epoch"], resolved_task=resolved)
wrong_semantic_card = card(ident, proposal_value=semantic, blocker={"category": "other", "summary": "Different"})
raises("proposal_mismatch", c._record_card_published, state, wrong_semantic_card, now_epoch=wrong_semantic_card["issued_at_epoch"], resolved_task=resolved)

print("=== phase and deadline safety ===")
state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
raises("invalid_transition", c._attach_resolved_task, state, resolved, now_epoch=NOW + 200)
raises("invalid_transition", c._record_context_prepared, state, context(interaction_id=current["interaction_id"], revision=2, resolved=resolved, base_epoch=NOW + 200), resolved, now_epoch=NOW + 202)
start = response(current, "start")
observing = c._apply_response(state, start, received_at_epoch=start["occurred_at_epoch"] + 1, resolved_task=resolved)
raises("invalid_transition", c._attach_resolved_task, observing, resolved, now_epoch=NOW + 300)
raises("invalid_transition", c._record_context_prepared, observing, context(interaction_id=current["interaction_id"], revision=2, resolved=resolved, base_epoch=NOW + 300), resolved, now_epoch=NOW + 302)

near_expiry_event = stuck(occurred_at_epoch=NOW)
precard, precard_task = new_resolved_state(event=near_expiry_event)
expired_manifest = context(interaction_id=uid(), revision=1, resolved=precard_task, base_epoch=NOW + 7100)
raises("expired", c._record_context_prepared, precard, expired_manifest, precard_task, now_epoch=NOW + 7200)

state, resolved = new_resolved_state()
ident = uid()
manifest = context(interaction_id=ident, revision=1, resolved=resolved, base_epoch=NOW + 100)
state = c._record_context_prepared(state, manifest, resolved, now_epoch=NOW + 102)
state = c._record_proposal_validated(state, proposal(), now_epoch=NOW + 103)
already_expired = card(ident, issued_at_epoch=NOW + 104, expires_at_epoch=NOW + 105)
raises("expired", c._record_card_published, state, already_expired, now_epoch=NOW + 105, resolved_task=resolved)
predated = card(ident, issued_at_epoch=NOW + 102, expires_at_epoch=NOW + 500)
raises("invalid_timestamp", c._record_card_published, state, predated, now_epoch=NOW + 104, resolved_task=resolved)

print("=== task-fingerprint safety gates ===")
changed = task(hashlib.sha256(b"changed").hexdigest())
state, resolved = new_resolved_state()
changed_at_context = c._record_context_prepared(state, context(interaction_id=uid(), revision=1, resolved=resolved, base_epoch=NOW + 100), changed, now_epoch=NOW + 102)
check("task change before Context supersedes", changed_at_context["terminal_status"] == "superseded")
state, resolved = new_resolved_state()
ident = uid()
manifest = context(interaction_id=ident, revision=1, resolved=resolved, base_epoch=NOW + 100)
state = c._record_context_prepared(state, manifest, resolved, now_epoch=NOW + 102)
state = c._record_proposal_validated(state, proposal(), now_epoch=NOW + 103)
changed_at_card = c._record_card_published(state, card(ident), now_epoch=NOW + 104, resolved_task=changed)
check("task change before Card supersedes", changed_at_card["terminal_status"] == "superseded")
state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
changed_at_response = c._apply_response(state, response(current), received_at_epoch=current["issued_at_epoch"] + 11, resolved_task=changed)
check("task change before Response supersedes", changed_at_response["terminal_status"] == "superseded")
check("superseded interaction accepts no response", not changed_at_response["accepted_responses"])

print("=== replay and first-response semantics ===")
event = c.validate_stuck_event(stuck())
initial = c._new_interaction(event, received_at_epoch=NOW + 1)
check("exact Stuck replay is idempotent", c._ingest_stuck(initial, event, received_at_epoch=NOW + 2) == initial)
raises("idempotency_conflict", c._ingest_stuck, initial, {**event, "task_description": "Changed"}, received_at_epoch=NOW + 2)

state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
start = c.validate_response(response(current, "start"))
accepted = c._apply_response(state, start, received_at_epoch=start["occurred_at_epoch"] + 1, resolved_task=resolved)
version = accepted["state_version"]
check("exact Response replay returns prior state", c._apply_response(accepted, start, received_at_epoch=start["occurred_at_epoch"] + 2, resolved_task=resolved) == accepted)
check("Response replay does not bump state", accepted["state_version"] == version)
raises("idempotency_conflict", c._apply_response, accepted, {**start, "action": "defer"}, received_at_epoch=start["occurred_at_epoch"] + 2, resolved_task=resolved)
raises("card_already_responded", c._apply_response, accepted, response(current, "defer"), received_at_epoch=start["occurred_at_epoch"] + 2, resolved_task=resolved)

state, resolved = new_resolved_state()
state, first = prepare_and_publish(state, resolved)
shrink = response(first, "shrink")
state = c._apply_response(state, shrink, received_at_epoch=shrink["occurred_at_epoch"] + 1, resolved_task=resolved)
first_time = state["first_response_at_epoch"]
state, second = prepare_and_publish(state, resolved)
second_start = response(second, "start")
state = c._apply_response(state, second_start, received_at_epoch=second_start["occurred_at_epoch"] + 1, resolved_task=resolved)
check("aggregate first response remains earliest", state["first_response_at_epoch"] == first_time)
check("Start time is tracked separately", state["start_at_epoch"] == second_start["occurred_at_epoch"])

print("=== Receipt and delivery evidence precedence ===")
state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
posted = c.validate_card_receipt(receipt(current))
with_receipt = c._record_card_receipt(state, posted, received_at_epoch=posted["posted_at_epoch"] + 1)
version = with_receipt["state_version"]
check("exact Receipt replay returns prior state", c._record_card_receipt(with_receipt, posted, received_at_epoch=posted["posted_at_epoch"] + 2) == with_receipt)
check("Receipt replay does not bump state", with_receipt["state_version"] == version)
raises("idempotency_conflict", c._record_card_receipt, with_receipt, {**posted, "posted_at_epoch": posted["posted_at_epoch"] + 1}, received_at_epoch=posted["posted_at_epoch"] + 2)
raises("delivery_evidence_conflict", c._record_delivery_result, with_receipt, card_id=current["card_id"], result="confirmed_not_posted", occurred_at_epoch=posted["posted_at_epoch"] + 3)

state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
state = c._record_delivery_result(state, card_id=current["card_id"], result="confirmed_not_posted", occurred_at_epoch=current["issued_at_epoch"] + 1)
state = c._record_card_receipt(state, receipt(current), received_at_epoch=current["issued_at_epoch"] + 3)
check("valid Receipt overrides earlier non-posted evidence", state["revisions"][0]["delivery_evidence"] == "posted")
check("contradictory delivery evidence is retained", "delivery_evidence_conflict" in state["revisions"][0]["evidence_issues"])
expired = c._advance_time(state, now_epoch=current["expires_at_epoch"])
check("posted Card is not classified as not posted", expired["resolution_reason"] == "card_expired_without_response")

state, resolved = new_resolved_state()
state, first = prepare_and_publish(state, resolved)
shrink = response(first, "shrink")
state = c._apply_response(state, shrink, received_at_epoch=shrink["occurred_at_epoch"] + 1, resolved_task=resolved)
state, second = prepare_and_publish(state, resolved)
state = c._record_delivery_result(state, card_id=first["card_id"], result="confirmed_not_posted", occurred_at_epoch=second["issued_at_epoch"] + 1)
expired = c._advance_time(state, now_epoch=second["expires_at_epoch"])
check("old revision evidence cannot classify current Card", expired["resolution_reason"] == "card_expired_without_response")
check("current revision delivery remains none", expired["revisions"][1]["delivery_evidence"] == "none")

print("=== timing and terminal behavior ===")
late_event = c.validate_stuck_event(stuck(occurred_at_epoch=NOW))
state = c._new_interaction(late_event, received_at_epoch=NOW + 1)
resolved = task()
state = c._attach_resolved_task(state, resolved, now_epoch=NOW + 2)
state, current = prepare_and_publish(state, resolved, base_epoch=NOW + 7100)
start = response(current, "start", occurred_at_epoch=NOW + 7150)
state = c._apply_response(state, start, received_at_epoch=NOW + 7151, resolved_task=resolved)
state = c._advance_time(state, now_epoch=NOW + 7201)
check("request expiry does not interrupt observing Start", state["terminal_status"] is None)
state = c._advance_time(state, now_epoch=state["observation_due_at_epoch"])
check("observation completes", state["resolution_reason"] == "start_observation_elapsed")
raises("terminal_immutable", c._attach_resolved_task, state, resolved, now_epoch=NOW + 8000)

state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
early_claim = response(current, "start", occurred_at_epoch=current["issued_at_epoch"] + 1)
raises("expired", c._apply_response, state, early_claim, received_at_epoch=current["expires_at_epoch"], resolved_task=resolved)

print("=== no execution authority ===")
state, resolved = new_resolved_state()
state, current = prepare_and_publish(state, resolved)
start = response(current, "start")
state = c._apply_response(state, start, received_at_epoch=start["occurred_at_epoch"] + 1, resolved_task=resolved)
serialized = json.dumps(state, default=list)
for forbidden in (
    '"shell_command"',
    '"action_file"',
    '"uri_to_open"',
    '"writes_live_action_queue"',
    '"edits_obsidian_now"',
):
    check(f"state excludes {forbidden}", forbidden not in serialized)
check("Start creates only observation deadline", state["observation_due_at_epoch"] == start["occurred_at_epoch"] + 1 + 600)

print()
print(f"=== {PASSED} passed, {FAILED} failed ===")
if FAILED:
    raise SystemExit(1)
print("ALL PASS")
