# intervention-outcomes

`intervention-outcomes` materializes deterministic outcome summaries for user-visible interventions.

It reads append-only evidence from:

```text
AI/events/interventions/YYYY-MM-DD.jsonl
AI/events/actions/YYYY-MM-DD.jsonl
AI/events/recovery/YYYY-MM-DD.jsonl
```

It writes derived review state only:

```text
AI/state/interventions/current.json
AI/state/interventions/stats.json
AI/state/interventions/status.md
```

Authority boundary:

```text
events are evidence
ai_system.intervention_outcomes summarizes evidence
intervention_outcomes_reporter.py writes derived review state/status only
```

It must not propose, execute, launch apps, call an LLM, mutate recovery state, or change policy.

## Manual run

```zsh
ai-intervention-outcomes --days 7 --write
```

## Smoke test

```zsh
PYTHONPATH=modules/programs/ai/python nix run nixpkgs#python3 -- modules/programs/ai/tests/intervention_outcomes_reporter_smoke.py
```

