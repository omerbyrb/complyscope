# ADR-0007: Depend on redscope 2.0.0 (amends ADR-0003)

- **Status:** Accepted
- **Date:** 2026-10-29
- **Amends:** [ADR-0003](0003-redscope-integration-via-adapter.md), which planned the
  prerequisite redscope changes as release v1.1.0

## Context

ADR-0003 listed three redscope changes needed before integration: move the code into a
`redscope` package, fix the module registry, and add a stable `check_id` to findings. They
were delivered in omerbyrb/redscope#1 and omerbyrb/redscope#2.

Moving the code changes every import path (`core.*` becomes `redscope.core.*`), so
existing plugins and any code importing redscope break. Under semantic versioning a
backwards-incompatible change requires a new major version, not a minor one.

## Decision

- redscope is released as **v2.0.0** (tag `v2.0.0`), not v1.1.0.
- complyscope's optional `scan` extra pins redscope to that tag:
  `redscope @ git+https://github.com/omerbyrb/redscope@v2.0.0`.
- complyscope maps findings only by the check ids documented in redscope's
  [`docs/check-ids.md`](https://github.com/omerbyrb/redscope/blob/v2.0.0/docs/check-ids.md).
  Those ids are a stability promise: removing or redefining one is itself a breaking change
  for redscope.

## Consequences

- The version number tells redscope users that an upgrade needs code changes.
- Upgrading redscope in complyscope is a deliberate pin change, reviewed in a PR.
- A clean install of the tag was checked: version 2.0.0, all 26 modules load, the wordlists
  ship with the package and no top-level `core` package is installed.
