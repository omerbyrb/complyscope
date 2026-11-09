# ADR-0011: No absent evidence from a host that showed no open ports

- **Status:** Accepted
- **Date:** 2026-11-08
- **Amends:** [ADR-0010](0010-redscope-adapter-design.md), which described 19 `absent`
  observations from a host with no open ports as intended behaviour

## Context

ADR-0008 says a check that did not really run must produce no evidence. redscope 2.0.0
does not let the adapter tell those cases apart at host level: `portscan` treats a timeout
and a refused connection alike as "port closed" and reports no error, and `serviceenum` and
`banner` silently pass over closed ports.

A host that is down or fully filtered therefore looked identical to a clean one. It would
have produced `absent` evidence for every check, and controls such as "no unsupported
software" would have passed without any service having been seen. That is the false
assurance ADR-0008 exists to prevent.

## Decision

- `portscan` is the reachability gate. If it crashes, reports errors or sees no open ports,
  the adapter records no evidence for that host and sends it no further traffic. Every
  remaining module is listed under `skipped` with the reason.
- If `banner` identifies no services, its `absent` results are dropped, because "no
  end-of-life software" says nothing when no software was identified. Real `present`
  findings are kept.

## Consequences

- A host that genuinely has every scanned port closed is reported as not assessed. We accept
  this: the error goes in the safe direction, and the skipped reason tells the user why.
- A host with open ports can still have individual ports filtered, so `absent` for one
  service means "not seen on a reachable host", not proof that it is not running.
- A more precise fix would be for redscope to distinguish refused from timed-out
  connections. That needs a new redscope release and can follow later.
