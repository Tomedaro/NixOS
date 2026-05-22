# Roadmap

This file is planned work only. Do not use it as current-state documentation.

## Priority 1 - Stabilize authority and direct mutation boundaries

1. Preserve regression coverage for `recovery.target.start` default-off behavior and explicit opt-in success.
2. Clarify and test `action-bridge` authority defaults before lowering broad numeric authority.
3. Follow the `SAFETY_MODEL.md` named capability default-off migration checklist before flipping any additional named capability default.
4. Treat `recovery.target.start` as the first completed default-off example; do not select or start another default-off candidate without a separate Research and Design plan.
5. Keep direct TaskNotes mutation disabled until deterministic apply/promote exists.
6. Keep Anki task output proposal/off only until deterministic TaskNotes apply/promote exists.
7. Preserve regression coverage proving default/reviewable paths cannot mutate real TaskNotes.

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

## Extension-model follow-up

Before adding many new goal-achievement instruments, add a lightweight capability/instrument registry:

1. define a module manifest shape;
2. list context providers, planners, review surfaces, action adapters, memory modules, and evaluators;
3. require each side-effecting instrument to declare reads, writes, authority, schemas, tests, and disable switch;
4. add a registry consistency check;
5. use one small new instrument as the reference implementation.

This keeps future functionality easy to add without creating a giant unbounded agent.
