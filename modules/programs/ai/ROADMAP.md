# Roadmap

This file is planned work only. Do not use it as current-state documentation.

## Priority 1 - Stabilize authority and direct mutation boundaries

1. Split/lower broad `action-bridge` authority.
2. Mark, hard-gate, or disable `promote_task_proposal` as legacy/direct.
3. Deprecate `anki-bridge taskNoteMode = "direct"`.
4. Add tests proving default configuration cannot mutate real TaskNotes through legacy/direct paths.

## Priority 2 - Canonicalize action and TaskNotes flows

1. Migrate `dialog-bridge` answer/dismiss handling to canonical `AI/inbox/actions/*.json`.
2. Add first-class read-only TaskNotes context.
3. Define deterministic TaskNotes apply/promote schema.
4. Implement apply/promote gate with idempotency, conflict handling, and events.

## Priority 3 - Protocol and audit hardening

1. Add schema lifecycle docs and versioning.
2. Upgrade JSONL evidence logs or document/replace them with authoritative audit semantics.
3. Add producer identity/provenance where needed.
4. Add service hardening and safe default review.

## Priority 4 - Product intelligence

1. Define evidence ledger and personal model hypothesis schema.
2. Add correction/supersession semantics.
3. Define goal hierarchy: values/life areas, goals, projects/habits, commitments/tasks, sessions, interventions, outcomes.
4. Expand planner metadata: why now, evidence refs, confidence, user burden, capacity assumption, linked goal, expiry, alternatives.
5. Define attention/receptivity policy: quiet hours, low-energy mode, repeated-ignore backoff, deep-work suppression, channel switching.

## Priority 5 - Product evaluation

1. Add scenario evals for stale context, wrong inference, repeated ignored nudges, low energy, active deep work, conflicting goals, daily review quality, and recovery quality.
2. Add voice/relationship quality checks: friendly, non-punitive, non-shaming, agency-preserving.
3. Track outcome quality beyond mechanical smoke tests.

## Priority 6 - UI expansion only after protocols are boring

Desktop popup UI, richer phone controls, and more autonomous behavior should wait until protocols, authority, and review gates are stable and well tested.
