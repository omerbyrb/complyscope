# ADR-0006: Ship framework catalogues inside the Python package

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

ADR-0002 and the first architecture sketch placed catalogues in a top-level `frameworks/`
directory. Files outside `src/complyscope/` are not part of the installed package, so
`pip install complyscope` would give users a tool with no controls to assess against.

## Decision

Catalogues live in `src/complyscope/frameworks/<framework>/` (layout from ADR-0005) and are
included in the wheel. `complyscope.controls.load_builtin_framework(id)` finds them by the
`id` declared in each `framework.yaml`, not by directory name.

Control files carry a numeric prefix (`1_firewalls.yaml` … `5_malware_protection.yaml`) so
the loader's alphabetical order matches the publisher's theme order.

Each catalogue records the exact source version and URL in `framework.yaml`; summaries are
written in our own words and point readers to the authoritative document.

## Consequences

- Installed and development copies behave the same (the wheel was checked to contain every
  catalogue file when this decision was made).
- Users can still load their own catalogue from any directory with `load_framework(path)`.
- Updating a framework version is a reviewable data change plus a package release.
