# ADR-0012: How control status and the compliance score are decided

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

The mapping engine turns evidence into a verdict per control. Most Cyber Essentials
controls cannot be fully judged by an external scan, and hosts can produce no evidence at
all (ADR-0011). The verdict and the headline number must not overstate what is known.

## Decision

Each technical rule is evaluated on every in-scope host. The host list is passed in
explicitly, because a host with no evidence would otherwise vanish from the calculation.

| Situation | Status |
|---|---|
| Any rule fails on any host | `fail` |
| No evidence for any rule on any host, or no technical rules | `not_assessed` |
| Some rule and host combinations have no evidence | `partial` |
| All clean, but the control also needs the questionnaire (`hybrid`) | `partial` |
| All clean on every host, `automated` control | `pass` |

A failure always wins over missing evidence: a known problem is not hidden by gaps
elsewhere. Every result carries a rationale and the evidence behind it.

The score is two separate numbers, both out of all controls:

- **Compliance:** the share of controls with status `pass`. `partial` earns no credit.
- **Coverage:** the share of controls with any status other than `not_assessed`.

## Consequences

- Until the questionnaire exists (week 5), no Cyber Essentials control can pass: a fully
  clean scan gives 0% compliance and 25.9% coverage (7 of 27 controls). That is accurate.
- Cyber Essentials certification is all-or-nothing, so the percentage is a progress
  measure and never a claim of certification.
- `portscan.risky_service_exposed` also fires for exposed databases, so CE-FW-03 (admin
  interfaces) can fail for a service that is not an admin interface. Narrowing this needs
  a finer check id from redscope.
