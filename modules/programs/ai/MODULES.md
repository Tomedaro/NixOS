# Modules

This is the high-level module map. Detailed evidence belongs in `docs/MODULE_REVIEW_REGISTER.md`.

| Module | Purpose | Side-effect level | Notes |
| --- | --- | --- | --- |
| `action-bridge` | Processes live action queue and selected actions. | High | Legacy/direct TaskNotes promotion is disabled; reviewable drafts remain separate. |
| `phone-bridge` | Phone-facing message/status bridge. | Medium | Writes phone outbox/state. |
| `dialog-bridge` | Desktop/dialog interaction bridge. | Medium | Queues canonical `answer_question` action files into `AI/inbox/actions`; `action-bridge` owns answer/dismiss lifecycle processing. Desktop UI must not emit `dismiss_question` until a real dismiss signal exists. |
| `session-manager` | Session lifecycle and state. | Medium | Supports recovery/session flows. |
| `coach-daemon` | Coaching/recovery loop. | Medium | Should stay friendly and bounded. |
| `recovery-manager` | Recovery proposal/status handling. | Medium | Should propose rather than silently commit. |
| `recovery-trigger` | Trigger recovery flow from signals/state. | Medium | Must avoid nag loops and respect attention policy. |
| `intervention-outcomes` | Outcome recording/reporting. | Low/Medium | Useful basis for learning loop, but not full product eval yet. |
| `anki-bridge` | Anki/recovery bridge. | Observe + draft/propose | Direct TaskNotes mode is removed/hard-disabled; `propose` is the supported task output mode. |
| `vault-bridge` | AI vault integration/config. | Medium | Protocol/state bridge. |
| `llm-planner` | Planner/proposal generation. | Low | Proposal-oriented; should include richer metadata over time. |
| `obsidian_*` Python modules | Obsidian protocol, context, proposals, approval, task drafts. | Low/Medium | Strong review/draft boundary. |
| `python/ai_system/*` | Shared protocol/context/utilities. | Varies | Source of canonical schemas/utilities. |
| `dev/*` | Diagnostics, smoke, rebuild helpers. | Varies | Live checks default read-only unless flags request mutation. |
| `tests/*` | Smoke tests. | None | Good coverage of mechanics; product evals still needed. |
| `default.nix`, module `default.nix` files | Nix configuration and service wiring. | Configuration authority | Must document safe defaults and dangerous options. |

## Module review rule

For every meaningful module, the full register should list:

- purpose;
- status;
- inputs;
- outputs;
- side effects;
- authority level;
- queue paths;
- state paths;
- tests;
- docs that mention it;
- issues;
- refactor/doc actions.

## Minimum module contract pressure test

Before implementing first-class read-only TaskNotes context, document a Markdown-only module contract for `tasknotes.read_context`. This is a module contract registry pressure test, not a replacement for `ACTION_CAPABILITY_POLICY`.

Minimum contract:

- type: context provider;
- reads: bounded TaskNotes source paths;
- writes: bounded AI context output/artifacts only;
- `may_mutate_tasknotes`: false;
- `required_action_capabilities`: none;
- output includes provenance, freshness, and limits;
- tests prove no TaskNotes writes, bounded/provenanced output, and safe-off/disabled behavior.

A module contract should reference `ACTION_CAPABILITY_POLICY` only when that module dispatches or requires live `action-bridge` actions. Future deterministic TaskNotes apply/promote remains separate planned work.
