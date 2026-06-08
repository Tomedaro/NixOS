# Conversation and Memory

This setup uses two memory layers:

- Reviewed Markdown memory for stable source of truth.
- Automatic conversation memory from pi-hermes-memory, when the pinned extension is installed.

## Reviewed memory files

- Global personal interaction memory: `~/.pi/agent/MEMORY.md`.
- Study memory: `~/Learning/MEMORY.md` and the `~/Learning/vault/` graph.
- NixOS setup truth: `/home/daniil/NixOS/modules/programs/cli/pi/docs/` and the Nix source files.
- Work project truth: the project `AGENTS.md`, docs, and code.

## Automatic Hermes memory

pi-hermes-memory is private soft recall, not durable source of truth.

Use it to recognize preferences, repeated confusions, long arcs, and interaction style.
Do not use it to replace project files, the setup wiki, or reviewed Markdown memory.

## Consolidation rule

When a memory seems durable, useful, and not sensitive, propose adding it to the
appropriate reviewed Markdown memory file. Do not silently promote automatic memory
into durable memory.
