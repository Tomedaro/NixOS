# Simplify conventions

This file is read on demand by `/simplify`.


`/simplify` means small, behavior-preserving clarity work on changed files. It is not redesign, feature work, dependency cleanup, architecture migration, formatting churn, style normalization, or a general code review.

A correct result may be **no changes**.

The default posture is conservative: prefer a small obvious improvement over a clever refactor. If semantic equivalence is uncertain, leave the code unchanged and explain why.

## Core contract

`/simplify` must preserve:

- evaluated Nix values;
- NixOS/Home Manager module semantics;
- flake outputs and exported names;
- package identity, versions, hashes, and source pins;
- service enablement and dependencies;
- option priorities and merge behavior;
- import topology;
- host-specific behavior;
- secrets and security boundaries.

Do not make code shorter by making behavior harder to reason about.

## Work scope

Start from the files changed in `git diff`.

Inspect nearby files only to understand:
- local style;
- option definitions;
- imports;
- references;
- formatter/check commands;
- whether a name/path is public.

Do not scan or rewrite the whole repo unless needed to prove safety.

Do not touch unrelated files for formatting, sorting, or preference cleanup.

## Decision procedure

For each changed file:

1. Classify it:
   - NixOS module;
   - Home Manager module;
   - flake or flake support file;
   - package expression;
   - overlay or override;
   - host-specific config;
   - non-Nix support file.

2. Identify candidate improvements:
   - dead local bindings;
   - repeated local expressions;
   - unclear private names;
   - needless nesting;
   - broad hidden scope;
   - obsolete comments;
   - commented-out code;
   - debug leftovers;
   - dense expressions that need local names.

3. Check for complexity displacement:
   - Does the change merely hide complexity in a helper, file split, `mapAttrs`, `mkMerge`, or abstraction?
   - Does it make grep/search/navigation worse?
   - Does it reduce visible nesting while increasing semantic indirection?

4. Assign risk:
   - Green: purely local, behavior-preserving, easy to verify.
   - Yellow: probably safe, but touches structure, scope, imports, option declarations, merging, or module boundaries.
   - Red: may alter evaluation, public interface, package identity, host behavior, security, deployment, or module semantics.

5. Edit Green candidates by default.
   - Edit Yellow candidates only when the clarity win is strong and locally justified.
   - Do not edit Red candidates during `/simplify`.

6. Review the final diff.
   - If the diff is harder to review than the original code, revert the simplification.

## Green changes: usually safe

These are good `/simplify` targets when local context confirms safety:

- Remove unused private `let` bindings.
- Remove obsolete comments, commented-out code, temporary TODOs, and debugging leftovers.
- Replace repeated long local expressions with a clearly named binding.
- Rename private local variables when the new name reveals intent.
- Inline a short one-use binding when the name adds no meaning.
- Split a dense expression across lines when it improves reading.
- Preserve meaningful comments while removing comments that merely restate code.
- Reduce accidental duplication inside the same file with a local binding.
- Prefer explicit scope when it reduces ambiguity without adding noise.

## Yellow changes: handle with care

These require a clear reason and a short final-summary note:

- Moving code between files.
- Extracting a new module.
- Introducing a helper function.
- Replacing nested attrsets with dotted assignments, or the reverse.
- Replacing `with pkgs;` with `inherit (pkgs) ...`.
- Replacing `rec` with `let ... in`.
- Introducing `lib.mkMerge`.
- Changing option declarations.
- Changing package override structure.
- Reordering attributes or imports.
- Adding comments to explain non-obvious behavior.

## Red changes: do not do during `/simplify`

Do not change these unless the user explicitly requested that exact change:

- `flake.lock`;
- flake input URLs, pins, branches, commits, `follows`, supported systems, or output names;
- public option names;
- host names;
- imported file names;
- paths used for imports, persistence, state, data, secrets, or systemd units;
- secrets, keys, encrypted files, secret wiring, or credential paths;
- hardware configuration;
- boot, disk, filesystem, persistence, impermanence, swap, LUKS, or initrd settings;
- users, groups, permissions, sudo/doas, SSH, VPN, firewall, ports, or network security;
- service enablement, ordering, dependencies, timers, sockets, or restart behavior;
- package versions, source URLs, hashes, patches, build phases, install paths, or passthru tests;
- overlays, overlay ordering, package identity, or override mechanism;
- `specialArgs`, `extraSpecialArgs`, `_module.args`, or module argument plumbing;
- `mkForce`, `mkOverride`, `mkBefore`, `mkAfter`, `mkOrder`, or priority/order semantics;
- generated files, lock files, vendored files, or machine-generated config;
- broad formatting of unrelated files;
- flattening or abstraction that changes laziness, recursion, option priority, attrset update behavior, or module merge behavior.

