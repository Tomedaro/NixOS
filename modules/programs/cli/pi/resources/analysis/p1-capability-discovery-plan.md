# P1 — Capability Discovery & Profile Explainability: Design Plan

**Scope:** Items P1.4 (explain-profile), P1.5 (resource-inventory), P1.6 (extension manifest generation), P1.7 (prompt/skill linting) from `agent-capability-roadmap.md`, plus `docs/LOOKUP.json` routing updates.

**Status:** IC.1 (`pi-admin resource-inventory`) implemented; IC.2-IC.5 remain planned.

---

## Table of Contents

1. [Architectural Vision](#1-architectural-vision)
2. [Data Model — The Resource Registry](#2-data-model--the-resource-registry)
3. [Sub-Project A: Foundation — Resource Inventory (`pi-admin resource-inventory`)](#3-sub-project-a-foundation--resource-inventory)
4. [Sub-Project B: Quality Gate — Prompt/Skill Linting (`pi-admin lint-resources`)](#4-sub-project-b-quality-gate--promptskill-linting)
5. [Sub-Project C: Artifact — Generated Extension Manifest (`pi-admin generate-extension-manifest`)](#5-sub-project-c-artifact--generated-extension-manifest)
6. [Sub-Project D: UX — Profile Explainability (`pi-admin explain-profile`)](#6-sub-project-d-ux--profile-explainability)
7. [Integration & Wiring](#7-integration--wiring)
8. [Extensibility to P2+](#8-extensibility-to-p2)
9. [Dependency Order & Risk](#9-dependency-order--risk)
10. [Appendix: Reference — Current Resource Layout](#10-appendix-reference--current-resource-layout)

---

## 1. Architectural Vision

### 1.1 Core Insight

The Pi module already has a clear **source-of-truth model**:
- `settings/global.json` = canonical package pins
- `resources/<profile>/prompts/` = canonical prompt files
- `resources/<profile>/skills/<name>/SKILL.md` = canonical skill files
- `resources/<profile>/AGENTS.md` = canonical profile instructions

But there is **no unified query layer** over these sources. Discovery today means `ls` and `grep`. P1 introduces a **tool suite** that makes the module introspectable:

```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐
│  DISCOVER    │    │   LINT       │    │   RENDER      │    │   SERVE/EXPLAIN  |
│ (inventory)  │    │ (validation) │    │ (manifest)    │    │ (explain-profile)|
└──────┬───────┘    └──────┬───────┘    └───────┬───────┘    └────────┬─────────┘
       │                   │                     │                     │
       ▼                   ▼                     ▼                     ▼
   JSON registry      Pass/fail items       Markdown docs        Interactive CLI
   (machine)          (actionable)          (human)              (human+JSON)
```

**Important**: This is a **tool suite**, not a pipelined executor. Each command is standalone and re-discovers from source. Commands share the same JSON schema as their interchange format but are designed to be run independently. A true pipeline (one command's JSON output piped directly into another) can be added in P2 via `--stdin` flags but is not part of P1.

### 1.2 Principles

1. **Inventory before expansion** — discover what exists before adding more. This means resource-inventory is **the** foundation of all P1 work.
2. **Lint before consume** — don't render a manifest or explain a profile using data that fails validation. Linting gates the pipeline.
3. **Generate where possible** — `docs/EXTENSIONS.md` should be generated from `settings/global.json`, not written by hand.
4. **JSON plumbing, Markdown UX** — every discovery/lint command emits JSON for machine consumption; human-facing output is a separate concern.
5. **P2-ready output format** — the resource inventory JSON schema must accommodate the agent capability matrix (rows = resource, columns = profile/trigger/tools/risk) without a breaking change.
6. **No new runtime state** — all output is computed on demand from source files and runtime `~/.pi/agent/npm` inspection. Nothing is cached long-term (a short-lived temp cache per command invocation is acceptable for performance).

### 1.3 Where code lives

All new commands follow the existing pattern:
- **Script definition**: `scripts.nix` (or extracted into `scripts/resource.nix` if P1 pushes past ~300 lines)
- **Nixpkgs tooling**: `jq`, `python3` for JSON processing; `find`, `grep`, `sort` for filesystem discovery
- **Binary dependencies**: Coreutils, findutils, gnugrep, gnused, python3, jq — all already available
- **CLI entrypoints**: `pi-admin resource-inventory`, `pi-admin lint-resources`, `pi-admin generate-extension-manifest`, `pi-admin explain-profile`

**Design constraint**: Do NOT introduce a new compiled language (Go, Rust) or a heavyweight runtime (Node) for these commands. They are text-processing pipelines and must stay as shell + jq + python3. All existing `pi-admin` subcommands use this pattern.

### 1.4 Module Root Resolution

All relative paths in this plan (e.g. `policies/nixos.jsonc`) resolve against the Pi module source root. Commands find it through `${paths.piSourceDir}` — the same variable already used by `pi-admin status` and the `source_hash()` function in `wrappers.nix`:

```bash
PI_SOURCE_DIR="${paths.piSourceDir}"   # e.g. /home/daniil/NixOS/modules/programs/cli/pi
```

This variable is available in all wrapper scripts and is exported through `wrapperPrelude`. New scripts reference it directly.

---

## 2. Data Model — The Resource Registry

### 2.1 Core Types

Every discoverable resource in the Pi module belongs to one of five categories:

```jsonc
// Resource Registry — the unified output schema for pi-admin resource-inventory --json
{
  "version": 1,
  "generated_at": "2026-06-20T13:00:00Z",
  "schema_lint_level": "inline",    // Tracks which lint checks have been run
                                  // Values: "none" | "inline" | "deep"
  "profiles": [                    // All known profiles, discovered from policies/
    "nixos", "safe", "study", "study-tutor", "trusted", "work", "research"
  ],
  "profile_aliases": {             // Profile aliases (cautious/safe/readonly = safe)
    "cautious": "safe",
    "readonly": "safe",
    "safe": "safe"
  },
  "profile_inheritance": {         // Profiles that inherit resources from another
    "study-tutor": "study"
  },
  "resources": [
    {
      "kind": "extension",       // One of: extension | prompt | skill | agents | mcp_server
      "id": "pi-lens",           // Stable identifier
      "profiles": ["nixos", "study", "work", "study-tutor", "safe", "trusted", "research"],
                                 // All known profiles (global extension)
      "path": "settings/global.json",
      "risk_class": "code-intelligence",
      "metadata": {
        "version": "0.x.y",      // From package pins (runtime version in separate field)
        "description": "LSP/AST diagnostics and semantic search/replace",
        "source": "npm:@gotgenes/pi-lens@0.5.2",
        "overlay": null          // null for global, "study-tutor" for overlay packages
      },
      "runtime": {               // Absent if runtime inspection unavailable
        "installed_version": "0.5.2",
        "status": "match"
      },
      "lint_level": "inline",    // Which level of lint was applied
      "warnings": []             // Lint findings (empty if none or lint not run)
    },
    {
      "kind": "extension",
      "id": "pi-learning-tutor",
      "profiles": ["study-tutor"],
      "path": "settings/study-tutor.overlay.json",
      "metadata": {
        "source": "npm:@majorgilles/pi-learning-tutor@0.x.y",
        "overlay": "study-tutor"
      },
      "warnings": []
    },
    {
      "kind": "prompt",
      "id": "pi-change.md",
      "profiles": ["nixos"],
      "path": "resources/nixos/prompts/pi-change.md",
      "metadata": {
        "description": "Plan safe Pi setup changes through the wiki first",
        "argument_hint": "<change description>"
      },
      "lint_level": "none",
      "warnings": []
    }
  ]
}
```

### 2.2 Profile Enumeration Strategy

Profiles are enumerated from the `policies/` directory. Every profile has a policy file (`<profile>.jsonc`), making this the canonical source. The mapping:

| Source | Profiles | Canonical? |
|--------|----------|-----------|
| `policies/*.jsonc` (6 files) | nixos, safe, study, trusted, work, research | ✅ Yes — every profile has a policy |
| `mcp/*.json` (5 files) | global, nixos, research, study, work | Partial — `global` is not a user profile |
| `resources/*/` (5 dirs) | global, nixos, study, study-tutor, work | Partial — `global` is not a profile, `study-tutor` has no policy |
| Smart launcher logic | nixos, study, study-tutor, work, research, trusted, raw | Complete but implicit |

**Rule**: Use `policies/*.jsonc` as the canonical profile source. Strip `.jsonc` suffix to get profile names. This yields 6 profiles: `nixos`, `safe`, `study`, `trusted`, `work`, `research`.

**Alias resolution**: `cautious`, `readonly`, and `safe` all map to the `safe` policy. The registry documents this in `profile_aliases`. Commands that filter by profile should resolve aliases before matching.

**Inherited profiles**: `study-tutor` has no policy file but inherits the `study` profile's resources. The registry documents this in `profile_inheritance`. Resources from the study profile tree automatically have `profiles: ["study", "study-tutor"]`.

### 2.3 Extension-to-Profile Mapping (Overlay Merge Model)

Extensions come from two sources that must be merged differently:

**Source: `settings/global.json` → packages[]**
```json
"packages": ["npm:@gotgenes/pi-lens@0.5.2", "npm:gentle-engram@0.1.7", ...]
```
These apply to **all** profiles. The `profiles` array for each = every known profile from `policies/`.

**Source: `settings/<profile>.overlay.json` → extraPackages[]**
```json
"extraPackages": ["npm:@majorgilles/pi-learning-tutor", ...]   // study-tutor.overlay
"extraPackages": []                                              // study.overlay, work.overlay
```
These **add** to the global set for that profile only. The merge uses the existing `stable_package_merge` logic from `scripts.nix`:

```jq
def stable_package_merge:
  # Merge base packages[] with overlay extraPackages[]
  # Base wins on conflict (keeping original version)
;

($base * ($overlay | del(.extraPackages)))
| .packages = stable_package_merge($base.packages; $overlay.extraPackages)
```

The inventory applies this same merge per profile to determine each profile's complete extension set. For the default (no `--profile` flag), it reports each extension with a `profiles` array showing where it applies.

### 2.4 Design Decisions

| Decision | Rationale |
|----------|-----------|
| Flat resource list with profile arrays | A resource can appear in multiple profiles. Array avoids duplicating entries and makes filtering trivial. |
| `warnings[]` per resource + `lint_level` header | A consumer can check `schema_lint_level` to know if warnings are complete ("deep"), partial ("inline"), or absent ("none"). Solves the completeness signal problem. |
| `profile_inheritance` map | Documents that study-tutor inherits from study without requiring a separate resource directory. |
| `path` relative to pi module root | Portable. CLI resolves via `PI_SOURCE_DIR` env var at runtime. |
| `runtime` object separate from `metadata` | Metadata is from source pins; runtime info is from `~/.pi/agent/npm`. If runtime is unavailable, the key is absent (not null). Consumers check with `has("runtime")`. |
| No runtime lookup for MCP | MCP server definitions are in source files. Runtime state (binary present?) is tracked by `mcp-check`, not inventory. |
| No embedded file contents | Keeps the registry compact (~5-10KB) and fast to generate. File contents are consumed by lint and render stages only. |

### 2.5 Discovery Sources

| Kind | Source of truth | Discovery method |
|------|-----------------|-----------------|
| profiles | `policies/*.jsonc` | `find` *.jsonc, strip suffix. Aliases hard-coded (cautious/safe/readonly → safe). Inheritance: study-tutor → study (hard-coded). |
| extension (global) | `settings/global.json` → `packages[]` | jq extract. `profiles` = all known profiles. |
| extension (overlay) | `settings/*.overlay.json` → `extraPackages[]` | jq extract per overlay. `profiles` = `[profileName]` from overlay. Merge per `stable_package_merge`. |
| prompt | `resources/<profile>/prompts/*.md` | `find` by glob, parse YAML frontmatter with python3. `profiles` = `[profile]` + inherited profiles. |
| skill | `resources/<profile>/skills/*/SKILL.md` | `find` by glob, parse YAML frontmatter with python3. `profiles` = `[profile]` + inherited profiles. |
| agents | `resources/<profile>/AGENTS.md` | `find` by glob. `profiles` = `[profile]` (global is a pseudo-profile, not a user-facing profile). |
| mcp_server | `mcp/*.json` | Parse JSON, extract `mcpServers` keys. `profiles` derived from filename (`mcp/study.json` → `["study"]`, `mcp/global.json` → all profiles). |

---

## 3. Sub-Project A: Foundation — Resource Inventory

### 3.1 Command: `pi-admin resource-inventory`

**Purpose**: The single source-of-truth query for "what does this Pi setup contain?"

**Interface**:

```bash
# Default: human-readable table grouped by kind
pi-admin resource-inventory

# JSON output (canonical, machine-readable)
pi-admin resource-inventory --json

# Filter by kind
pi-admin resource-inventory --kind extension
pi-admin resource-inventory --kind prompt,skill

# Filter by profile
pi-admin resource-inventory --profile nixos

# Output warnings only
pi-admin resource-inventory --warnings-only

# Quick counts
pi-admin resource-inventory --counts
# > extensions: 18 global + 3 study-tutor overlay
# > prompts: 8, skills: 6, agents: 5, mcp_servers: 5
```

**Exit codes** (aligned with `lint-resources`):
- `0`: success, no warnings
- `1`: success with warnings (info or warning severity)
- `2`: errors present (error severity in any resource)
- `3`: internal error (file not found, parse failure)

### 3.2 Implementation — Six-Stage Merge Pipeline

The inventory pipeline has six stages. Each stage produces a JSON fragment; a final jq merge combines them:

```
STAGE 0: Enumerate profiles
  Input:  policies/*.jsonc
  Action: find + sed strip suffix + sort
  Output: all_profiles array ["nixos","safe","study","trusted","work","research"]
          Also known_inheritance map {"study-tutor": "study"}
          Also known_aliases map {"cautious":"safe","readonly":"safe","safe":"safe"}

STAGE 1: Discover global extensions
  Input:  settings/global.json
  Action: jq extract packages[] with type=="object" and .source | startswith("npm:")
          Each gets profiles = all known profiles
  Output: extension entries (global)

STAGE 2: Discover overlay extensions and merge
  Input:  settings/*.overlay.json
  Action: For each overlay file:
          - Read profileName from overlay
          - Extract extraPackages[]
          - Merge with global set using stable_package_merge logic:
            Overlay extension not in global → add with profiles=[profileName]
            Overlay extension same as global → skip (already in global set)
          (This is the same merge semantics used by compose_project_settings in scripts.nix)
  Output: overlay extension entries merged into global set

STAGE 3: Discover prompts
  Input:  resources/*/prompts/ directory tree
  Action: find + python3 parse YAML frontmatter
          For study-tutor inheritance: resources/study/prompts/*.md get profiles += ["study-tutor"]
  Output: prompt entries

STAGE 4: Discover skills
  Input:  resources/*/skills/*/SKILL.md
  Action: find + python3 parse YAML frontmatter
          Same study-tutor inheritance rule
  Output: skill entries

STAGE 5: Discover AGENTS files + MCP servers
  Input:  resources/*/AGENTS.md, mcp/*.json
  Action: find + jq
          mcp/global.json → profiles = all known profiles
          mcp/<profile>.json → profiles = [profile]
  Output: agents and mcp_server entries

STAGE 6: Merge, annotate with runtime info, add lint, emit
  Action: jq --slurp merge of all stages
          Run inline lint checks → populate warnings[]
          Set schema_lint_level = "inline"
          Add runtime version annotations from ~/.pi/agent/npm
          Format as table or JSON
```

### 3.3 Runtime Version Annotation

Version extraction uses **python3**, not sed, for robustness:

```bash
# Python3 extraction — handles scoped packages, npm: prefix, any version string
python3 -c "
import json, re, sys

npm_prefix = '$HOME/.pi/agent/npm'
source_pins = json.loads(sys.stdin.read())

for pin in source_pins:
    m = re.match(r'^npm:(.+)@(.+)$', pin)
    if not m:
        continue
    name, version = m.groups()
    pkg_json = f'{npm_prefix}/node_modules/{name}/package.json'
    try:
        with open(pkg_json) as f:
            installed = json.load(f).get('version', 'unknown')
    except (FileNotFoundError, json.JSONDecodeError):
        installed = None
    # emit as JSON annotation
"
```

This handles `@gotgenes/pi-lens@0.5.2` (scoped), `gentle-engram@0.1.7` (unscoped), and fails loudly on unexpected formats instead of silently producing wrong names.

**Failure handling**: If `~/.pi/agent/npm/node_modules` is missing or a specific package is uninstalled, `installed` is `None` and the runtime annotation is omitted. An info-level warning is added. The inventory itself never fails due to missing runtime data.

### 3.4 Output Format — Human Table

```
Resource Inventory for Pi module
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Profiles: nixos, safe, study, study-tutor, trusted, work, research
Lint level: inline

EXTENSIONS (21)                   Profiles (subset)    Source
─────────────────────────────────────────────────────────────────────
pi-lens (0.5.2 ✓)                 all                  npm:@gotgenes/pi-lens@0.5.2
gentle-engram (0.1.7 ✓)           all                  npm:gentle-engram@0.1.7
pi-learning-tutor (missing)       study-tutor           npm:@majorgilles/pi-learning-tutor
...

PROMPTS (8)                       Profile      Description
─────────────────────────────────────────────────────────────────────
pi-change.md                      nixos        Plan safe Pi setup changes
study.md                          study, st*   Start or continue a study session
...

SKILLS (6)                        Profile      Sections
─────────────────────────────────────────────────────────────────────
pi-nix-self-maintenance           nixos        When, Procedure, Pitfalls, Verification
learning-session                  study, st*   When, Procedure, Pitfalls
...

AGENTS FILES (5)                               Line count
─────────────────────────────────────────────────────────────────────
resources/global/AGENTS.md        120
resources/nixos/AGENTS.md         45
...

MCP SERVERS (5)                   Profiles     Direct tools
─────────────────────────────────────────────────────────────────────
mcp-nixos                         global       true
anki-read-strict                  study        false
...

WARNINGS (3)
─────────────────────────────────────────────────────────────────────
⚠ prompt "review.md" (study): missing 'argument_hint' in frontmatter
⚠ skill "work-session" (work): SKILL.md missing 'Pitfalls' section
⚠ extension "pi-learning-tutor" (study-tutor): not installed at expected path
```
*Note: `st*` = study-tutor (inherited)*

### 3.5 What `--json` Enables

The JSON output is the canonical interchange format for downstream consumers:

```bash
# P2 capability matrix: transform JSON into a pivot table
pi-admin resource-inventory --json \
  | jq -r '.resources[] | [.kind, .id, (.profiles | join(",")), .metadata.description // ""] | @tsv'

# P2 eval: capture baseline
pi-admin resource-inventory --json > /tmp/current-inventory.json

# CI gate: fail on errors
pi-admin resource-inventory --json | jq '[.resources[].warnings[] | select(.severity == "error")] | length > 0'
# exit 2 if errors present

# Verify all inline checks ran
pi-admin resource-inventory --json | jq -r '.schema_lint_level'
# Must be "inline" or "deep"
```

---

## 4. Sub-Project B: Quality Gate — Prompt/Skill Linting

### 4.1 Design Principle

Linting is **embedded in the inventory pipeline**, not a separate scan. The same pipeline that discovers resources also validates them. The `pi-admin lint-resources` command is a convenience wrapper that:

1. Runs `resource-inventory --json` internally
2. Applies additional deep lint checks
3. Emits results with the same exit code schema

Linting has **two modes**:

1. **Inline (attached to inventory)** — fast checks on frontmatter, paths, duplicates. Always runs as part of `resource-inventory`. Sets `schema_lint_level: "inline"` in the JSON header.
2. **Deep (standalone)** — slower checks reading full file contents, validating section shapes, cross-references. Run explicitly via `pi-admin lint-resources --deep`. Sets `schema_lint_level: "deep"`.

A consumer reading inventory JSON can check `schema_lint_level`:
- `"deep"` → all warnings are complete
- `"inline"` → only fast checks ran; deep issues not reported
- `"none"` → no lint was performed (initial bootstrap, before lint is implemented)

### 4.2 Command: `pi-admin lint-resources`

```bash
# Default: inline checks only (same as resource-inventory --warnings-only)
pi-admin lint-resources

# Deep mode: all inline + file content checks
pi-admin lint-resources --deep

# Compact output (errors + warnings only, one line each)
pi-admin lint-resources --short

# JSON output
pi-admin lint-resources --json

# Only errors (exit non-zero if any)
pi-admin lint-resources --errors-only

# Specific kind
pi-admin lint-resources --kind prompt
pi-admin lint-resources --kind skill,agents
```

**Exit codes** (aligned with `resource-inventory`):
- `0`: clean — no warnings or errors
- `1`: warnings only (info or warning severity)
- `2`: errors present
- `3`: internal error (file not found, parse failure)

### 4.3 Lint Rules

#### Inline checks (fast, always-on, part of `resource-inventory`)

| Rule ID | Target | Check | Severity |
|---------|--------|-------|----------|
| `frontmatter-description` | prompt, skill, agents | YAML frontmatter has a `description` field | error if absent |
| `frontmatter-present` | prompt, skill, agents | File starts with valid YAML frontmatter (`---`) | error if absent |
| `argument-hint` | prompt | Frontmatter has `argument-hint` field | warning if absent |
| `path-exists` | all | Source `path` resolves to an existing file | error if missing |
| `duplicate-id` | all | No two resources share the same `kind` + `id` | error if conflict |
| `filename-convention` | prompt, skill, agents | Names follow kebab-case (lowercase, hyphens) | info if violates |
| `runtime-match` | extension | Installed version matches pinned version (when runtime data available) | warning if mismatch |
| `runtime-missing` | extension | Pinned package is not installed at expected npm path | warning if absent |

#### Deep checks (opt-in with `--deep`)

| Rule ID | Target | Check | Severity | Execution cost |
|---------|--------|-------|----------|----------------|
| `skill-sections-present` | skill | SKILL.md contains required sections (`## When to Use`, `## Procedure`, `## Pitfalls` or `## Verification`) | error if any missing | Reads full SKILL.md |
| `description-nonempty` | prompt, skill, agents | `description` is not empty or a placeholder like "TODO" | warning if generic | Reads frontmatter only (already available) |
| `cross-ref-links` | prompt, skill | Relative paths in content resolve to existing files | warning if broken | Scans file body for `[text](path)` |
| `skill-registry-indexed` | skill | Skill appears in `<available_skills>` section or registry | info if unindexed | Reads AGENTS.md or registry file |
| `agents-file-size` | agents | AGENTS.md is under 150 lines | warning if exceeded | Line count check |
| `prompt-description-match` | prompt | Description in frontmatter matches prompt's content theme (basic: first 100 chars contain description keywords) | info if mismatched | Reads first 100 chars beyond frontmatter |

**Important**: Deep checks are intentionally bounded. They read file bodies (up to ~500 lines per file) and validate patterns. They do NOT run NLP, embeddings, or LLM analysis. The `prompt-description-match` check is a simple keyword overlap heuristic — anything more sophisticated belongs in P2 evals.

### 4.4 Rule Registry

The rule set is defined as a data-driven JSON array, not hard-coded if-else chains:

```jsonc
// In the script, rules are loaded from an embedded JSON array
[
  {"id": "frontmatter-description", "kinds": ["prompt","skill","agents"], "checks": ["frontmatter.has_description"], "severity": "error", "mode": "inline"},
  {"id": "duplicate-id", "kinds": ["*"], "checks": ["dedup.kind_id"], "severity": "error", "mode": "inline"},
  {"id": "cross-ref-links", "kinds": ["prompt","skill"], "checks": ["content.links_resolve"], "severity": "warning", "mode": "deep"},
  {"id": "skill-sections-present", "kinds": ["skill"], "checks": ["content.has_section('## When to Use')", "content.has_section('## Procedure')"], "severity": "error", "mode": "deep"}
]
```

Adding a new rule in P2 means adding one row to this array and writing one check handler. Handlers are named functions in python3 that accept a resource entry and file path, returning `null` (no issue) or a warning object.

Future P2 rules might add:
```jsonc
{"id": "description-content-match", "kinds": ["prompt"], "checks": ["content.keyword_overlap >= 0.3"], "severity": "info", "mode": "deep"}
```

---

## 5. Sub-Project C: Artifact — Generated Extension Manifest

### 5.1 Command: `pi-admin generate-extension-manifest`

```bash
# Generate to stdout (Markdown)
pi-admin generate-extension-manifest

# Write to docs/EXTENSIONS.md
pi-admin generate-extension-manifest --write

# Dry-run: show diff vs current file
pi-admin generate-extension-manifest --diff

# Check: exit 0 if current file matches, exit 1 with diff if not
pi-admin generate-extension-manifest --check
```

### 5.2 Design

The current `docs/EXTENSIONS.md` is hand-maintained. This sub-project makes it **generated from source**, with a **diff gate** to prevent silent drift.

**Data flow**:

```
settings/global.json  ──→ jq extract                 ──→  python3 template  ──→  Markdown
settings/*.overlay.json ──→ jq merge (stable_package) ──→  extension list
runtime ~/.pi/agent/npm ──→ version check             ──→  version annotations
```

**Template engine**: Python3 with simple string templates (NOT shell interpolation). Python3 is already available and avoids pipe-escaping problems:

```python
# python3 template — handles pipe-escaping, missing fields, alignment
TABLE_HEADER = "| Extension | Tool(s) / surface | Use for | Risk class | Version | Profiles |\n|---|---|---|---|---|---|\n"

def render_row(ext):
    name = ext["id"]
    tools = ext.get("tools", "—")
    use_for = ext["metadata"].get("description", "—").replace("|", "\\|")
    risk = ext.get("risk_class", "—")
    version = ext.get("runtime", {}).get("installed_version", ext["metadata"].get("version", "—"))
    profiles = ", ".join(ext["profiles"][:3])
    if len(ext["profiles"]) > 3:
        profiles += f", +{len(ext['profiles'])-3} more"
    return f"| `{name}` | {tools} | {use_for} | {risk} | {version} | {profiles} |\n"
```

**Output template**:

```markdown
# Installed Pi Extensions

> **Auto-generated** by `pi-admin generate-extension-manifest`.
> Source of truth: `settings/global.json`. Last generated: 2026-06-20.
> Do not edit by hand. Run `pi-admin generate-extension-manifest --check` after changing settings.

## Extension table

| Extension | Tool(s) / surface | Use for | Risk class | Version | Profiles |
|---|---|---|---|---|---|
| `pi-lens` | LSP, ast-grep tools | Code intelligence | code-intelligence | 0.5.2 | nixos, study, work, +5 more |
| `gentle-engram` | mem_* tools | Durable project memory | memory | 1.16.1 | all |
| … | … | … | … | … | … |

## Overlay extensions

| Extension | Profile | Source |
|---|---|---|
| `pi-learning-tutor` | study-tutor | `settings/study-tutor.overlay.json` |
| `keating` | study-tutor | `settings/study-tutor.overlay.json` |
| `teach-me` | study-tutor | `settings/study-tutor.overlay.json` |

## Design notes

- For memory system details, see `docs/MEMORY.md`.
- For extension risk classes, see `docs/SECURITY.md`.
- Runtime version is checked against `~/.pi/agent/npm/node_modules/`.
```

### 5.3 `--check` Mode

An idempotence check useful for CI and post-change validation:

```bash
pi-admin generate-extension-manifest --check
# 0 = current docs/EXTENSIONS.md matches generated output
# 1 = mismatch, diff shown on stdout
# 3 = internal error
```

This prevents the manifest file from drifting when someone edits `settings/global.json` but forgets to regenerate the docs file.

**Important**: `--write` writes to the Nix source tree, which may require write access. The command warns if the target is not writable and suggests the user run from the repo root with appropriate permissions (no `sudo` needed if the user owns the NixOS repo).

### 5.4 Relation to `docs/LOOKUP.json`

Add a lookup key:

```json
"extension_manifest": [
  "docs/EXTENSIONS.md",
  "settings/global.json",
  "settings/study-tutor.overlay.json",
  "scripts.nix  # pi-admin generate-extension-manifest"
],
```

---

## 6. Sub-Project D: UX — Profile Explainability

### 6.1 Command: `pi-admin explain-profile`

**Purpose**: A single command that answers "what is this Pi session configured to do?" — consolidating information currently spread across wrappers, settings, policies, MCP configs, resources, and docs.

```bash
# Default: explain the currently active profile
pi-admin explain-profile

# Specific profile
pi-admin explain-profile --profile study
pi-admin explain-profile --profile nixos

# JSON output
pi-admin explain-profile --json

# Compact output (one-line summary)
pi-admin explain-profile --short
# > Current profile: nixos (selected by smart launcher from /home/daniil/NixOS)
```

### 6.2 Output Structure

```
pi-admin explain-profile --profile nixos

PROFILE: nixos
─────────────────────────────────────────────────────────────

SELECTION REASON
  Auto-selected by smart launcher from /home/daniil/NixOS
  (matches NixOS repository path configured in programs.pi.paths.nixosRepo)

PERMISSION POLICY
  File: policies/nixos.jsonc
  Effective rules:
  • Shell: allowed (with path restrictions)
  • Edit: allowed (within repo tree)
  • Write: allowed (within repo tree)
  • Network: allowed
  • Raw bypass: explicit (pi-raw)

SETTINGS
  Base:       settings/global.json
  Overlays:   (none for this profile)
  Extensions: 18 global packages (see `pi-admin generate-extension-manifest`)

MCP CONFIGURATION
  File: mcp/nixos.json
  Servers: mcp-nixos (directTools: true), engram (directTools: false)
  Lazy servers: both

RESOURCE ROOTS
  Prompts:   resources/nixos/prompts/ (4 prompts)
  Skills:    resources/nixos/skills/ (1 skill)
  AGENTS:    resources/nixos/AGENTS.md
  Managed:   yes (source → pi-admin sync nixos)
  Seed:      no

SYNC / DRIFT STATE
  Source hash:    a1b2c3d4 (git commit HEAD)
  Runtime sync:   synced (last: 2026-06-19)
  Drift check:    OK (pi-admin drift reported match)
  Source check:   OK (pi-admin source-check: 12/12 passed)

CAVEATS
  • Not a sandbox: policy-backed safety, not OS isolation
  • Cautious/read-only/safe aliases are convenience modes, not OS sandboxes
  • Engram memory: disabled in study and work profiles

FOR MORE
  • pi-admin resource-inventory --profile nixos
  • pi-admin lint-resources --profile nixos
  • pi-admin drift
  • docs/PROFILES.md
```

### 6.3 Information Sources & Error Handling

Each section below shows its data source and how failures are handled.

| Section | Data source | Fetch method | If fetch fails |
|---------|------------|--------------|----------------|
| Profile name | `PI_PROFILE` env var or smart-launcher detection | Read env var, call `detect_mode()` from `pi-admin` dispatch | Show "unknown profile" |
| Selection reason | Smart-launcher CWD logic | Replicate `detect_mode()` logic inline | Show "unknown context" |
| Permission policy | `policies/<profile>.jsonc` | Read file, JSONC-strip via existing `jsoncStrip` python script | Show "⚠ policy file not found" |
| Settings | `settings/global.json` + overlay chain (if applicable) | jq merge using `composeSettingsJq` from `scripts.nix` | Show "⚠ settings file not found" |
| MCP config | `mcp/<profile>.json` | jq extract `mcpServers` keys | Show "⚠ no MCP config" |
| Resource roots | `resources/<profile>/` | `find` count from inventory output (read from cached result, not re-run full inventory) | Show "⚠ resource discovery unavailable" |
| Drift state | `pi-admin drift` (in-process call to the drift check) | Source the drift script's check functions directly, NOT via subprocess call to `pi-admin drift` | Show "⚠ drift check unavailable" |
| Source check state | `pi-admin source-check` (in-process call, same approach) | Source the source-check script's check functions directly | Show "⚠ source check unavailable" |
| Caveats | Section 6.5 trigger table | Evaluate trigger conditions inline | ⸺ |

**Key design rule**: `explain-profile` does NOT call `pi-admin` as a subprocess. It imports the same check functions used by `drift` and `source-check` directly. This avoids:
- Circular dependency (`pi-admin` calling `pi-admin`)
- Cascading failure (drift failure crashing explain-profile)
- Redundant process spawn overhead

The check functions are defined as separate shell libraries under `lib/` or as python3 modules that both `pi-admin drift` and `pi-admin explain-profile` can source. If the drift/source-check functions are unavailable, `explain-profile` continues with degraded output rather than failing.

### 6.4 `--json` Output

```json
{
  "profile": "nixos",
  "selection_reason": "smart-launcher: cwd matches nixosRepo path",
  "generated_at": "2026-06-20T13:00:00Z",
  "policy": {
    "path": "policies/nixos.jsonc",
    "summary": {
      "shell": "allowed",
      "edit": "allowed",
      "network": "allowed",
      "raw_bypass": "explicit"
    }
  },
  "settings": {
    "base": "settings/global.json",
    "overlays": [],
    "extensions_count": 18
  },
  "mcp": {
    "path": "mcp/nixos.json",
    "servers": [
      {"name": "mcp-nixos", "direct_tools": true, "lazy": true},
      {"name": "engram", "direct_tools": false, "lazy": true}
    ],
    "status": "available"
  },
  "resources": {
    "prompts": {"count": 4, "paths": ["resources/nixos/prompts/..."]},
    "skills": {"count": 1, "paths": ["resources/nixos/skills/..."]},
    "agents": "resources/nixos/AGENTS.md",
    "status": "ok"
  },
  "drift": {
    "status": "ok",
    "detail": "all source files match runtime",
    "last_sync": "2026-06-19"
  },
  "source_check": {
    "status": "ok",
    "passed": 12,
    "total": 12
  },
  "caveats": [
    "not a sandbox: policy-backed safety, not OS isolation",
    "Engram memory: disabled in study and work profiles"
  ]
}
```

All failure cases use a `status` field: `"ok"`, `"unavailable"`, or `"error"`. Consumers check `status` before reading other fields.

### 6.5 Caveats Engine

The caveats section is derived from a data-driven trigger table, not hard-coded strings:

```jsonc
// Embedded caveat rules (one row per caveat)
[
  {
    "id": "not-a-sandbox",
    "text": "Not a sandbox: policy-backed safety, not OS isolation",
    "trigger": "profile != 'raw'",
    "profiles": ["*"]
  },
  {
    "id": "engram-disabled-study",
    "text": "Engram memory: disabled in study profile",
    "trigger": "engram_present == false",
    "profiles": ["study", "study-tutor"]
  },
  {
    "id": "engram-disabled-work",
    "text": "Engram memory: disabled in work profile",
    "trigger": "engram_present == false",
    "profiles": ["work"]
  },
  {
    "id": "cautious-aliases",
    "text": "Cautious/read-only/safe aliases are convenience modes, not OS sandboxes",
    "trigger": "true",
    "profiles": ["cautious", "safe", "readonly"]
  },
  {
    "id": "no-sandbox-available",
    "text": "No OS-level sandbox available (pi-sandbox not yet implemented)",
    "trigger": "true",
    "profiles": ["*"]
  },
  {
    "id": "cautious-proposal-mode",
    "text": "Cautious mode: edits produce proposals, not direct writes",
    "trigger": "profile == 'cautious' || profile == 'safe' || profile == 'readonly'",
    "profiles": ["cautious", "safe", "readonly"]
  }
]
```

Adding a caveat means adding one row to this JSON array. No code change beyond the data. Triggers are evaluated as simple conditions (profile match, engram check, file existence) — no expression language needed.

---

## 7. Integration & Wiring

### 7.1 New Commands

All new commands follow the existing `pi-admin` dispatch pattern:

| Command | Sub-project | Script location | Dependencies |
|---------|-------------|-----------------|-------------|
| `pi-admin resource-inventory` | A | `scripts.nix` or extracted `scripts/resource.nix` | jq, find, python3 |
| `pi-admin lint-resources` | B | `scripts.nix` or extracted `scripts/resource.nix` | jq, find, python3 |
| `pi-admin generate-extension-manifest` | C | `scripts.nix` or extracted `scripts/resource.nix` | jq, python3 |
| `pi-admin explain-profile` | D | `scripts.nix` or extracted `scripts/resource.nix` | jq, find, python3 |

**Dispatch wiring** (add to `piAdmin` case statement in `wrappers.nix`):

```bash
resource-inventory)
  exec ${scripts.piResourceInventory}/bin/pi-resource-inventory "$@"
  ;;
lint-resources)
  exec ${scripts.piLintResources}/bin/pi-lint-resources "$@"
  ;;
generate-extension-manifest|gen-ext-manifest)
  exec ${scripts.piGenerateExtensionManifest}/bin/pi-generate-extension-manifest "$@"
  ;;
explain-profile)
  exec ${scripts.piExplainProfile}/bin/pi-explain-profile "$@"
  ;;
```

### 7.2 Wiring in `home-module.nix`

```nix
home.packages = [
  # ... existing packages ...
  scripts.piResourceInventory
  scripts.piLintResources
  scripts.piGenerateExtensionManifest
  scripts.piExplainProfile
];

# Update help text in piAdmin usage()
```

### 7.3 `docs/LOOKUP.json` Updates

```json
{
  "resource_inventory": [
    "scripts.nix  # pi-admin resource-inventory",
    "resources/analysis/agent-capability-roadmap.md",
    "settings/global.json",
    "settings/*.overlay.json",
    "resources/"
  ],
  "lint_resources": [
    "scripts.nix  # pi-admin lint-resources"
  ],
  "extension_manifest": [
    "docs/EXTENSIONS.md",
    "settings/global.json",
    "settings/study-tutor.overlay.json",
    "scripts.nix  # pi-admin generate-extension-manifest"
  ],
  "explain_profile": [
    "scripts.nix  # pi-admin explain-profile",
    "docs/PROFILES.md",
    "policies/",
    "mcp/",
    "resources/"
  ]
}
```

### 7.4 `scripts.nix` Impact

**Short-term** (P1 only, ~300 lines total): Add script derivations inline in `scripts.nix`. Each command is a separate `writeShellApplication` or `pkgs.writeText` entry, matching the existing pattern used by `pi-drift-check`, `pi-source-check`, etc.

**Medium-term** (~300+ lines total): Extract all resource scripts into a dedicated `scripts/resource.nix` file and import it from `scripts.nix`. This follows the roadmap's P6 maintainability goal but is allowed before P6 because P1 adds enough surface area to justify it.

### 7.5 Nix Build Impact

All P1 scripts use **zero new Nix build dependencies**. They rely on:
- `pkgs.jq` — already in the build closure
- `pkgs.python3` — already in the build closure
- `pkgs.findutils`, `pkgs.gnugrep`, `pkgs.gnused`, `pkgs.coreutils` — all already present

The build cost is a few small `writeShellApplication` derivations — negligible on `nixos-rebuild` (sub-second).

---

## 8. Extensibility to P2+

### 8.1 P2 Capability Matrix

The resource inventory JSON is the direct input for the P2 capability matrix:

```
P1: resource-inventory --json
    ↓  (pipe via --stdin in P2)
P2: pi-admin capability-matrix [--stdin] [--json]
    Columns: kind, id, profiles, tools, risk, validation_command
```

Adding a `tools` field to the inventory schema (for extensions) and a `validation_command` field (for any resource) in P2 is **backward-compatible**:

```jsonc
// P2 extension to the inventory schema (new fields only)
{
  "kind": "extension",
  "id": "pi-lens",
  // ↓ New in P2, P1 consumers ignore them
  "tools": ["lsp_diagnostics", "lsp_navigation", "ast_grep_search"],
  "validation_command": "pi-admin source-check",
  "risk_class": "code-intelligence"
}
```

For P2, a `--stdin` flag on `lint-resources` and `generate-extension-manifest` would allow piping:

```bash
pi-admin resource-inventory --json \
  | pi-admin lint-resources --stdin \
  | pi-admin capability-matrix --stdin
```

This is explicitly deferred to P2 — P1 commands are standalone.

### 8.2 P2 Regression Evals

The inventory JSON + lint output provides the baseline for evals:

| Eval | Data source | Mechanism |
|------|------------|-----------|
| AGENTS routing | Inventory profile mapping | Read each AGENTS.md, verify routing by checking file header + LOOKUP.json |
| Memory routing | Inventory extension list | Verify engram/hermes presence per profile matches docs/MEMORY.md |
| Prompt/skill selection | Inventory | Verify at least one prompt and one skill exist per active profile |
| Review delegation | Inventory subagent list | Verify rpiv-advisor + pi-subagents are present |
| Lint regression | Inventory JSON snapshot | Compare current lint output against stored baseline; any new errors fail the eval |

### 8.3 `explain-profile` as P2 Hub

The `explain-profile --json` output grows into a hub that aggregates checks from other commands. In P2, add:

```bash
pi-admin explain-profile --json --include-drift --include-mcp-check
```

This keeps `explain-profile` as the user-facing entrypoint while individual commands remain standalone and independently useful.

### 8.4 Schema Versioning

The registry `version` field enables branching:

```bash
version=$(echo "$inventory" | jq -r '.version')
case "$version" in
  1) transform_v1 ;;
  2) pass_through ;;
  *) fail "unsupported schema version $version" ;;
esac
```

Schema evolution rules:
- Adding new optional fields at any level → minor bump (1.x), backward-compatible
- Changing semantics of existing fields → major bump (2.0), consumers check version
- Removing fields → major bump, never in P1

---

## 9. Dependency Order & Risk

### 9.1 Recommended Implementation Order

```
Phase 1: Resource inventory (core foundation)
  └── pi-admin resource-inventory --json
      - Stage 0: profile enumeration (from policies/)
      - Stage 1-2: extension discovery (global + overlay merge)
      - Stage 3-5: prompt, skill, agents, MCP discovery
      - Stage 6: runtime version annotation, inline lint, merge + emit
  └── Human table output (--no-json default)
  └── Exit codes: 0 clean, 1 warnings, 2 errors, 3 internal

Phase 2: Inline linting (runs with inventory, no separate command yet)
  └── Inline lint rules: frontmatter presence, paths, duplicates, runtime match
  └── schema_lint_level tracking in JSON header

Phase 3: Deep linting (standalone command)
  └── pi-admin lint-resources --deep
  └── Section checks, cross-refs, skill registry indexing
  └── --short output mode

Phase 4: Extension manifest generation
  └── pi-admin generate-extension-manifest
  └── python3 template (not shell interpolation)
  └── --write, --diff, --check modes

Phase 5: Profile explainability
  └── pi-admin explain-profile
  └── In-process drift/source-check function import (NOT subprocess call)
  └── Caveat engine (data-driven JSON trigger table)
  └── --json, --short modes

Phase 6: Documentation & routing
  └── Update docs/EXTENSIONS.md (via --write, committed)
  └── Update docs/LOOKUP.json (new routes)
  └── Update resources/analysis/TRACKING.md (mark P1 complete)
  └── (Optional) Add "Resources" section to docs/RESOURCES.md
```

### 9.2 Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| YAML frontmatter parsing in shell is fragile | Medium | High (false warnings) | Use python3 with `import yaml`. PyYAML is part of standard python3. The existing `jsonc-strip.py` pattern in `scripts.nix` proves the approach. |
| Overlay merge logic differs from `scripts.nix` `composeSettingsJq` | Medium | High (inconsistent extension reporting) | Reuse the exact same `stable_package_merge` jq function from `scripts.nix`. The inventory calls `jq -s 'EXACT_COMPOSE_JQ'` — not a reimplementation. |
| Runtime version annotation fails silently (empty node_modules) | Low | Low (missing runtime field) | The `runtime` key is simply absent when data is unavailable. Consumers check `has("runtime")`. An info-level warning is added. |
| `explain-profile` depends on drift/source-check functions that don't exist as shared libraries | Medium | Medium (duplicate logic or subprocess call) | **Solution**: Extract drift and source-check core logic into `lib/drift.sh` / `lib/source-check.sh` before building explain-profile. Both `pi-admin drift` and `pi-admin explain-profile` source the same library. This is a pre-requisite for Phase 5. |
| Inventory JSON schema drifts from consumers | Medium | Medium (broken pipes) | Schema version field + documented evolution rules. Pin v1 in the first implementation. All P1 consumers validate version >= 1 before processing. |
| Large output with `--warnings-only` on clean system is confusing | Low | Low (empty output) | Show "No warnings. Resource inventory is clean." instead of an empty table (same pattern as `pi-admin policy-lint` which shows "0 warnings, 0 errors"). |
| New scripts bloat `scripts.nix` past maintainability threshold | Medium | Medium (refactoring debt) | Extract to `scripts/resource.nix` at ~300 lines. The threshold is: when the 4 new scripts together exceed 300 lines, extract. Don't wait for P6. |

### 9.3 Pre-requisite: Shared Library Extraction

Before Phase 5, the drift and source-check functions must be extracted into shared libraries that both `pi-admin drift`/`pi-admin source-check` AND `pi-admin explain-profile` can source:

```bash
# lib/drift.sh — sourced by pi-drift-check AND pi-explain-profile
check_drift() {
  local profile="$1"
  # ... drift comparison logic ...
  echo "$result"
}

# lib/source-check.sh — sourced by pi-source-check AND pi-explain-profile
check_source_integrity() {
  local profile="$1"
  # ... source validation logic ...
  echo "$result"
}
```

This extraction is a pre-requisite of Phase 5, not an independent task. It adds ~20 lines of shell to move functions from the existing scripts to shared files and import them via `. "$PI_SOURCE_DIR/lib/drift.sh"`.

### 9.4 Explicit Non-Goals

These are **out of scope** for P1:

- ❌ Agent capability matrix (P2) — Schema designed for it, but the pivot/visualization is P2 work.
- ❌ `--stdin` piping between commands (P2) — P1 commands are standalone. Pipe support deferred to P2.
- ❌ Regression evals (P2) — Lint output is a building block, but eval fixtures and runners are P2.
- ❌ MCP governance report (P2) — `pi-admin mcp-check` already covers static validation.
- ❌ Launch metadata stamping (TRACKING.md P1.5) — Separate item, tracked in TRACKING.md.
- ❌ Nix packaging changes — No new Nix derivations for existing npm packages.
- ❌ Runtime state mutation — All P1 commands are read-only. They never write to runtime state.
- ❌ Always-loaded AGENTS.md changes — Inventory and explain commands are on-demand. Nothing is added to always-loaded context.

---

## 10. Appendix: Reference — Current Resource Layout

### 10.1 Source tree

```
modules/programs/cli/pi/
├── settings/
│   ├── global.json                       ← Extension pins (18 packages)
│   ├── study.overlay.json               ← extraPackages: [] (none)
│   ├── study-tutor.overlay.json         ← extraPackages: [pi-learning-tutor, keating, teach-me]
│   └── work.overlay.json                ← extraPackages: [] (none)
├── mcp/
│   ├── global.json                       ← MCP server config (all profiles)
│   ├── nixos.json                        ← MCP for nixos profile
│   ├── research.json                     ← MCP for research profile
│   ├── study.json                        ← MCP for study profile
│   └── work.json                         ← MCP for work profile
├── policies/
│   ├── nixos.jsonc                       ← Permission policies
│   ├── safe.jsonc
│   ├── study.jsonc
│   ├── trusted.jsonc
│   ├── work.jsonc
│   └── research.jsonc
├── resources/
│   ├── global/
│   │   ├── AGENTS.md                     ← Always-loaded instructions
│   │   └── simplify-conventions.md
│   ├── nixos/
│   │   ├── AGENTS.md                     ← NixOS profile instructions
│   │   ├── prompts/
│   │   │   ├── pi-change.md
│   │   │   ├── security.md
│   │   │   ├── setup.md
│   │   │   └── status.md
│   │   └── skills/
│   │       └── pi-nix-self-maintenance/
│   │           └── SKILL.md
│   ├── study/
│   │   ├── AGENTS.md
│   │   ├── prompts/
│   │   │   ├── study.md
│   │   │   ├── consolidate.md
│   │   │   ├── map-topic.md
│   │   │   └── review.md
│   │   └── skills/
│   │       ├── learning-session/SKILL.md
│   │       ├── memory-consolidation/SKILL.md
│   │       ├── spaced-review/SKILL.md
│   │       └── topic-graph-maintenance/SKILL.md
│   └── work/
│       ├── AGENTS.md
│       ├── prompts/
│       │   └── work.md
│       └── skills/
│           └── work-session/SKILL.md
├── docs/
│   ├── INDEX.md                          ← Wiki index
│   ├── LOOKUP.json                       ← Machine route map
│   ├── EXTENSIONS.md                     ← Human extension reference (to be generated)
│   └── ...
├── lib/                                  ← Shared libraries (pre-requisite for Phase 5)
│   ├── drift.sh                          ← Extracted drift check functions
│   └── source-check.sh                   ← Extracted source-check functions
└── resources/analysis/
    ├── agent-capability-roadmap.md       ← This plan's source document
    ├── improvement-plan.md
    └── TRACKING.md                       ← Progress tracking
```

### 10.2 Current Inventory (for reference)

| Kind | Count | Profile distribution | Notes |
|------|-------|---------------------|-------|
| Extension (global) | 18 | all 6 profiles (nixos, safe, study, trusted, work, research) | From `global.json` packages[] |
| Extension (overlay) | 3 | study-tutor only | From `study-tutor.overlay.json` extraPackages[] |
| Prompt | 8 | nixos (4), study + study-tutor (4), work (1) | study-tutor inherits study's 4 prompts |
| Skill | 6 | nixos (1), study + study-tutor (4), work (1) | study-tutor inherits study's 4 skills |
| AGENTS file | 5 | global, nixos, study, study-tutor, work | study-tutor has its own AGENTS.md |
| MCP server | 5 (across 6 configs) | global (all), nixos, research, study, work | nixos+global share same server set |

### 10.3 Decision Log

This plan adds:
- 4 new `pi-admin` subcommands (shell scripts in `scripts.nix` or extracted `scripts/resource.nix`)
- 1-2 shared library files (`lib/drift.sh`, `lib/source-check.sh`) — extracted from existing scripts
- Updates to `docs/EXTENSIONS.md` (generated from source, committed)
- Updates to `docs/LOOKUP.json` (new routing entries)
- Updates to `resources/analysis/TRACKING.md` (mark P1 items in progress/complete)

This plan does **not** add:
- New Nix options
- New wrapper profiles
- New runtime state
- New always-loaded AGENTS.md content
- New build dependencies
- New compiled languages or runtimes
