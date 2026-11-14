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

## Collecting evidence

Technical checks need the `scan` extra, which installs
[redscope](https://github.com/omerbyrb/redscope) v2.0.0:

```bash
pip install -e ".[scan]"
cp examples/scope.example.yaml scope.yaml   # then edit: organisation, authorisation, hosts
complyscope collect --scope scope.yaml --output evidence.json
```

`collect` refuses to run without a completed authorisation block, only touches hosts listed
in the scope, shows what it is about to do and asks for confirmation (`--yes` skips the
prompt). The result is an evidence file in which every check is recorded as `present` or
`absent`. Checks that could not run are listed as skipped and produce no evidence, so they
can never count as a pass. `scope.yaml` and `evidence*.json` are git-ignored because they
describe real systems.

## Assessing controls

```bash
complyscope assess --scope scope.yaml --evidence evidence.json
```

`assess` sends no network traffic. It judges each control as `pass`, `fail`, `partial` or
`not_assessed` and reports two separate figures: **compliance** (controls that pass) and
**coverage** (controls that could be assessed at all). Until the questionnaire module
exists, a clean scan cannot pass a Cyber Essentials control, and the figures are never a
certification.

## Managing risks

```bash
complyscope risks --scope scope.yaml --evidence evidence.json --register risks.yaml
```

Every failed control becomes a drafted risk in `risks.yaml`, scored with the
[risk methodology](docs/risk-methodology.md) (likelihood × impact, 5 × 5). complyscope
estimates likelihood from the evidence but leaves impact, owner, treatment and plan to a
person, and lists what each risk still needs. Edit `risks.yaml` freely: running the command
again refreshes only likelihood and evidence, adds new risks, reopens closed risks that fail
again, and points out risks whose controls no longer fail so their owner can close them.

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