## Nix language rules

### Scope

Prefer explicit scope over broad hidden scope.

Good:
- `pkgs.git` when the source remains clear;
- `inherit (pkgs) git jq;` when several names from the same source are reused;
- `inherit (lib) mkIf mkOption types;` when the local file already follows that style;
- a local `let` binding for repeated or conceptually important values.

Allowed when already clear:
- small package lists using `with pkgs; [ ... ]`.

Avoid:
- adding top-level `with`;
- adding broad nested `with`;
- hiding where names come from;
- mechanically replacing every existing `with` when the diff adds noise.

### `rec`

Do not add `rec` unless sibling self-reference is intentional and clearer than alternatives.

Prefer `let ... in` when:
- a shared value has a meaningful name;
- a value is used in multiple places;
- it avoids accidental self-reference;
- it reduces ambiguity.

Do not remove `rec` if doing so requires a larger rewrite or makes the code harder to read.

### `let ... in`

Use `let ... in` for:
- `cfg`;
- repeated expressions;
- long expressions;
- meaningful paths or command strings;
- local package lists;
- values that explain intent.

Avoid `let` when:
- the binding is used once;
- the name adds no meaning;
- it separates a simple value too far from its use;
- it hides ordinary NixOS option assignments.

### `inherit`

Use `inherit` to reduce noise only when the source remains obvious.

Avoid:
- long `inherit` lists that obscure what is used;
- ambiguous sources;
- style-only rewrites from qualified names to `inherit`.

### Attribute sets and merging

Remember:

- `//` is shallow.
- `lib.recursiveUpdate` is Nix attrset merging.
- NixOS/Home Manager module merging is different.
- `lib.mkMerge` is for module definitions, not ordinary attrset cleanup.

Do not replace module-system merging with plain attrset merging.

Do not use `//` to flatten nested config unless shallow replacement is exactly intended.

### URLs, paths, and purity

Quote URLs.

Do not introduce:
- `<nixpkgs>` lookup paths;
- dependency on `$NIX_PATH`;
- impure imports;
- unpinned fetches;
- source paths whose store name accidentally depends on the parent directory;
- new fetchers without the repo's existing pin/hash discipline.

In flake code, preserve the existing explicit input/output structure.

## NixOS and Home Manager module rules

### Module shape

For modules with options, the common shape is:

```nix
{ lib, config, pkgs, ... }:

let
  cfg = config.<namespace>;
in
{
  options.<namespace> = {
    enable = lib.mkEnableOption "...";
  };

  config = lib.mkIf cfg.enable {
    # definitions
  };
}
```

This is a convention, not a rewrite mandate. Do not reshape a small valid module just to match the template.

### Options

Use `lib.mkEnableOption` for normal enable switches.

Use `lib.mkOption` for custom options, with:

* explicit `type`;
* a real `default` only when semantically intended;
* concise description;
* example only when helpful.

Do not:

* add options for values that are not meant to be externally configured;
* introduce a submodule for a single local group;
* rename existing options;
* weaken or broaden option types;
* remove defaults without proving they are redundant.

### Config definitions

Use direct assignments for deliberate final values.

Use `lib.mkDefault` only for defaults meant to be overridden elsewhere.

Do not introduce, remove, or reorder:

* `mkForce`;
* `mkOverride`;
* `mkBefore`;
* `mkAfter`;
* `mkOrder`;
* priority wrappers.

These are semantic tools, not simplification tools.

### Conditionals

Use `lib.mkIf cfg.enable { ... }` for configuration conditional on module options.

Do not write top-level `config = if config.foo.enable then { ... } else { ... };` when the condition depends on the configuration tree.

Do not make `imports` depend on `config`.

Prefer:

* import modules unconditionally;
* gate their behavior with options and `lib.mkIf`.

Use `lib.mkMerge` only when separate conditional/unconditional definition sets are clearer than one nested attrset.

