# Security Limitations

## Important

Policy-backed profiles are not OS sandboxes.

The historical `pi-readonly` symlink test showed that external-directory policy can fail when a tool checks the written path instead of the canonical resolved path.

Example failure pattern:

```text
project/secret-link/file.txt -> /home/daniil/.ssh/id_ed25519
```

A textual path check sees `project/secret-link/file.txt`. A correct security boundary must also check the resolved target.

## Current stance

- `pi` is a convenience launcher.
- `pi-readonly` and `PI_PROFILE=cautious pi` are cautious, policy-backed modes only.
- They are not safe for untrusted repositories.
- They should not be described as secure sandboxes.

## Future hardening

A real sandbox profile should use canonical path checks and/or OS-level isolation such as bubblewrap or an audited `pi-sandbox` integration.

Until that exists and passes symlink regression tests, do not rely on Pi profiles as a hard security boundary.
