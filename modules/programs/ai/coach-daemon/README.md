# coach-daemon

Immediate rule-based desktop productivity feedback.

## Why this exists

The LLM planner is too slow/expensive to run every minute. The coach gives quick local feedback based on ActivityWatch.

## Boot safety

ActivityWatch persists old events. On boot, the latest event may be stale.
The coach ignores ActivityWatch events older than `EVENT_FRESHNESS_SECONDS` and suppresses notifications during `STARTUP_GRACE_SECONDS`.

## Outputs

- `AI/state/desktop/now.md`
- `AI/state/desktop/now.json`
- `AI/state/desktop/coach-state.json`
- `AI/logs/desktop/YYYY-MM-DD.md`
- `AI/events/desktop/YYYY-MM-DD.jsonl`
