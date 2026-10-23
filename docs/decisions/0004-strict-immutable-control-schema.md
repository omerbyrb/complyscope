# ADR-0004: Validate controls with a strict, immutable schema

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Control YAML files are written by hand (ADR-0002). A compliance tool that silently accepts
a mistake produces a wrong compliance result, which is worse than no result: a typo such as
`asessment: automated` or an evidence rule pointing at the wrong source could make a
control look assessed when it is not.

## Decision

Model controls with Pydantic v2 and make the schema strict:

- **Unknown keys are rejected** (`extra="forbid"`), so typos fail at load time.
- **Evidence rules are a discriminated union on `source`.** A `redscope` rule must name a
  `check`; a `questionnaire` rule must name a `question`. Each source has exactly the fields
  it needs.
- **Evidence must match the assessment method.** An `automated` control cannot rely on
  questionnaire answers and a `questionnaire` control cannot rely on scans; `hybrid` allows
  both.
- **Framework-level checks** reject duplicate control ids and controls whose theme is not
  declared by the framework.
- **Models are immutable** (`frozen=True`). Controls are reference data; nothing in an
  assessment run should be able to change them.

A control with no evidence rules is allowed while a catalogue is being drafted. It can only
ever be reported as `not_assessed`.

## Consequences

- Catalogue errors surface immediately with the control id in the message.
- Adding a new evidence source means adding a new rule model, a deliberate code change.
- The same models give FastAPI request/response schemas for free in week 5.
