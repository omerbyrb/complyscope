from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from complyscope import __version__  # noqa: E402
from complyscope.api import create_app  # noqa: E402
from complyscope.cli import cli  # noqa: E402
from complyscope.controls import load_builtin_framework  # noqa: E402
from complyscope.models import Evidence, EvidenceCollection, Risk, RiskRegister  # noqa: E402
from complyscope.risk.register import write_register  # noqa: E402
from complyscope.scoping import load_scope  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "examples" / "scope.example.yaml"
ANSWERS = ROOT / "examples" / "answers.example.yaml"
WHEN = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
ORG = "Acme Ltd (fictional)"


def write_evidence(path, failing=()):
    ce = load_builtin_framework("cyber-essentials")
    checks = sorted({r.check for c in ce.controls for r in c.evidence if r.source == "redscope"})
    items = [
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
        for host in load_scope(SCOPE).hosts
    ]
    path.write_text(
        EvidenceCollection(
            organisation=ORG, complyscope_version="0.1.0", created_at=WHEN, items=items
        ).to_json()
    )


@pytest.fixture
def files(tmp_path):
    evidence = tmp_path / "evidence.json"
    write_evidence(evidence, {("banner.eol_software", "localhost")})
    register = tmp_path / "risks.yaml"
    write_register(
        register,
        RiskRegister(
            organisation=ORG,
            framework="cyber-essentials",
            risks=(
                Risk(
                    id="R-CE-SU-01",
                    framework="cyber-essentials",
                    control_ids=("CE-SU-01",),
                    title="Control not met: supported software",
                    likelihood=4,
                    impact=3,
                    raised_on=date(2026, 11, 17),
                    review_by=date(2026, 12, 17),
                ),
            ),
        ),
    )
    return {"evidence": evidence, "register": register, "tmp": tmp_path}


def client(files, **overrides):
    paths = {
        "scope_path": SCOPE,
        "evidence_path": files["evidence"],
        "answers_path": ANSWERS,
        "register_path": files["register"],
    } | overrides
    return TestClient(create_app(**paths))


def test_health_reports_the_version(files):
    response = client(files).get("/api/health")

    assert response.json() == {"status": "ok", "version": __version__}


def test_assessment_returns_score_and_every_control(files):
    body = client(files).get("/api/assessment").json()

    assert body["organisation"] == ORG
    assert body["framework"] == {
        "id": "cyber-essentials",
        "name": "Cyber Essentials",
        "version": "3.3",
    }
    assert body["score"]["total"] == 27
    assert body["score"]["coverage_percent"] == 100.0
    statuses = {c["id"]: c["status"] for c in body["controls"]}
    assert statuses["CE-SU-01"] == "fail"
    assert statuses["CE-UA-01"] == "pass"


def test_control_detail_includes_evidence_answers_and_crosswalk(files):
    body = client(files).get("/api/controls/CE-SU-01").json()

    assert body["status"] == "fail"
    assert "banner.eol_software on localhost" in body["rationale"]
    assert {e["observed"] for e in body["evidence"]} == {"present", "absent"}
    assert [a["question"] for a in body["answers"]] == ["CE-SU-01-Q1"]
    assert body["crosswalk"]["iso27001-2022"] == ["A.8.8"]


def test_unknown_control_is_404(files):
    assert client(files).get("/api/controls/CE-XX-99").status_code == 404


def test_risks_include_score_level_and_what_they_need(files):
    (risk,) = client(files).get("/api/risks").json()["risks"]

    assert (risk["id"], risk["score"], risk["level"]) == ("R-CE-SU-01", 12, "high")
    assert risk["needs_attention"] == ["no risk owner", "impact not confirmed", "no treatment plan"]


def test_missing_register_means_no_risks(files):
    response = client(files, register_path=files["tmp"] / "none.yaml").get("/api/risks")

    assert response.json() == {"organisation": ORG, "risks": []}


def test_bad_inputs_are_reported_with_their_source(files):
    response = client(files, evidence_path=files["tmp"] / "missing.json").get("/api/assessment")

    assert response.status_code == 422
    assert response.json()["detail"]["source"] == "evidence"


def test_invalid_register_is_reported(files):
    files["register"].write_text("- nope\n")

    response = client(files).get("/api/risks")

    assert response.status_code == 422
    assert response.json()["detail"]["source"] == "register"


def test_api_is_read_only(files):
    assert client(files).post("/api/assessment").status_code == 405


def test_api_picks_up_changed_files_without_restart(files):
    api = client(files)
    assert api.get("/api/controls/CE-SU-01").json()["status"] == "fail"

    write_evidence(files["evidence"])

    assert api.get("/api/controls/CE-SU-01").json()["status"] == "pass"


# --- complyscope serve ------------------------------------------------------------------


@pytest.fixture
def captured_run(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    return calls


def test_serve_binds_to_localhost_by_default(captured_run):
    result = CliRunner().invoke(cli, ["serve", "--scope", str(SCOPE)])

    assert result.exit_code == 0, result.output
    assert captured_run == [{"host": "127.0.0.1", "port": 8000}]


def test_serve_refuses_a_public_address_without_explicit_consent(captured_run):
    refused = CliRunner().invoke(cli, ["serve", "--host", "0.0.0.0"])

    assert refused.exit_code == 2
    assert "--allow-remote" in refused.stderr
    assert captured_run == []

    allowed = CliRunner().invoke(cli, ["serve", "--host", "0.0.0.0", "--allow-remote"])
    assert allowed.exit_code == 0, allowed.output
    assert captured_run == [{"host": "0.0.0.0", "port": 8000}]


def test_serve_treats_localhost_as_local_and_other_names_as_remote(captured_run):
    assert CliRunner().invoke(cli, ["serve", "--host", "localhost"]).exit_code == 0
    assert CliRunner().invoke(cli, ["serve", "--host", "laptop.example.test"]).exit_code == 2
    assert [call["host"] for call in captured_run] == ["localhost"]


def test_serve_explains_how_to_install_the_web_extra(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "uvicorn", None)

    result = CliRunner().invoke(cli, ["serve"])

    assert result.exit_code == 1
    assert "complyscope[web]" in result.stderr
