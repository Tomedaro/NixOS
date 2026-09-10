# Analyst/Worker Stop Matrix

## Worker must stop and return control

| Trigger | Required handoff |
|---|---|
| Requirements are ambiguous | Ask Analyst for clarification |
| Needed files/actions exceed plan scope | Report scope expansion and proposed split |
| Diff approaches warning budget | Report budget risk |
| Diff exceeds stop budget | Stop; Analyst must split, require SDD, or ask human |
| Required validation fails | Report failure and smallest known next step |
| Fixing validation would expand scope | Stop; do not improvise |
| Required tool/skill/permission unavailable | Report `MISSING_TOOL` or `MISSING_PERMISSION` |
| Review-critical artifact is too large to summarize or excerpt safely | Stop and ask Analyst how to reduce scope |
| Durable memory write seems necessary | Write a memory candidate instead and return control |
| Secret/credential access appears necessary | Stop and ask human through Analyst |
| Destructive command appears necessary | Stop and ask human through Analyst |
| Likely SDD trigger discovered | Stop and report `POSSIBLE_SDD_REQUIRED` |
| Simplification would change semantics | Stop and report the unsafe simplification |
| Simplification reveals broader refactor need | Stop and propose a separate stage or SDD |

## Analyst must ask the human

| Trigger | Required question |
|---|---|
| Product behavior remains underspecified | Ask for business/behavior decision |
| SDD is required but scope is unclear | Ask for SDD scope and non-goals |
| Destructive operation, migration, publish, or credential use | Ask explicit approval |
| Baseline tests fail unexpectedly | Ask whether to isolate baseline or proceed with caveat |
| Reviewer budget cannot be protected without changing delivery strategy | Ask split/chained strategy question |
| Memory/policy/security configuration would change | Ask explicit approval |
| Final artifact is referenced only by path | Ask Worker for summary/excerpt before DONE |
| Repository work avoided `ctx_*` tools without reason | Ask Worker for explanation or rerun efficiently |

## Analyst must require SDD or explicit override

| Trigger | Default action |
|---|---|
| Public API change | Require SDD |
| Data model or persistence change | Require SDD |
| Auth, permission, security, or policy change | Require SDD |
| Dependency addition/removal | Require SDD |
| Multi-subsystem behavior change | Require SDD |
| Product/architecture ambiguity | Require SDD |
| Diff exceeds warning budget before implementation | Require SDD or split plan |

## Analyst should escalate to advisor/reviewer

| Trigger | Default action |
|---|---|
| Second Worker failure on same slice | Ask advisor or fresh reviewer |
| Conflicting tool outputs or evidence | Ask advisor before choosing branch |
| High-risk final acceptance | Ask advisor/reviewer before DONE |
| Considering a major approach change after failed validation | Ask advisor before pivoting |

## Abort conditions

| Trigger | Action |
|---|---|
| Human denies required approval and no safe alternative exists | Abort or re-scope |
| Required credentials/secrets are unavailable | Abort or ask for alternate path |
| Tooling/environment is unreliable enough that evidence cannot be trusted | Abort or isolate environment issue |
| Scope has expanded beyond the original task and user does not approve SDD/split | Abort or pause |
