# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

complyscope makes design choices that a reviewer, contributor or auditor will later ask
about ("why YAML?", "why not copy redscope's code?"). Without a written record the
reasoning is lost and decisions get silently reversed.

## Decision

Record each significant decision as a short Architecture Decision Record in
`docs/decisions/`, numbered sequentially, using the sections: Context, Decision,
Consequences. ADRs are never edited after acceptance; a later ADR supersedes an earlier one.

## Consequences

- Design rationale is reviewable alongside the code, in the same pull requests.
- Small overhead per decision, which is acceptable for a project that values traceability
  (the same principle complyscope applies to compliance evidence).
