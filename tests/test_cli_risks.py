from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from complyscope.cli import cli
from complyscope.controls import load_builtin_framework
from complyscope.models import Evidence, EvidenceCollection, Risk, RiskRegister
from complyscope.risk.register import load_register, write_register
from complyscope.scoping import load_scope

EXAMPLE_SCOPE = Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml"
WHEN = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
ORGANISATION = "Acme Ltd (fictional)"
EOL_ON_LOCALHOST = {("banner.eol_software", "localhost")}


def evidence_items(failing=()):
    ce = load_builtin_framework("cyber-essentials")
    checks = sorted({rule.check for control in ce.controls for rule in control.evidence})
    return [
        Evidence(
            source="redscope",
            check=check,
            target=host,
            observed="present" if (check, host) in failing else "absent",
            severity="high" if (check, host) in failing else None,
            collected_at=WHEN,
            collector="redscope 2.0.0",
        )
        for check in checks
        for host in load_scope(EXAMPLE_SCOPE).hosts
    ]


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "evidence.json", tmp_path / "risks.yaml"


def write_evidence(path, failing=()):
    collection = EvidenceCollection(
        organisation=ORGANISATION,
        complyscope_version="0.1.0",
        created_at=WHEN,
        items=evidence_items(failing),
    )
    path.write_text(collection.to_json())


def risks(evidence, register):
    args = ["risks", "--scope", str(EXAMPLE_SCOPE), "--evidence", str(evidence)]
    return CliRunner().invoke(cli, [*args, "--register", str(register)])


def row(output, risk_id):
    return next(line.split() for line in output.splitlines() if line.startswith(risk_id))


def test_first_run_drafts_risks_for_failed_controls(paths):
    evidence, register = paths
    write_evidence(evidence, EOL_ON_LOCALHOST)

    result = risks(evidence, register)

    assert result.exit_code == 0, result.output
    assert "Added: R-CE-SU-01, R-CE-SU-02" in result.stdout
    assert row(result.stdout, "R-CE-SU-01")[:4] == ["R-CE-SU-01", "high", "12", "-"]
    assert "R-CE-SU-01: no risk owner, impact not confirmed, no treatment plan" in result.stdout
    assert "2 open risk(s) above the risk appetite" in result.stdout
    assert [r.id for r in load_register(register).risks] == ["R-CE-SU-01", "R-CE-SU-02"]


def test_rerun_keeps_what_the_owner_wrote(paths):
    evidence, register = paths
    write_evidence(evidence, EOL_ON_LOCALHOST)
    risks(evidence, register)

    current = load_register(register)
    edited = Risk.model_validate(
        current.risks[0].model_dump()
        | {
            "owner": "Jane Doe (fictional)",
            "impact": 2,
            "impact_confirmed": True,
            "plan": "Upgrade OpenSSH on localhost",
        }
    )
    write_register(
        register, RiskRegister.model_validate(current.model_dump() | {"risks": [edited]})
    )

    result = risks(evidence, register)

    assert result.exit_code == 0, result.output
    assert row(result.stdout, "R-CE-SU-01")[:4] == ["R-CE-SU-01", "medium", "8", "Jane"]
    assert "R-CE-SU-01:" not in result.stdout.split("Needs attention:")[1]
    assert load_register(register).risks[0].owner == "Jane Doe (fictional)"


def test_fixed_issue_is_reported_for_review_not_deleted(paths):
    evidence, register = paths
    write_evidence(evidence, EOL_ON_LOCALHOST)
    risks(evidence, register)
    write_evidence(evidence)

    result = risks(evidence, register)

    assert result.exit_code == 0, result.output
    assert "No longer failing (review for closure): R-CE-SU-01, R-CE-SU-02" in result.stdout
    assert len(load_register(register).risks) == 2


def test_no_failures_and_no_register_raises_no_risks(paths):
    evidence, register = paths
    write_evidence(evidence)

    result = risks(evidence, register)

    assert result.exit_code == 0, result.output
    assert "No open risks." in result.stdout
    assert load_register(register).risks == ()


def test_register_for_another_organisation_is_refused(paths):
    evidence, register = paths
    write_evidence(evidence)
    write_register(register, RiskRegister(organisation="Other Ltd", framework="cyber-essentials"))

    result = risks(evidence, register)

    assert result.exit_code == 2
    assert "belongs to" in result.stderr


def test_invalid_register_is_a_usage_error(paths):
    evidence, register = paths
    write_evidence(evidence)
    register.write_text("- not a register\n")

    result = risks(evidence, register)

    assert result.exit_code == 2
    assert "risks.yaml" in result.stderr


def test_evidence_checks_are_shared_with_assess(paths):
    evidence, register = paths
    collection = EvidenceCollection(
        organisation="Other Ltd", complyscope_version="0.1.0", created_at=WHEN
    )
    evidence.write_text(collection.to_json())

    result = risks(evidence, register)

    assert result.exit_code == 2
    assert "Other Ltd" in result.stderr
    assert not register.exists()
