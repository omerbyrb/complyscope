# ADR-0010: How the redscope adapter turns scans into evidence

- **Status:** Accepted
- **Date:** 2026-11-02
- **Builds on:** ADR-0003 (adapter boundary), ADR-0008 (presence and absence), ADR-0009 (scope)

## Context

The adapter is the only code that imports redscope. It must turn redscope's
`ScanResult` objects into `Evidence` without ever producing false assurance, and it must
be testable without scanning anything.

## Decision

1. **Scope gate first.** `RedscopeCollector.collect(host)` calls `Scope.ensure_in_scope`
   before any module runs. A test asserts that no module is called for an out-of-scope host.
2. **Fixed module set for Cyber Essentials:** `portscan`, `serviceenum`, `banner`,
   `cvelookup`, `ssltls`, `headers`, in that order.
3. **Explicit chaining.** `cvelookup` needs service versions from `banner`. redscope 2.0.0
   does not pass them between modules, so the adapter does. If `banner` found nothing,
   `cvelookup` is skipped and produces no evidence.
4. **Absent evidence comes from a known check list.** `MODULE_CHECKS` lists every check id
   each module can emit. A module that finishes without errors yields `absent` evidence for
   each listed check it did not report. A module that crashes or reports errors yields
   nothing and is recorded under `skipped` with the reason.
5. **Drift check.** A test parses the installed redscope source and requires
   `MODULE_CHECKS` to match it exactly. CI installs the pinned `scan` extra, so upgrading
   redscope cannot silently change what "absent" means.
6. **Testable by design.** The redscope call is an injectable `runner`, and the clock is
   injectable. Unit tests use canned `ScanResult.to_dict()` payloads; redscope is imported
   lazily so complyscope works without the `scan` extra.

## Consequences

- An external scan can only ever give part of the evidence for a Cyber Essentials control.
  Each evidence rule says in a comment what the scan cannot see; the questionnaire
  (week 5) covers the rest.
- A first run against `localhost` produced 19 `absent` observations from three modules
  and skipped `ssltls`, `headers` (no HTTPS service) and `cvelookup` (no versions). The
  controls behind the skipped modules stay `not_assessed`, which is the intended behaviour.
- The redscope chaining gap is worth fixing upstream; until then the adapter owns it.
