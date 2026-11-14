from datetime import date

import pytest

from complyscope.models import ControlResult, ControlStatus, Risk, RiskRegister, RiskStatus
from complyscope.risk.register import (
    RegisterError,
    load_register,
    merge_register,
    write_register,
)

TODAY = date(2026, 11, 14)
ORG = "Acme Ltd (fictional)"


def draft(control_id="CE-FW-01", likelihood=4, evidence=("x.y on a.example.test (high)",)):
    return Risk(
        id=f"R-{control_id}",
        framework="cyber-essentials",
        control_ids=(control_id,),
        title=f"Control not met: {control_id}",
        likelihood=likelihood,
        impact=3,
        raised_on=TODAY,
        review_by=date(2026, 12, 14),
        evidence_summary=evidence,
    )


def owned(control_id="CE-FW-01", **overrides):
    """A risk after its owner has worked on it."""
    data = draft(control_id).model_dump() | {
        "owner": "Jane Doe (fictional)",
        "impact": 5,
        "impact_confirmed": True,
        "treatment": "transfer",
        "plan": "Move the service behind the managed firewall",
        "raised_on": date(2026, 10, 1),
        "review_by": date(2026, 11, 30),
    }
    return Risk.model_validate(data | overrides)


def result(control_id, status):
    return ControlResult(control_id=control_id, status=status, rationale="because")


def register(*risks, organisation=ORG, framework="cyber-essentials"):
    return RiskRegister(organisation=organisation, framework=framework, risks=risks)


def merge(existing, drafts, results):
    return merge_register(
        existing,
        drafts,
        results,
        organisation=ORG,
        framework="cyber-essentials",
    )


def test_first_run_adds_every_drafted_risk():
    merged, changes = merge(None, (draft("CE-FW-01"), draft("CE-SU-01")), ())

    assert [r.id for r in merged.risks] == ["R-CE-FW-01", "R-CE-SU-01"]
    assert changes.added == ("R-CE-FW-01", "R-CE-SU-01")


def test_rerun_keeps_owner_decisions_and_refreshes_evidence():
    fresh = draft(likelihood=5, evidence=("x.y on b.example.test (critical)",))

    merged, changes = merge(register(owned()), (fresh,), ())
    (risk,) = merged.risks

    assert risk.owner == "Jane Doe (fictional)"
    assert (risk.impact, risk.impact_confirmed) == (5, True)
    assert risk.treatment.value == "transfer"
    assert risk.plan == "Move the service behind the managed firewall"
    assert (risk.raised_on, risk.review_by) == (date(2026, 10, 1), date(2026, 11, 30))
    assert risk.likelihood == 5
    assert risk.evidence_summary == ("x.y on b.example.test (critical)",)
    assert changes.updated == ("R-CE-FW-01",)


def test_risk_whose_control_now_passes_is_kept_and_reported():
    results = (result("CE-FW-01", ControlStatus.PARTIAL),)

    merged, changes = merge(register(owned()), (), results)

    assert merged.risks == (owned(),)
    assert changes.no_longer_failing == ("R-CE-FW-01",)
    assert changes.not_reassessed == ()


def test_risk_whose_control_could_not_be_assessed_is_not_reported_as_fixed():
    results = (result("CE-FW-01", ControlStatus.NOT_ASSESSED),)

    merged, changes = merge(register(owned()), (), results)

    assert merged.risks == (owned(),)
    assert changes.no_longer_failing == ()
    assert changes.not_reassessed == ("R-CE-FW-01",)


def test_closed_risk_that_fails_again_is_reopened():
    closed = owned(status="closed")

    merged, changes = merge(register(closed), (draft(),), ())

    assert merged.risks[0].status is RiskStatus.OPEN
    assert changes.reopened == ("R-CE-FW-01",)


def test_closed_risk_needs_no_attention():
    assert owned(status="closed", owner=None, plan="").needs_attention() == []


@pytest.mark.parametrize(
    "existing",
    [register(organisation="Other Ltd"), register(framework="iso27001-2022")],
)
def test_register_for_another_organisation_or_framework_is_refused(existing):
    with pytest.raises(RegisterError, match="belongs to"):
        merge(existing, (), ())


def test_register_rejects_duplicate_risk_ids():
    with pytest.raises(ValueError, match="duplicate risk id"):
        register(owned(), owned())


def test_register_round_trips_through_yaml(tmp_path):
    path = tmp_path / "risks.yaml"
    original = register(owned(), draft("CE-SU-01"))

    write_register(path, original)

    assert load_register(path) == original
    assert path.read_text().startswith("# complyscope risk register")


def test_missing_register_loads_as_none(tmp_path):
    assert load_register(tmp_path / "risks.yaml") is None


@pytest.mark.parametrize(
    "content",
    [
        "risks: !!python/object/apply:os.system ['echo pwned']\n",
        "- just a list\n",
        "organisation: Acme\nframework: cyber-essentials\nrisks: [{id: nonsense}]\n",
    ],
)
def test_invalid_register_files_are_refused_with_the_file_name(tmp_path, content):
    path = tmp_path / "risks.yaml"
    path.write_text(content)

    with pytest.raises(RegisterError, match="risks.yaml"):
        load_register(path)