### Imports

Nix `import` and module-system `imports` are different.

Do not:

* replace module `imports` with plain `import`;
* conditionally include module imports based on `config`;
* move imports across files only to shorten a parent file.

Extract or move modules only when the resulting boundary is clearer and all references/imports are updated.

### Submodules and structured options

Use `types.submodule`, `types.attrsOf`, `types.listOf`, or `types.nullOr` only when they model real user-facing structure.

A submodule is justified when:

* there are repeated structured instances;
* callers need validation for each instance;
* the abstraction is already part of the public module interface;
* it reduces future error risk.

A submodule is not justified when:

* there is only one local group;
* the structure is private implementation detail;
* it makes the code harder to search, edit, or review.

## Flakes, packages, overlays, and overrides

### Flakes

Do not edit `flake.lock`.

Do not change:

* input URLs;
* branches;
* commits;
* `follows`;
* systems;
* `nixosConfigurations`;
* `homeConfigurations`;
* formatter outputs;
* check outputs;
* devShell behavior;
* exported attribute names.

A simplification may clarify local expressions inside `flake.nix`, but must not change exported structure.

### Overlays

Do not change overlay ordering.

Do not move package definitions between overlays unless explicitly requested.

Do not replace an existing overlay pattern with a new framework.

Keep `final`/`prev` or `self`/`super` naming consistent with local style.

### Package expressions

Do not change:

* `pname`;
* `version`;
* `src`;
* hashes;
* patches;
* build inputs;
* native build inputs;
* build phases;
* install paths;
* passthru tests;
* `meta` semantics.

Good simplifications:

* remove unused private bindings;
* name repeated paths or flags;
* clarify a long phase only when behavior is identical;
* preserve existing override style.

### Overrides

Do not replace:

* `override`;
* `overrideAttrs`;
* overlays;
* module options;
* package arguments;

with another mechanism merely because it looks shorter.

Preserve the current abstraction boundary.

## Nesting and complexity

Reducing nesting is good only when it reduces total cognitive load.

Good de-nesting:

* remove pointless wrapper attrsets;
* inline a one-use binding whose name adds no meaning;
* extract a repeated long expression into a local name;
* split a deeply nested expression into meaningful local values;
* keep related NixOS options grouped by service/subsystem.

Bad de-nesting:

* replacing clear nested config with clever `map`, `mapAttrs`, `genAttrs`, `fold`, or helper functions;
* replacing module-system merging with ordinary attrset merging;
* introducing `lib.mkMerge` just to avoid indentation;
* using `//` to flatten config when recursive or module merging is needed;
* moving a small host-specific block to a separate file only to shorten the parent;
* extracting abstractions that make grep/search/navigation worse;
* splitting one coherent service config across distant files.

Prefer visible structure over hidden structure.

A nested block is acceptable when it mirrors:

* NixOS option hierarchy;
* service ownership;
* host-specific intent;
* security boundaries;
* boot/deployment order;
* upstream module documentation.

Do not flatten nesting mechanically. First ask: "Will the next maintainer understand this faster after the change?" If not, leave it nested.

## File and module structure

Keep code inline when it is:

* short;
* host-specific;
* used once;
* clearer near surrounding config;
* tightly coupled to adjacent settings.

Extract to a separate file only when:

* the block is large enough to hide the parent structure;
* the block is independently meaningful;
* the block is reused by multiple hosts/modules;
* the file name improves navigation;
* all imports/references can be updated safely.

Do not create helper libraries just to DRY two small occurrences.

Duplication is acceptable when it preserves local clarity.

## Attribute ordering and grouping

Preserve meaningful order.

Conventional order, when already present:

1. file header comments;
2. module arguments;
3. local `let` bindings;
4. `imports`;
5. `options`;
6. `config`;
7. assertions/warnings/meta, if local style uses them.

Within `config`, group related settings by service or subsystem.

Do not sort attributes mechanically when:

* comments define groups;
* order mirrors boot/service flow;
* order mirrors documentation;
* order affects generated lists;
* local style is intentionally grouped.

## Comments

Remove comments that:

* restate the code;
* describe removed behavior;
* are stale;
* are commented-out code;
* were temporary debugging notes.

Preserve comments that explain:

