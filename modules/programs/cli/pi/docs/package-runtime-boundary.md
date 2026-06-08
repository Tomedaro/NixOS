# Pi package and runtime boundary

## Core rule

Do not set `PI_PACKAGE_DIR` in the NixOS Pi wrappers.

`PI_PACKAGE_DIR` overrides the Pi runtime package directory. It is not the directory for user installed Pi extension packages.

If it points to `~/.pi/agent/npm`, Pi may try to load internal runtime assets from the npm cache and crash with paths like:

```text
~/.pi/agent/npm/dist/modes/interactive/theme/dark.json
```

## Correct model

* Pi itself comes from the Nix package and wrapper.
* User Pi packages install under `~/.pi/agent/npm`.
* Project Pi packages install under `.pi/npm`.
* Package versions are controlled by versioned specs in `settings.json`.
* npm behavior is controlled through `npmCommand`, normally `["pi-npm"]`.
* `pi-bootstrap`, `pi-study-init`, and `pi-work-init` sync source managed settings and resources.
* `pi-compat-check`, `pi-doctor`, and `pi-drift-check` validate the resulting runtime.

## Offline mode clarification

`PI_OFFLINE=1` disables Pi startup network operations such as update checks, package update checks, and telemetry.

It is not an operating system network sandbox. A profile can still call the model provider, and if shell or network tools are allowed, it may still reach the internet.

For real network isolation, add an OS level sandbox layer such as bubblewrap, systemd-run hardening, network namespace rules, or firewalling.
