# Architecture

complyscope works the way an auditor does: gather **evidence**, judge each **control**
against that evidence, record what fails as a **risk**, and report the result.

## Data flow

```
  scope.yaml (authorised targets + organisation profile)
          │
          ▼
┌─────────────────────── COLLECTORS (evidence gathering) ──────────────────┐
│  redscope_adapter        questionnaire            policy_docs (AI)       │
│  (the ONLY module that   (answers for non-        (policy documents      │
│   imports redscope)       technical controls)      for gap analysis)     │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
                         Evidence  (one normalised model)
                                   │
   frameworks/**/*.yaml ───▶  MAPPING ENGINE
   (controls as data)              │
                                   ▼
            ControlResult: pass / fail / partial / not_assessed
            + references to the evidence behind the decision ──▶ compliance score
                                   │
                                   ▼
                         RISK REGISTER
              failed control → risk (likelihood × impact, owner, treatment plan)
                                   │
                                   ▼
                            Assessment  (single result object)
                     ┌─────────────┼──────────────┐
                     ▼             ▼              ▼
               HTML/PDF report  FastAPI +      JSON export
                               dashboard
```

## Package layout

| Path | Responsibility |
|---|---|
| `src/complyscope/cli.py` | Click CLI; always prints the authorised-use notice |
| `src/complyscope/models/` | Pydantic models: `Control`, `Evidence`, `ControlResult`, `Risk`, `Assessment` |
| `src/complyscope/controls/` | Load and validate framework YAML files |
| `src/complyscope/collectors/` | Evidence collectors behind a common interface |
| `src/complyscope/mapping/` | Decide control status from evidence; compute scores |
| `src/complyscope/risk/` | Risk scoring and register |
| `src/complyscope/reporting/` | HTML/PDF report rendering |
| `src/complyscope/ai/` | LLM-assisted policy gap analysis with cited rationale |
| `src/complyscope/api/` | FastAPI service for the dashboard |
| `src/complyscope/frameworks/` | Control catalogues as YAML data, shipped in the package ([ADR-0006](decisions/0006-ship-catalogues-inside-the-package.md)) |
| `examples/` | Fictional organisation data and sample reports |
| `docs/decisions/` | Architecture Decision Records |

Packages are added in the week they are built; this table is the target shape.

## Key principles

1. **Controls are data, not code.** See [ADR-0002](decisions/0002-controls-as-data.md).
2. **One door to redscope.** See [ADR-0003](decisions/0003-redscope-integration-via-adapter.md).
3. **Traceability.** Every control result links to the evidence that produced it.
4. **Missing evidence is not a pass.** A control with no evidence is `not_assessed`.
