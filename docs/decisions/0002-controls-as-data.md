# ADR-0002: Define controls as YAML data, not code

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

complyscope must support several frameworks (Cyber Essentials first, then ISO/IEC
27001:2022 Annex A and NIST CSF 2.0). Frameworks are revised over time, and the people best
placed to review a control definition are compliance practitioners, not necessarily Python
developers.

If each control were a Python class, adding or correcting a control would need a code
change, and reviewing a control catalogue would mean reading code.

## Decision

Each framework's controls live in YAML files under `frameworks/<framework>/`. A control
declares its identifier, title, theme, how it is assessed (`automated`, `questionnaire` or
`hybrid`), the evidence rules that decide its status, and a crosswalk to equivalent controls
in other frameworks.

YAML files are validated against a Pydantic schema at load time, so a malformed control
fails fast with a clear error instead of producing a wrong compliance result.

## Consequences

- New frameworks and framework revisions are data changes, reviewable in a diff.
- One piece of evidence can satisfy controls in several frameworks through the crosswalk.
- The evidence-rule vocabulary in YAML must stay small and well documented, otherwise YAML
  becomes a poorly designed programming language. Complex logic stays in the mapping engine.
- Framework text is summarised in our own words to respect the publishers' copyright.
