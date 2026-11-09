from datetime import UTC, datetime

import pytest

from complyscope.controls import load_builtin_framework
from complyscope.mapping.engine import evaluate, score
from complyscope.models import ControlStatus, Evidence, EvidenceCollection, Framework

WHEN = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)
HOSTS = ("a.example.test", "b.example.test")


def seen(check, target, observed):
    return Evidence(
        source="redscope",
        check=check,
        target=target,
        observed=observed,
        severity="high" if observed == "present" else None,
        title="A finding" if observed == "present" else "",
        collected_at=WHEN,
        collector="redscope 2.0.0",
    )


def collection(*items):
    return EvidenceCollection(
        organisation="Acme Ltd (fictional)",
        complyscope_version="0.1.0",
        created_at=WHEN,
        items=items,
    )


def control(control_id, assessment, *checks):
    return {
        "id": control_id,
        "theme": "t",
        "title": control_id,
        "assessment": assessment,
        "evidence": [{"source": "redscope", "check": c} for c in checks],
    }


def framework(*controls):
    return Framework.model_validate(
        {
            "id": "mini",
            "name": "Mini",
            "version": "1",
            "publisher": "tests",
            "source_url": "https://example.org",
            "themes": ["t"],
            "controls": controls,
        }
    )


def status_of(ctrl, *items, hosts=HOSTS):
    return evaluate(framework(ctrl), collection(*items), hosts)[0]


def clean(check="x.y", hosts=HOSTS):
    return [seen(check, host, "absent") for host in hosts]


def test_automated_control_passes_only_when_clean_on_every_host():
    assert status_of(control("C1", "automated", "x.y"), *clean()).status is ControlStatus.PASS


def test_any_failure_on_any_host_fails_the_control_and_names_it():
    result = status_of(
        control("C1", "automated", "x.y"),
        seen("x.y", HOSTS[0], "absent"),
        seen("x.y", HOSTS[1], "present"),
    )

    assert result.status is ControlStatus.FAIL
    assert "x.y on b.example.test" in result.rationale


def test_host_without_evidence_prevents_a_pass():
    result = status_of(control("C1", "automated", "x.y"), seen("x.y", HOSTS[0], "absent"))

    assert result.status is ControlStatus.PARTIAL
    assert "1 of 2" in result.rationale


def test_failure_beats_missing_evidence():
    result = status_of(control("C1", "automated", "x.y"), seen("x.y", HOSTS[0], "present"))

    assert result.status is ControlStatus.FAIL


def test_no_evidence_at_all_is_not_assessed():
    assert status_of(control("C1", "automated", "x.y")).status is ControlStatus.NOT_ASSESSED


def test_clean_hybrid_control_is_only_partial():
    result = status_of(control("C1", "hybrid", "x.y"), *clean())

    assert result.status is ControlStatus.PARTIAL
    assert "questionnaire" in result.rationale


def test_failing_hybrid_control_fails():
    result = status_of(control("C1", "hybrid", "x.y"), *[seen("x.y", h, "present") for h in HOSTS])

    assert result.status is ControlStatus.FAIL


def test_control_without_technical_rules_is_not_assessed():
    assert status_of(control("C1", "questionnaire")).status is ControlStatus.NOT_ASSESSED


def test_result_keeps_the_evidence_behind_the_decision():
    items = clean() + clean("other.check")

    result = status_of(control("C1", "automated", "x.y"), *items)

    assert {e.check for e in result.evidence} == {"x.y"}
    assert len(result.evidence) == 2


def test_evaluate_needs_at_least_one_host():
    with pytest.raises(ValueError, match="host"):
        evaluate(framework(control("C1", "automated", "x.y")), collection(), ())


def test_score_counts_only_passes_and_reports_coverage_separately():
    results = evaluate(
        framework(
            control("PASS", "automated", "a.a"),
            control("FAIL", "automated", "b.b"),
            control("PARTIAL", "hybrid", "c.c"),
            control("NONE", "questionnaire"),
        ),
        collection(
            *clean("a.a"),
            *[seen("b.b", h, "present") for h in HOSTS],
            *clean("c.c"),
        ),
        HOSTS,
    )

    summary = score(results)

    assert (summary.passed, summary.failed, summary.partial, summary.not_assessed) == (1, 1, 1, 1)
    assert summary.total == 4
    assert summary.compliance_percent == 25.0
    assert summary.coverage_percent == 75.0


def test_score_of_nothing_is_zero():
    summary = score(())

    assert (summary.compliance_percent, summary.coverage_percent) == (0.0, 0.0)


def test_clean_scan_of_the_real_catalogue_cannot_claim_compliance():
    ce = load_builtin_framework("cyber-essentials")
    checks = {r.check for c in ce.controls for r in c.evidence}
    items = [seen(check, HOSTS[0], "absent") for check in sorted(checks)]

    summary = score(evaluate(ce, collection(*items), HOSTS[:1]))

    assert (summary.passed, summary.partial, summary.not_assessed) == (0, 7, 20)
    assert summary.compliance_percent == 0.0
    assert summary.coverage_percent == 25.9
