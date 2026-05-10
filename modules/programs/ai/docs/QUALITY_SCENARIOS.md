# Quality scenarios
These scenarios convert product aspirations into testable quality attributes.

## Usability and autonomy

### QS-USER-001: Explain interruption

When the system interrupts the user, the rendered interaction must include or be able to show `why_now`, evidence refs, and a way to correct it.

### QS-USER-002: Correct wrong inference

When the user marks an inference wrong, the system records a correction and future proposals stop relying on that inference unless superseded by stronger explicit evidence.

### QS-USER-003: Preserve choice

When a task proposal could become a durable commitment, the system presents it as a draft/review artifact, not as completed work.

## Attention and recovery

### QS-ATTN-001: Repeated ignore backoff

If similar nudges are ignored twice within a configured window, the next decision must reduce pressure, change strategy, ask a clarifying question, or stay silent.

### QS-ATTN-002: Snooze respect

If the user snoozes a nudge, the same pressure must not be reissued before the snooze expires.

### QS-ATTN-003: Stale context humility

If key context is stale, user-facing text must not make confident claims about the current situation.

### QS-ATTN-004: Deep work suppression

If the current activity aligns with the active session policy, the assistant should not interrupt unless the user requested it or a higher-priority commitment requires review.

### QS-ATTN-005: Silence as success

Daily/weekly summaries should be able to count cases where staying quiet was the intended intervention.

## Learning quality

### QS-LEARN-001: Evidence-backed hypotheses

Every inferred pattern must include evidence refs, confidence, scope, and expiry.

### QS-LEARN-002: Reversible adaptation

Every adaptive policy must have a rollback/supersession path.

### QS-LEARN-003: No overgeneralization

A pattern learned from Anki night nudges must not automatically apply to all productivity nudges.

### QS-LEARN-004: User confirmation wins

Approved facts and explicit corrections override lower-confidence inferred patterns.

## Maintainability

### QS-MAINT-001: Add provider safely

A future contributor can add a context provider by updating one provider module, one module register entry, one protocol entry if files are written, and one smoke/product eval.

### QS-MAINT-002: Schema evolution

Optional vNext fields can be added without breaking v1 consumers. Required changes need migration notes and tests.

### QS-MAINT-003: Research traceability

Every research claim in docs maps to an invariant, schema field, control, or eval.

## Documentation quality

### QS-DOC-001: Current/planned separation

Current implemented behavior and roadmap items must be in separate docs.

### QS-DOC-002: Maturity precision

Features must not be called implemented if only scaffolded. Use maturity levels: concept, scaffolded, mechanically implemented, tested, user-operational, adaptive/learning, deprecated.
