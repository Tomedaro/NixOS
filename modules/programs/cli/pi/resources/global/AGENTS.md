<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->

# Global Pi instructions for this NixOS system

This global profile is for general coding and NixOS work, not dedicated study.

## Pi setup routing

For any question about Pi itself, this NixOS module, the smart launcher, wrappers, settings, policies, packages, MCP, memory, study/work profiles, or runtime `.pi` state, read these first:

1. `/home/daniil/NixOS/modules/programs/cli/pi/docs/INDEX.md`
2. `/home/daniil/NixOS/modules/programs/cli/pi/docs/LOOKUP.json`

Do not start with broad `grep -R` across the whole NixOS repository for Pi setup questions unless the wiki routes are missing or insufficient.

For small Pi setup changes, use `docs/LOOKUP.json` to identify the narrowest route, read only those files, and stop. Do not inspect wrappers, scripts, package settings, policies, or profile resources unless the selected route points there or the request depends on them.

## NixOS rules

- This machine is managed declaratively with NixOS.
- Durable Pi setup changes belong under `/home/daniil/NixOS/modules/programs/cli/pi/**`.
- Runtime files under `~/.pi/agent/**`, `~/Learning/**`, and work project `.pi/**` are generated or user-owned depending on the ownership docs.
- Do not use `pi install`, `pi remove`, `pi uninstall`, or `pi config` for durable setup changes. Edit this Nix source tree, rebuild/test, then use `pi-admin sync` or the relevant compatibility sync command.
- `pi update` and `pi update --extensions` are intentional maintenance actions for pinned packages; explain what will change before running them.
- If `~/.pi/agent/LOCAL.md` exists, read it for private local preferences, but do not create or overwrite it from Nix.
- Never put API keys, tokens, passwords, private SSH material, or OAuth credentials into Nix files.
- Prefer small diffs and show `git diff --stat` plus relevant `git diff` before final recommendations.

## Language learning support

- At the start of every user-facing response, provide a corrected version of the user's latest natural-language message when it contains noticeable grammar, spelling, punctuation, or wording issues in **English** or **French**.
- Prefix it with `Corrected (en):` for English corrections and `Corrected (fr):` for French corrections, and keep it brief.
- Preserve the user's meaning, tone, technical terms, paths, commands, code, logs, diffs, JSON, Nix, shell snippets, stack traces, and quoted text.
- Do not rewrite messages that are mostly code, commands, logs, file contents, or terminal output.
- If the user's message is already natural in the language used, or if correction would add noise, omit the correction and continue normally.

## Token policy

- Keep always-loaded context small.
- Use the Pi setup wiki and lookup map before reading source files.
- Use prompts/skills for repeatable workflows instead of growing this file.
