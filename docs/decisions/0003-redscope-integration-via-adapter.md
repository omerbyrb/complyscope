# ADR-0003: Integrate redscope as a pinned library behind an adapter

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

[redscope](https://github.com/omerbyrb/redscope) already performs the technical checks
complyscope needs as evidence (TLS, email authentication, HTTP headers, exposed services,
CVEs). Each redscope module returns a `ScanResult` containing `Finding` objects.

Options considered:

1. **Copy redscope's code into complyscope.** Fast to start, but two copies drift apart and
   fixes must be made twice.
2. **Call the redscope CLI and parse its output.** Loose coupling, but brittle text/JSON
   parsing and no type safety.
3. **Depend on redscope as a library and isolate it behind an adapter.**

Reviewing redscope v1.0.0 surfaced three blockers for option 3:

- Its code lives in top-level packages named `core` and `modules`, which would collide with
  other installed packages.
- The module registry in `core/plugin_loader.py` lists only 11 of the 24 modules, so
  `ssltls` and `emailsec` cannot be loaded by name.
- `Finding` has no stable identifier, only a human-readable title and free-form tags, so
  mapping on titles would break whenever wording changes.

## Decision

Choose option 3:

- Before integration, release **redscope v1.1.0**: move code into a `redscope` package,
  fix the module registry, and add a stable `check_id` (e.g. `tls.weak_protocol`) to
  `Finding`.
- complyscope depends on redscope pinned to a release tag, as an optional extra
  (`pip install complyscope[scan]`), so the rest of the tool works without scanning
  dependencies.
- Only `collectors/redscope_adapter.py` imports redscope. It converts redscope findings
  into complyscope's own `Evidence` model.

## Consequences

- redscope changes affect a single file in complyscope.
- Control YAML references redscope `check_id`s, never titles.
- complyscope's tests can use fake `Evidence` without running live scans.
- The redscope refactor is extra work in week 2, but it improves redscope itself.
