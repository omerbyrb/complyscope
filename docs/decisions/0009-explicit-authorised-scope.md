# ADR-0009: Technical checks run only against an explicit, authorised scope

- **Status:** Accepted
- **Date:** 2026-11-01

## Context

complyscope drives redscope, which sends real network traffic. Scanning a system without
permission can be unlawful (in the UK, the Computer Misuse Act 1990) and harms the people
who run it. A compliance tool should also mirror real audit practice, where scope and
authority to test are agreed in writing before fieldwork starts.

## Decision

Every collection run reads a `scope.yaml` with three parts:

1. **organisation**: whose systems are being assessed.
2. **authorisation**: `confirmed: true`, who confirmed it, when (not a future date), and an
   optional reference such as an engagement letter. Loading fails without it.
3. **targets**: an explicit list of single hosts (hostname or IP address).

Collectors must call `Scope.ensure_in_scope(host)` before touching a host. Anything not
listed exactly is refused.

The scope deliberately does **not** accept URLs, ports, CIDR ranges or wildcards. Each of
these can silently widen what is tested: `*.example.com` matches hosts nobody listed, and a
`/16` range covers 65,536 addresses. Hosts are normalised (case, trailing dot, IPv6
compression) so that equivalent spellings neither bypass the check nor create duplicates.
A subdomain of an in-scope host is out of scope unless it is listed itself.

Real scope files name client systems, so `/scope.yaml` is git-ignored and only
`examples/scope.example.yaml` (fictional organisation, reserved `.test` names, localhost)
is tracked.

## Consequences

- Assessing many hosts means listing each one. That is intentional friction for an SME tool.
- The authorisation record travels with the assessment and can appear in the report.
- `confirmed: true` is a declaration, not proof. complyscope records it but cannot verify
  it; responsibility stays with the user, as the README's authorised-use notice states.
