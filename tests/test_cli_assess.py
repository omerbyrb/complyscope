from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from complyscope.cli import cli
from complyscope.collectors import redscope_adapter
from complyscope.controls import load_builtin_framework
from complyscope.models import Evidence, EvidenceCollection
from complyscope.scoping import load_scope

EXAMPLE_SCOPE = Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml"
WHEN = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)
ORGANISATION = "Acme Ltd (fictional)"


def seen(check, target, observed="absent"):
    return Evidence(
        source="redscope",
        check=check,
        target=target,
        observed=observed,
        severity="high" if observed == "present" else None,
        collected_at=WHEN,
        collector="redscope 2.0.0",
    )


def clean_evidence(overrides=()):
    """Every catalogue check, clean on every in-scope host, except (check, host) overrides."""
    ce = load_builtin_framework("cyber-essentials")
    checks = sorted({rule.check for control in ce.controls for rule in control.evidence})
    return [
        seen(check, host, "present" if (check, host) in overrides else "absent")
        for check in checks
        for host in load_scope(EXAMPLE_SCOPE).hosts
    ]


@pytest.fixture
def evidence_file(tmp_path):
    def _write(items, organisation=ORGANISATION):
        path = tmp_path / "evidence.json"
        collection = EvidenceCollection(
            organisation=organisation, complyscope_version="0.1.0", created_at=WHEN, items=items
        )
        path.write_text(collection.to_json())
        return path

    return _write


def assess(evidence, *args, scope=EXAMPLE_SCOPE):
    return CliRunner().invoke(
        cli, ["assess", "--scope", str(scope), "--evidence", str(evidence), *args]
    )


def row(output, control_id):
    return next(line.split() for line in output.splitlines() if line.startswith(control_id))


def test_clean_scan_reports_statuses_score_and_coverage(evidence_file):
    result = assess(evidence_file(clean_evidence()))

    assert result.exit_code == 0, result.output
    assert row(result.stdout, "CE-FW-01")[1] == "partial"
    assert row(result.stdout, "CE-UA-01")[1] == "not_assessed"
    assert "Compliance: 0.0% (0 of 27 controls pass)" in result.stdout
    assert "Coverage:   25.9% (7 of 27 controls assessed)" in result.stdout
    assert "not a certification" in result.stdout


def test_failed_control_is_shown_with_its_reason(evidence_file):
    items = clean_evidence(overrides={("banner.eol_software", "localhost")})

    result = assess(evidence_file(items))

    assert result.exit_code == 0, result.output
    assert row(result.stdout, "CE-SU-01")[1] == "fail"
    assert "CE-SU-01: Failed: banner.eol_software on localhost" in result.stdout


def test_empty_evidence_is_entirely_not_assessed(evidence_file):
    result = assess(evidence_file([]))

    assert result.exit_code == 0, result.output
    assert "Coverage:   0.0% (0 of 27 controls assessed)" in result.stdout


def test_evidence_from_another_organisation_is_refused(evidence_file):
    result = assess(evidence_file([], organisation="Other Ltd"))

    assert result.exit_code == 2
    assert "Other Ltd" in result.stderr


def test_evidence_about_a_host_outside_the_scope_is_refused(evidence_file):
    result = assess(evidence_file([seen("banner.eol_software", "other.example.test")]))

    assert result.exit_code == 2
    assert "other.example.test" in result.stderr


def test_missing_evidence_file_is_a_usage_error(tmp_path):
    result = assess(tmp_path / "missing.json")

    assert result.exit_code == 2
    assert "not found" in result.stderr


def test_malformed_evidence_file_is_a_usage_error(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text("{not json")

    result = assess(path)

    assert result.exit_code == 2
    assert "invalid evidence" in result.stderr


def test_invalid_scope_is_a_usage_error(evidence_file, tmp_path):
    result = assess(evidence_file([]), scope=tmp_path / "missing.yaml")

    assert result.exit_code == 2
    assert "not found" in result.stderr


def test_unknown_framework_is_a_usage_error(evidence_file):
    result = assess(evidence_file([]), "--framework", "pci-dss")

    assert result.exit_code == 2
    assert "unknown framework" in result.stderr


def test_assess_never_runs_a_scan(evidence_file, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("assess must not scan")

    monkeypatch.setattr(redscope_adapter, "run_redscope_module", forbidden)

    assert assess(evidence_file(clean_evidence())).exit_code == 0
