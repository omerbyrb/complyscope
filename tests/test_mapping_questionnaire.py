"""The mapping engine with questionnaire answers alongside technical evidence."""

from datetime import UTC, date, datetime

import pytest

from complyscope.mapping.engine import evaluate
from complyscope.models import (
    Answer,
    AnswerSheet,
    ControlStatus,
    Evidence,
    EvidenceCollection,
    Framework,
)
from complyscope.risk import draft_risks

WHEN = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
HOST = "a.example.test"


def framework():
    return Framework.model_validate(
        {
            "id": "mini",
            "name": "Mini",
            "version": "1",
            "publisher": "tests",
            "source_url": "https://example.org",
            "themes": ["t"],
            "controls": [
                {
                    "id": "Q-ONLY",
                    "theme": "t",
                    "title": "Questionnaire control",
                    "assessment": "questionnaire",
                    "evidence": [{"source": "questionnaire", "question": "Q1"}],
                },
                {
                    "id": "HYBRID",
                    "theme": "t",
                    "title": "Hybrid control",
                    "assessment": "hybrid",
                    "evidence": [
                        {"source": "redscope", "check": "x.y"},
                        {"source": "questionnaire", "question": "Q2"},
                    ],
                },
            ],
            "questions": [
                {"id": "Q1", "text": "First?", "allow_not_applicable": True},
                {"id": "Q2", "text": "Second?"},
            ],
        }
    )


def answers(**given):
    return AnswerSheet(
        organisation="Acme Ltd (fictional)",
        framework="mini",
        answers=tuple(
            Answer(
                question=question,
                answer=value,
                answered_by="Jane Doe (fictional)",
                answered_on=date(2026, 11, 15),
                note="Explained" if value == "not_applicable" else "",
            )
            for question, value in given.items()
        ),
    )


def scan(observed="absent"):
    return EvidenceCollection(
        organisation="Acme Ltd (fictional)",
        complyscope_version="0.1.0",
        created_at=WHEN,
        items=(
            Evidence(
                source="redscope",
                check="x.y",
                target=HOST,
                observed=observed,
                severity="high" if observed == "present" else None,
                collected_at=WHEN,
                collector="redscope 2.0.0",
            ),
        ),
    )


def statuses(collection, sheet=None):
    return {r.control_id: r for r in evaluate(framework(), collection, (HOST,), sheet)}


@pytest.mark.parametrize(
    "answer, expected",
    [("yes", "pass"), ("no", "fail"), ("not_applicable", "pass")],
)
def test_questionnaire_control_follows_its_answer(answer, expected):
    result = statuses(scan(), answers(Q1=answer))["Q-ONLY"]

    assert result.status is ControlStatus(expected)
    assert [a.question for a in result.answers] == ["Q1"]


def test_unanswered_question_leaves_the_control_not_assessed():
    assert statuses(scan(), answers())["Q-ONLY"].status is ControlStatus.NOT_ASSESSED


def test_no_answer_sheet_at_all_is_the_same_as_unanswered():
    assert statuses(scan())["Q-ONLY"].status is ControlStatus.NOT_ASSESSED


def test_hybrid_passes_only_with_a_clean_scan_and_a_yes():
    assert statuses(scan(), answers(Q2="yes"))["HYBRID"].status is ControlStatus.PASS


def test_hybrid_with_clean_scan_but_no_answer_stays_partial():
    assert statuses(scan(), answers())["HYBRID"].status is ControlStatus.PARTIAL


def test_hybrid_fails_on_a_no_even_with_a_clean_scan():
    result = statuses(scan(), answers(Q2="no"))["HYBRID"]

    assert result.status is ControlStatus.FAIL
    assert "Q2 answered no" in result.rationale


def test_hybrid_fails_on_the_scan_even_with_a_yes():
    result = statuses(scan("present"), answers(Q2="yes"))["HYBRID"]

    assert result.status is ControlStatus.FAIL
    assert f"x.y on {HOST}" in result.rationale


def test_risk_drafted_from_a_no_names_the_answer():
    results = evaluate(framework(), scan(), (HOST,), answers(Q1="no"))

    (risk,) = draft_risks(framework(), results, today=date(2026, 11, 15))

    assert risk.id == "R-Q-ONLY"
    assert risk.likelihood == 3
    assert risk.evidence_summary == ("Q1 answered no by Jane Doe (fictional) on 2026-11-15",)
