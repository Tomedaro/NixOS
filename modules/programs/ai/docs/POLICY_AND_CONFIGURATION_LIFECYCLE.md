# Policy and configuration lifecycle
## Problem

The docs say top-level Nix options should be the high-level control surface, while submodules should not invent canonical roots, queue paths, retention settings, nudge policy defaults, or adaptive behavior defaults. Current implementation has useful but distributed defaults.

## Proposed precedence model

```text
Nix defaults
-> user Nix config
-> vault policy files
-> current session policy
-> temporary explicit user instruction
-> reviewed adaptive policy experiment
-> inferred proposal only
```

Lower layers may narrow or temporarily tune behavior, but should not silently override higher-confidence explicit policy.

## Policy classes

### Static configuration

Examples:

- vault root;
- queue roots;
- enabled services;
- time zone;
- default modes;
- retention windows.

### Session policy

Examples:

- current task;
- mode;
- allowed/distracting apps/domains;
- proof expectation;
- intervention level;
- cooldown.

### User preference

Examples:

- quiet hours;
- preferred channels;
- preferred tone;
- low-energy behavior;
- never interrupt contexts.

### Adaptive policy proposal

Examples:

- reduce Anki nudges after 21:00;
- use Obsidian instead of phone for planning questions;
- ask fewer questions after repeated dismissals.

### Adaptive policy experiment

A time-bounded policy with evidence, hypothesis, metrics, and rollback.

## Lifecycle states

```text
proposed -> accepted -> active -> expired -> reviewed -> kept|revised|rejected|superseded
```

## Migration rules

1. Schema changes should be additive first.
2. Required field changes need compatibility readers and migration notes.
3. Old policy artifacts should remain interpretable.
4. Future contributors should document whether a default is static, user preference, session-level, or adaptive.

## Implementation sequence

1. Document precedence and classes.
2. Inventory defaults across Nix modules and scripts.
3. Add `policy_source` and `policy_scope` to policy outputs.
4. Add evals for precedence conflicts.
5. Only later consolidate defaults.
