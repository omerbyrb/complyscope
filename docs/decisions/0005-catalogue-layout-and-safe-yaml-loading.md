# ADR-0005: Catalogue file layout and safe YAML loading

- **Status:** Accepted
- **Date:** 2026-10-23

## Context

A framework catalogue can hold dozens of controls (ISO/IEC 27001:2022 Annex A has 93).
One large file is hard to review, and merge conflicts become likely. Catalogues may also
come from contributors, so loading one must never be able to run code.

## Decision

**Layout.** Each framework is a directory:

```
frameworks/<framework>/
    framework.yaml      # id, name, version, publisher, source_url, themes
    controls/*.yaml     # one file per theme, each with a top-level `controls` list
```

`framework.yaml` must not contain controls. Control files are read in alphabetical order,
so the catalogue order is deterministic.

**Safe parsing.** YAML is parsed only with `yaml.safe_load`, which builds plain data.
`yaml.load` with the default loader can construct arbitrary Python objects (for example via
`!!python/object/apply`), which turns a malicious catalogue into code execution. A test
checks that such tags are refused.

**Actionable errors.** Every load error raises `FrameworkLoadError` naming the file, and the
control id where there is one. A duplicate id names both files that define it.

## Consequences

- Reviewers see changes per theme in small diffs.
- Untrusted catalogues can be loaded without executing code.
- Cross-file checks (duplicate ids) happen in the loader; per-control and per-framework
  rules stay in the model (ADR-0004).
