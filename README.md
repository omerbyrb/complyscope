# complyscope

[![CI](https://github.com/omerbyrb/complyscope/actions/workflows/ci.yml/badge.svg)](https://github.com/omerbyrb/complyscope/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Open-source compliance-as-code for small and medium-sized organisations.**

complyscope collects technical evidence automatically, maps it to security framework
controls, and turns the gaps into a scored risk register and a report that both a
director and an engineer can read.

> ⚠️ **Authorised use only.** complyscope runs active technical checks (via
> [redscope](https://github.com/omerbyrb/redscope)). Only run it against systems you own
> or have written permission to assess. Example targets and data in this repository are
> local or fictional.

> 🚧 **Status: early development (v0.1).** See the [roadmap](#roadmap) for what works today.

## Why

Small organisations pursuing **Cyber Essentials** or **ISO 27001** usually track compliance
in spreadsheets: evidence goes stale, nobody knows which finding affects which control,
and risks are scored inconsistently. complyscope treats controls as data, evidence as
machine-collected facts, and every compliance decision as traceable back to its evidence.

## How it works

```
scope.yaml ──▶ Collectors ──▶ Evidence ──▶ Mapping engine ──▶ Control results ──▶ Risk register ──▶ Report
              (redscope,                    (+ framework                (pass / fail /     (likelihood ×
              questionnaire,                 YAML files)                 partial /          impact)
              policy docs)                                               not assessed)
```

See [docs/architecture.md](docs/architecture.md) for the full design and
[docs/decisions/](docs/decisions/) for the reasoning behind key choices.

## Frameworks

| Framework | Status |
|---|---|
| Cyber Essentials (Requirements for IT Infrastructure v3.3) | ✅ Control catalogue (27 controls) · 🚧 evidence mapping |
| ISO/IEC 27001:2022 Annex A | Planned (week 7) |
| NIST CSF 2.0 | Planned (week 7) |

## Quick start (development)

```bash
git clone https://github.com/omerbyrb/complyscope.git
cd complyscope
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
complyscope --help
complyscope controls list --theme user_access_control
pytest
```

## Roadmap

| Week | Goal |
|---|---|
| 1 | Architecture, repo skeleton, Cyber Essentials control data model, CI |
| 2 | redscope integration and automated evidence collection |
| 3 | Finding → control mapping engine, compliance score |
| 4 | Risk register and scoring methodology |
| 5 | FastAPI + dashboard, questionnaire module |
| 6 | HTML/PDF report generation |
| 7 | ISO 27001 + NIST CSF mappings, AI-assisted policy gap analysis |
| 8 | Tests, Docker, MkDocs site, demo, v1.0 release |

Progress is tracked in [milestones](https://github.com/omerbyrb/complyscope/milestones).

## Licence

[MIT](LICENSE) © 2026 Abdullah Omer Bayirbasi
