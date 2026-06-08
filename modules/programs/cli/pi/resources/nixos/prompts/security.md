---
description: Explain Pi profile safety, cautious mode limitations, and sandbox boundaries
argument-hint: "[question]"
---
<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->

Explain Pi setup security for: $ARGUMENTS

Read:
- `modules/programs/cli/pi/docs/SECURITY.md`
- `modules/programs/cli/pi/docs/SECURITY_LIMITATIONS.md`
- `modules/programs/cli/pi/docs/PROFILES.md`

Be explicit: policy-backed cautious mode is not a security sandbox, and the historical symlink escape means real isolation requires canonical path checks and/or OS-level sandboxing.
