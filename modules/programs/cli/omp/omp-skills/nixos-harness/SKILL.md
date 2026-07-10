---
name: nixos-harness
description: Use when modifying Daniil's NixOS, Home Manager, Hyprland, tmux, Neovim, or AI-agent harness.
---

Rules:
- Prefer declarative Nix/Home Manager changes over imperative installs.
- Inspect the flake and module structure before editing.
- Never put API keys, OAuth tokens, or private credentials into Nix-tracked files.
- Before finalizing, show the diff and explain rollback.
- Prefer small commits with one clear purpose.
- Run formatting and relevant Nix checks when possible.