* hardware quirks;
* security rationale;
* deployment constraints;
* secrets handling;
* module-system edge cases;
* unusual priority/order choices;
* why a package is pinned or patched;
* upstream bugs/issues;
* why obvious-looking simplifications would be wrong.

Add a short comment only when a future maintainer would otherwise be likely to simplify the code incorrectly.

## Naming

You may improve private local names.

Prefer names that reveal role:

* `cfg`;
* `packages`;
* `settings`;
* `stateDir`;
* `dataDir`;
* `serviceUser`;
* `socketPath`;
* `configFile`;
* `extraConfig`.

Do not rename:

* public options;
* flake outputs;
* host names;
* imported file names;
* secrets;
* users/groups;
* package attrs used externally;
* names referenced outside the changed file.

When unsure whether a name is public, treat it as public.

## LLM-specific anti-patterns

Avoid these common bad edits:

1. Over-abstraction

   * creating helpers, files, libraries, or submodules before there is real complexity.

2. DRY at the cost of clarity

   * hiding two readable repeated blocks behind indirect code.

3. Complexity displacement

   * removing visible duplication/nesting by creating hidden indirection elsewhere.

4. Semantic compression

   * turning clear multi-line Nix into dense one-liners.

5. Scope hiding

   * adding broad `with`, implicit imports, or ambiguous `inherit`.

6. Module semantic drift

   * replacing `mkIf`, `mkMerge`, or option merging with ordinary attrset operations.

7. Priority drift

   * adding, removing, or moving `mkDefault`, `mkForce`, `mkOverride`, `mkBefore`, or `mkAfter`.

8. Interface drift

   * renaming options, outputs, attrs, files, hosts, or secrets.

9. Topology drift

   * moving imports, overlays, package definitions, or host config without a strong reason.

10. Comment damage

* removing rationale comments because they are not executable.

11. Formatting churn

* touching unrelated lines or files only to make style uniform.

12. Evaluation-risk edits

* changing laziness, recursion, attrset merging, path values, or flake inputs without proof.

13. Modular mirage

* splitting files or adding layers while reducing cohesion and making navigation harder.

14. Test avoidance

* making broad edits and only saying "looks good" without checking the diff.

## Preferred transformation patterns

### Remove an unused local binding

Good when the binding is truly unused in the file.

Do not remove a binding that may be referenced through:

* string interpolation;
* generated attribute names;
* `inherit`;
* module arguments;
* overlays;
* callPackage arguments;
* implicit package function parameters.

### Introduce a local name

Good when the expression is repeated or conceptually important.

Prefer naming repeated paths, users, package lists, command strings, or option namespaces when that improves local reading.

Do not introduce a local name if it separates a simple value from its only use.

### Inline a meaningless binding

Good when the binding is short, used once, and the name adds no domain meaning.

Do not inline a binding that documents intent.

### Clarify conditionals

Prefer module-aware conditionals for module config.

Good:

```nix
config = lib.mkIf cfg.enable {
  services.example.enable = true;
};
```

Risky when the condition depends on module config:

```nix
config = if cfg.enable then {
  services.example.enable = true;
} else {};
```

Native `if then else` is fine for local values that do not depend on the module configuration tree.

### Preserve clear duplication

Do not abstract repeated host config if each host needs local readability and may diverge.

Duplication is not automatically a smell in declarative system configuration.

## Verification

Always inspect the final diff.

Use the narrowest relevant check available.

Possible checks:

* `nixfmt` or `nixfmt-rfc-style` on changed Nix files;
* `treefmt` on changed files if configured;
* targeted `nix eval` for touched outputs/options when cheap;
* targeted `nix build .#<attr>` for changed packages;
* targeted Home Manager or NixOS build for changed host/module config if documented;
* `nix flake check` only when reasonable for the size of the change;
* markdown lint/check only if configured for instruction files.

Do not run expensive full-system checks for instruction-only edits unless the repo documents that as normal.

If a check is skipped, say why.

## Final summary format

When `/simplify` finishes, summarize:

* files changed;
* simplification categories applied;
* semantic areas intentionally left untouched;
* checks run;
* checks skipped and why;
* any Yellow candidate changed and why;
* any tempting candidate intentionally not changed because it was risky.

If no edits were made, say one of:

* changed files were already clear enough;
* potential simplifications were subjective;
* potential simplifications risked behavior changes.
