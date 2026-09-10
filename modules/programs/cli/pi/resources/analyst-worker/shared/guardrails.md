# Shared Analyst/Worker Guardrails

These rules apply to every Analyst and Worker stage.

## Scope control

- One stage equals one logical slice.
- Prefer one subsystem and a reviewable diff.
- Stop when the stage becomes mixed, sprawling, or no longer matches the Analyst plan.

## Reviewer workload protection

- Respect the configured file-count and net-LOC budgets.
- Do not combine feature work, refactor, dependency changes, and cleanup in one stage unless explicitly approved.
- If the warning budget is exceeded, the Analyst must decide whether to split.
- If the stop budget is exceeded, pause the run.

## Approval boundaries

- No destructive operations without human permission.
- No policy, secret, credential, dependency, publishing, migration, or memory-behavior changes without explicit review.
- No irreversible apply step without explicit acknowledgment.

## Evidence before done

- No `DONE` without validation artifacts and Analyst review.
- No “tests passed” claim without test output or saved evidence.
- No “verified” claim without naming what was verified.

## Simplification before review

- When files changed, Worker runs a changed-files-only simplification pass before Analyst review.
- Prefer `/simplify` or `pi-simplify` when available.
- Fall back to the checklist in `PI_AW_SIMPLIFY_CONVENTIONS` when slash-command execution is unavailable.
- Preserve behavior; do not expand into feature work, unrelated cleanup, or broad refactoring.
- If simplification would change semantics or requires a wider refactor, stop and report the risk.

## Artifact visibility

- Review-critical artifacts need a path, a short summary, and a reviewable excerpt or checksum in the Worker report.
- Analyst must reject final claims that depend on unseen artifact contents.
- Save large raw outputs under the artifact directory, but surface compact evidence in the report.

## Tool efficiency

- Prefer `ctx_*` tools for repository reads, search, listing, and validation shell commands.
- Use raw `read`, `grep`, `ls`, or `bash` only when exact raw output or tool availability requires it.
- Report non-`ctx_*` exceptions when repository context work is tool-heavy.

## Non-overclaim rule

- Distinguish evidence, inference, and speculation.
- Current files and command output override memory.
- If a tool or extension is missing, report that fact and stop.

## Memory hygiene

- Never store secrets or temporary scratch state in durable memory.
- Worker does not write durable memory.
- Analyst proposes memory candidates only after acceptance.
- Parent session decides final memory writes.

## Artifact hygiene

- Technical artifacts default to English.
- Keep raw logs transient unless needed for review.
- Keep durable artifacts small, named, and source-relevant.

## Safety precedence

Deterministic checks and explicit user decisions beat agent optimism. When judgment and policy disagree, pause and escalate.
