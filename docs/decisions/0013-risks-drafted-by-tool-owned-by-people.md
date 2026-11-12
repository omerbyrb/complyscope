# ADR-0013: complyscope drafts risks; people own them

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

A failed control is not yet a risk decision. Likelihood can be estimated from technical
evidence, but impact depends on what a system means to the business, and only a person
with authority can choose a treatment or accept a risk. ISO/IEC 27001:2022 clause 6.1.2
requires each risk to have an owner.

## Decision

- The methodology lives in [`docs/risk-methodology.md`](../risk-methodology.md): 5 × 5
  likelihood × impact, four levels with review periods, a default risk appetite, and four
  treatments. The code holds the same tables, and a test fails if the document and the code
  disagree.
- complyscope drafts **one risk per failed control**, with a stable id (`R-<control id>`)
  so later runs can match it to an existing register entry.
- **Likelihood** is drafted from the worst finding's severity (critical 5 … info 1).
- **Impact** is drafted as 3 and marked unconfirmed. **Owner** is empty, **treatment**
  defaults to mitigate and the **plan** is empty.
- `Risk.needs_attention()` lists what is missing: no owner, impact not confirmed, no plan,
  or acceptance above the risk appetite. A drafted risk always needs attention.
- Score and level are derived properties, never stored, so they cannot drift from
  likelihood and impact.

## Consequences

- The tool never pretends to know business impact or to make acceptance decisions.
- Risk levels on a fresh draft are provisional until the owner confirms the impact.
- `partial` and `not_assessed` controls do not become risks. They are assessment gaps, and
  they are reported as such.
