# ADR-0008: Evidence records both presence and absence of an issue

- **Status:** Accepted
- **Date:** 2026-11-01

## Context

redscope reports a finding only when it detects a problem. If complyscope treated "no
finding" as "control passed", a module that crashed, timed out or never ran would make
controls look compliant. That is the most dangerous failure mode for a compliance tool:
a false assurance.

## Decision

Every piece of evidence is an explicit observation of one check on one target:

- `observed: present` means the check ran and found the issue. Severity is required.
- `observed: absent` means the check ran successfully and did not find the issue. Severity
  is not allowed.
- If a check did not run (error, timeout, out of scope), **no evidence is recorded**. The
  mapping engine then reports the related controls as `not_assessed`, never `pass`.

The redscope adapter creates `absent` evidence only for checks that a module can emit
(redscope's published check ids) and only when that module finished without errors.

An `EvidenceCollection` is the unit written to disk as JSON. It rejects a check recorded as
both present and absent on the same target, and it allows several `present` items for one
check (for example two deprecated TLS versions). Timestamps must be timezone-aware so
collections from different machines can be compared.

Only the `redscope` source exists for now. `source` is a discriminator field, so
questionnaire evidence (week 5) can be added without changing existing JSON files.

## Consequences

- "Absence of evidence" and "evidence of absence" are kept apart, in line with how auditors
  treat evidence.
- The adapter needs to know which check ids each redscope module can emit.
- Evidence JSON is stable, versioned by `complyscope_version`, and safe to archive as an
  audit trail.
