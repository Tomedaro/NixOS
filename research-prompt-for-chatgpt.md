# @gotgenes/pi-permission-system Fork — External Directory Gate Research

## Context

I switched from the original `pi-permission-system@0.7.0` to `@gotgenes/pi-permission-system@10.7.1` (a community fork). The fork has a completely different config format — flat surfaces instead of nested `tools`/`bash`/`special` objects.

## Config format difference

**Old format (v0.7.0):**
```json
{
  "defaultPolicy": { "tools": "ask", "bash": "ask" },
  "tools": { "read": "allow" },
  "bash": { "cd *": "allow" },
  "special": { "external_directory": "ask" }
}
```

**New fork format (v10.7.1):**
```json
{
  "permission": {
    "*": "ask",
    "read": "allow",
    "write": "allow",
    "bash": { "cd *": "allow" },
    "external_directory": "ask"
  }
}
```

Every top-level key is a **surface name**. String values = `{ "*": action }`. Object values = pattern map. The universal `"*"` key is the fallback.

Relevant source: `normalizeFlatConfig()` in `src/normalize.ts` converts this to a Ruleset.

## The Problem

The fork has a **multi-gate architecture**:

1. **Bash surface gate** — matches `cd *` → `allow` ✅
2. **Bash external-directory gate** (`src/handlers/gates/bash-external-directory.ts`) — separately checks if any path in the bash command is outside CWD, and if so, checks the `external_directory` surface. Since `"external_directory": "ask"`, it prompts the user.

The two gates fire independently. Bash says allow, but external_directory says ask → user gets prompted.

Key code flow (`bash-external-directory.ts`):
```typescript
for (const p of externalPaths) {
  const check = resolver.resolve("external_directory", { path: p });
  if (check.state !== "allow") {
    uncoveredEntries.push({ path: p, check });
  }
}
```

And in `permission-manager.ts`, the `SPECIAL_PERMISSION_KEYS` set is:
```typescript
const SPECIAL_PERMISSION_KEYS = new Set(["external_directory", "path"]);
```

These surfaces are resolved by name directly.

## Current Config

```json
{
  "$schema": "https://raw.githubusercontent.com/gotgenes/pi-permission-system/main/schemas/permissions.schema.json",
  "permission": {
    "*": "ask",
    "read": "allow",
    "write": "allow",
    "edit": "allow",
    "grep": "allow",
    "find": "allow",
    "ls": "allow",
    "path": { "*": "allow" },
    "bash": {
      "*": "ask",
      "cd *": "allow",
      "pwd": "allow",
      "ls *": "allow",
      "find . *": "allow",
      "grep *": "allow",
      "rg *": "allow",
      "cat *": "allow",
      "sed -n *": "allow",
      "head *": "allow",
      "tail *": "allow",
      "wc *": "allow",
      "echo *": "allow",
      "git status --short": "allow",
      "git diff --stat": "allow",
      "git diff --check": "allow",
      "git branch --show-current": "allow",
      "nix eval --raw .#nixosConfigurations.Default.config.system.name": "allow",
      "cat ~/.ssh*": "deny",
      "cat ~/.gnupg*": "deny",
      "cat ~/.pi/agent/auth.json*": "deny",
      "grep -R . ~/.ssh*": "deny",
      "grep -R . ~/.gnupg*": "deny",
      "rg * ~/.ssh*": "deny",
      "rg * ~/.gnupg*": "deny",
      "rm -rf *": "deny",
      "git reset --hard*": "deny",
      "git clean -fd*": "deny",
      "curl *|*": "deny",
      "wget *|*": "deny",
      "pi install*": "deny",
      "pi remove*": "deny",
      "pi uninstall*": "deny",
      "pi config*": "ask",
      "pi update*": "ask"
    },
    "external_directory": "ask",
    "mcp": {
      "*": "ask",
      "mcp_status": "allow",
      "mcp_list": "allow",
      "mcp_search": "allow",
      "mcp_describe": "allow",
      "nixos*": "allow",
      "nixos:*": "allow"
    },
    "skills": { "*": "ask" }
  }
}
```

## Question

What is the best approach to allow `cd` (any argument) without prompting, while keeping the external_directory gate active as "ask" for potentially destructive commands?

**Options I see:**

1. **Set `"external_directory": "allow"`** — kills the gate entirely for all bash commands and path-bearing tools (read/write/edit). Too broad?
2. **Set `"external_directory": { "/tmp/*": "allow", "/home/daniil/*": "allow", "/nix/store/*": "allow", "*": "ask" }`** — per-path granularity, but requires maintaining a path allowlist. Also, the `cd` path isn't what triggers it — the extracted external paths from the bash command are checked. So `cd /tmp` extracts `/tmp`, checks `external_directory` surface with pattern `/tmp` — which would match `/tmp/*`? The wildcard pattern only matches `*` at the end according to the wildcard compiler.
3. **The old `PI_PERMISSION_SYSTEM_POLICY_AGENT_DIR` env var approach** — not supported by the fork at all (the fork reads from `extensions/pi-permission-system/config.json` only).
4. **Is there any way to express "allow external_directory for bash but not for other tools"?** — The surface is global, not tool-specific.

What tradeoffs am I missing? Is option 2 practical, or is option 1 the right call since bash rules already gate what commands can run?
