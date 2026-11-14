import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from complyscope.models import (
    ControlResult,
    ControlStatus,
    Evidence,
    Framework,
    Risk,
    RiskLevel,
    Treatment,
)
from complyscope.risk import (
    LEVEL_BANDS,
    LIKELIHOOD_FROM_SEVERITY,
    REVIEW_DAYS,
    draft_risks,
    risk_level,
)

DOC = Path(__file__).resolve().parents[1] / "docs" / "risk-methodology.md"
TODAY = date(2026, 11, 12)
WHEN = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)


def make_risk(**overrides):
    data = {
        "id": "R-CE-FW-01",
        "framework": "cyber-essentials",
        "control_ids": ["CE-FW-01"],
        "title": "Control not met: firewall",
        "likelihood": 4,
        "impact": 3,
        "impact_confirmed": True,
        "owner": "Jane Doe (fictional)",
        "treatment": "mitigate",
        "plan": "Close port 23 on the boundary firewall",
        "raised_on": TODAY,
        "review_by": date(2026, 12, 12),
    }
    data.update(overrides)
    return Risk.model_validate(data)


# --- Methodology -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score, level",
    [(1, "low"), (3, "low"), (4, "medium"), (6, "medium"), (8, "high"), (12, "high")]
    + [(15, "critical"), (25, "critical")],
)
def test_risk_level_bands(score, level):
    assert risk_level(score) is RiskLevel(level)


def test_every_possible_score_has_a_level():
    scores = {likelihood * impact for likelihood in range(1, 6) for impact in range(1, 6)}

    assert {risk_level(s) for s in scores} == set(RiskLevel)


def test_impossible_score_is_rejected():
    with pytest.raises(ValueError, match="not a possible"):
        risk_level(7)


def test_methodology_document_matches_the_code():
    text = DOC.read_text()

    for level, (low, high) in LEVEL_BANDS.items():
        row = rf"\| {level.value.capitalize()} \| {low}–{high} \| {REVIEW_DAYS[level]} days \|"
        assert re.search(row, text), f"docs disagree with code for {level.value}"
    for severity, likelihood in LIKELIHOOD_FROM_SEVERITY.items():
        assert f"| {severity.value} | {likelihood} |" in text


# --- Risk model --------------------------------------------------------------------------


def test_score_and_level_follow_likelihood_and_impact():
    risk = make_risk(likelihood=5, impact=4)

    assert (risk.score, risk.level) == (20, RiskLevel.CRITICAL)


@pytest.mark.parametrize("field", ["likelihood", "impact"])
@pytest.mark.parametrize("value", [0, 6])
def test_scales_run_from_one_to_five(field, value):
    with pytest.raises(ValidationError):
        make_risk(**{field: value})


def test_review_date_cannot_be_before_the_risk_was_raised():
    with pytest.raises(ValidationError, match="review_by"):
        make_risk(review_by=date(2026, 11, 1))


def test_complete_risk_needs_no_attention():
    assert make_risk().needs_attention() == []


def test_incomplete_risk_lists_what_the_owner_must_do():
    risk = make_risk(owner=None, impact_confirmed=False, plan="")

    assert risk.needs_attention() == ["no risk owner", "impact not confirmed", "no treatment plan"]


def test_accepting_a_risk_above_appetite_is_flagged():
    high = make_risk(treatment="accept", likelihood=4, impact=3)
    medium = make_risk(treatment="accept", likelihood=2, impact=3)

    assert "accepted above the risk appetite" in high.needs_attention()
    assert medium.needs_attention() == []


# --- Drafting from failed controls ---------------------------------------------------------


def evidence(check, target, severity):
    return Evidence(
        source="redscope",
        check=check,
        target=target,
        observed="present",
        severity=severity,
        title="A finding",
        collected_at=WHEN,
        collector="redscope 2.0.0",
    )


def framework():
    def control(control_id, title):
        return {
            "id": control_id,
            "theme": "t",
            "title": title,
            "assessment": "automated",
            "evidence": [{"source": "redscope", "check": "x.y"}],
        }

    return Framework.model_validate(
        {
            "id": "mini",
            "name": "Mini",
            "version": "1",
            "publisher": "tests",
            "source_url": "https://example.org",
            "themes": ["t"],
            "controls": [control("C-1", "First control"), control("C-2", "Second control")],
        }
    )


def result(control_id, status, *items):
    return ControlResult(
        control_id=control_id, status=status, rationale="because", evidence=tuple(items)
    )


def test_only_failed_controls_become_risks():
    results = (
        result("C-1", ControlStatus.FAIL, evidence("x.y", "a.example.test", "high")),
        result("C-2", ControlStatus.PARTIAL),
    )

    risks = draft_risks(framework(), results, today=TODAY)

    assert [r.id for r in risks] == ["R-C-1"]
    assert risks[0].control_ids == ("C-1",)
    assert risks[0].framework == "mini"
    assert risks[0].title == "Control not met: First control"


def test_draft_likelihood_comes_from_the_worst_finding():
    failing = result(
        "C-1",
        ControlStatus.FAIL,
        evidence("x.y", "a.example.test", "medium"),
        evidence("x.y", "b.example.test", "critical"),
    )

    (risk,) = draft_risks(framework(), (failing,), today=TODAY)

    assert risk.likelihood == 5
    assert risk.evidence_summary == (
        "x.y on a.example.test (medium)",
        "x.y on b.example.test (critical)",
    )


def test_draft_leaves_business_decisions_to_the_owner():
    failing = result("C-1", ControlStatus.FAIL, evidence("x.y", "a.example.test", "high"))

    (risk,) = draft_risks(framework(), (failing,), today=TODAY)

    assert (risk.impact, risk.impact_confirmed) == (3, False)
    assert risk.owner is None
    assert risk.treatment is Treatment.MITIGATE
    assert risk.needs_attention() == ["no risk owner", "impact not confirmed", "no treatment plan"]


@pytest.mark.parametrize("severity, days", [("critical", 14), ("high", 30), ("low", 90)])
def test_draft_review_date_follows_the_level(severity, days):
    failing = result("C-1", ControlStatus.FAIL, evidence("x.y", "a.example.test", severity))

    (risk,) = draft_risks(framework(), (failing,), today=TODAY)

    assert (risk.review_by - TODAY).days == days
