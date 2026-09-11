# Browser ownership

## Current decision

The selected Zen Beta integration is intentionally system-owned. Its NixOS
choice module supplies both the Zen package and FirefoxPWA through the internal
`workstationInternal.browser.systemPackages` option, and wraps Zen with
FirefoxPWA as a native-messaging host. The host package aggregator appends that
typed list at the browser boundary, preserving the historical package order
without relying on cross-module list-definition order. This keeps browser
desktop metadata out of the Home Manager user profile.

Declarative browser profile adoption is a separate decision and remains
deferred. Home Manager does not currently own `~/.zen`, `~/.mozilla`,
`profiles.ini`, browser settings, bookmarks, search configuration, extensions,
or MIME defaults. Existing browser and PWA data remains mutable state.

| Boundary | Current owner | Support state |
| --- | --- | --- |
| Zen Beta package | selected browser NixOS module | supported |
| FirefoxPWA package and Zen native-messaging wrapper | selected browser NixOS module | supported |
| `BROWSER=zen-beta` | Daniil's Home Manager root, derived from the choice catalogue | supported |
| Zen and Mozilla profiles | user-managed mutable state | deferred from declarative adoption |
| MIME/default-application policy | existing runtime/user state | deliberately unchanged |
| Firefox and Floorp selection | unresolved package/profile integration | pending |

## Why package and profile ownership are separate

Zen's upstream flake supports installing its package through either
`environment.systemPackages` or `home.packages`. Its Home Manager module is a
larger ownership boundary: enabling it installs the browser package, and a
non-empty profile declaration writes `profiles.ini` and files inside the
profile tree.

Desktop entries and MIME associations also follow XDG precedence. User data is
searched before system data, and user `mimeapps.list` files override lower
levels. Moving an otherwise identical browser or FirefoxPWA package into the
Home Manager profile can therefore change which desktop file is considered the
default handler.

An isolated migration attempt demonstrated that exact package-derivation and
executable equality were insufficient: user-profile desktop/MIME metadata
changed the effective handler for `application/vnd.mozilla.xul+xml`. That move
was rejected. Package installation remains at the system level, where current
runtime behavior is already established.

## Persistent contract

- A supported browser choice must provide a system module and declare its
  package owner as `system`.
- Browser profile modules remain catalogue artifacts with
  `profileStatus = "deferred"`; host and user composition roots may not import
  them.
- Zen Beta and FirefoxPWA are declared by the Zen system module, then appended
  by the residual host package aggregator through the typed internal browser
  package option. Neither package is named in the residual list or Daniil's
  Home Manager package list.
- Zen is wrapped with the same `pkgs.firefoxpwa` native-messaging host.
- The browser selector continues to provide command metadata independently of
  mutable profile adoption.
- This boundary does not declare or rewrite MIME defaults and does not touch
  browser data.

The source boundary is enforced by the flake's workstation check, including the
typed aggregation channel. The choice catalogue validates the system package
owner, deferred profile status, profile reason, system module, and profile
constructor.

## Validation for this ownership move

The source move itself must preserve all evaluated behavior. Validation compares
the reference and candidate values for:

1. the ordered `environment.systemPackages` derivation list;
2. the ordered Daniil Home Manager package derivation list;
3. the selected `BROWSER` value;
4. the active NixOS/Home Manager logical fingerprint, normalizing only the
   content-identical flake source path; and
5. the Zen and FirefoxPWA package identities and multiplicities.

The normal flake checks and all supported variants are then evaluated, followed
by one candidate system build. No activation, browser launch, mutable profile
read, MIME rewrite, or PWA mutation is part of this source-only phase.

## Future declarative profile adoption

Profile adoption is optional work, not unfinished package ownership. If it is
attempted later, it requires its own explicit phase:

1. close all browser and FirefoxPWA processes;
2. make recoverable backups of the relevant profiles and user XDG association
   files;
3. record the current URL, HTML, XUL, and PWA desktop handlers;
4. decide and declare the intended MIME/default policy before changing profile
   placement;
5. test the Home Manager profile module against a disposable profile copy;
6. verify native messaging, installed PWAs, profile selection, extensions,
   bookmarks, and effective default handlers; and
7. activate only through the guarded migration/rollback workflow.

Until that contract exists, importing a browser `profileModule` into a real user
is a regression.

## Host implications

`Singularity` is complete as the repository's current real host: it selects a
browser system module just as it selects system sides for desktops, terminals,
editors, and hardware. A future host can reuse the supported Zen package and
native-messaging integration through the catalogue, but its browser profiles,
installed PWAs, credentials, and default-application state are not provisioned
by this repository. Those remain explicit restore or adoption work.
