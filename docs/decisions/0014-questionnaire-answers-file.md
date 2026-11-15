# ADR-0014: Questionnaire answers live in their own file

- **Status:** Accepted
- **Date:** 2026-11-15
- **Amends:** [ADR-0008](0008-evidence-records-presence-and-absence.md), which planned to
  store questionnaire evidence inside the evidence collection; and
  [ADR-0012](0012-control-status-and-score.md), whose rule "a clean hybrid control is only
  partial" now applies only to hybrid controls without a question

## Context

20 of the 27 Cyber Essentials controls cannot be observed by an external scan, and the
other 7 can be observed only in part. The rest of the evidence has to come from the
organisation itself: its policies, settings and processes.

`evidence.json` is written by a machine run and is best kept unchanged as a record of that
run. Questionnaire answers are different. People write them, revise them over weeks, and
they apply to the organisation rather than to a single host.

## Decision

- Every control has at least one yes/no **question** in the catalogue's `questions.yaml`.
  "Yes" means the requirement is met. Hybrid controls keep their scan rules as well.
- Answers live in **`answers.yaml`**, edited by people and git-ignored for real
  organisations. Each answer records the answer, who gave it and when.
- `not_applicable` is allowed only where the question permits it (for example, "where an
  admin interface is reachable…"), and it requires a written justification.
- An unquoted YAML `yes`/`no`, which YAML 1.1 reads as a boolean, is accepted and converted.
- The engine treats a "no" as a failure and a missing answer as no evidence. A hybrid
  control passes only when the scan is clean on every host **and** the answer is "yes".
- Risks drafted from a "no" record who answered and when. Their likelihood is drafted as 3
  because there is no finding severity to start from.

## Consequences

- Full coverage is now possible: the example answers with a clean scan give 25 of 27
  controls passing and 100% coverage.
- A self-declared "yes" is weaker evidence than an observation. Answers stay attributable,
  so a reviewer can ask for supporting documents, as a Cyber Essentials assessor would.
- `evidence.json` stays a pure, machine-generated record of what was observed.
