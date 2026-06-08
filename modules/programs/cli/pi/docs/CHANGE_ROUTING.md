# Change Routing

Use this before changing the Pi setup.

## I want the simple daily command

Use:

```bash
pi
```

For maintenance, use:

```bash
pi-admin status
pi-admin sync
pi-admin drift
pi-admin compat
```

## I want to change global behavior, response style, or English correction

Edit:

- `resources/global/AGENTS.md`

Use this for rules that should apply across normal Pi profiles, such as answer style, setup-routing behavior, or English-learning correction.

Keep this file small because it is always-loaded context. Prefer prompts or skills for workflows that do not need to be active in every response.

Then run:

```bash
sudo nixos-rebuild test --flake /home/daniil/NixOS#Default
pi-admin sync global
pi-admin drift
```

## I want to change global model/provider/thinking/theme/packages

For pinned package versions, read `docs/PACKAGE_UPDATES.md` first.

Edit:

- `settings/global.json`
- `settings/deepseek-provider.json` for DeepSeek model metadata

Then run:

```bash
sudo nixos-rebuild test --flake /home/daniil/NixOS#Default
pi-admin sync global
pi-admin compat
pi-admin drift
```

## I want to change a permission policy

Edit:

- `policies/safe.jsonc`
- `policies/nixos.jsonc`
- `policies/study.jsonc`
- `policies/work.jsonc`
- `policies/research.jsonc`
- `policies/trusted.jsonc`

Then run:

```bash
sudo nixos-rebuild test --flake /home/daniil/NixOS#Default
pi-admin sync global
pi-admin drift
```

## I want to add a study instruction, prompt, or skill

Edit managed files under:

```text
resources/study/managed/
```

Then run:

```bash
pi-admin sync study
pi-admin drift
```

## I want to add a work instruction, prompt, or skill

Edit managed files under:

```text
resources/work/managed/
```

Then run with the target project explicit:

```bash
PI_WORK_DIR=/path/to/project pi-admin sync work
PI_WORK_DIR=/path/to/project pi-admin drift
```

## I want Pi to understand this setup better

Edit:

- `docs/INDEX.md`
- `docs/LOOKUP.json`
- specific topic docs
- `resources/nixos/AGENTS.md`
- `resources/nixos/prompts/`
- `resources/nixos/skills/`

`pi` inside `/home/daniil/NixOS` loads the NixOS setup prompt templates and self-maintenance skill.

## I want to install or remove a Pi extension/package

Do not make durable changes with `pi install`, `pi remove`, `pi uninstall`, or `pi config`. Edit `settings/global.json` or the relevant overlay/resource tree, then run the sync commands from this document.
