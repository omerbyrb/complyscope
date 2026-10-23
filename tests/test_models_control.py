import pytest
from pydantic import ValidationError

from complyscope.models import AssessmentMethod, Control, Framework, RedscopeRule


def make_control(**overrides):
    data = {
        "id": "CE-SC-01",
        "theme": "secure_configuration",
        "title": "Unnecessary services are disabled",
        "assessment": "hybrid",
        "evidence": [
            {"source": "redscope", "check": "tls.weak_protocol"},
            {"source": "questionnaire", "question": "CE-SC-Q1"},
        ],
        "crosswalk": {"iso27001-2022": ["A.8.9"], "nist-csf-2.0": ["PR.PS-01"]},
    }
    data.update(overrides)
    return Control.model_validate(data)


def make_framework(controls):
    return Framework.model_validate(
        {
            "id": "cyber-essentials",
            "name": "Cyber Essentials",
            "version": "test",
            "publisher": "NCSC",
            "source_url": "https://example.org",
            "themes": ["firewalls", "secure_configuration"],
            "controls": controls,
        }
    )


def test_valid_control_parses_evidence_into_typed_rules():
    control = make_control()

    assert control.assessment is AssessmentMethod.HYBRID
    assert isinstance(control.evidence[0], RedscopeRule)
    assert control.evidence[0].fail_if == "present"
    assert control.crosswalk["iso27001-2022"] == ("A.8.9",)


@pytest.mark.parametrize("bad_id", ["", "CE SC 01", "CE--01", "-CE-01"])
def test_malformed_control_id_is_rejected(bad_id):
    with pytest.raises(ValidationError):
        make_control(id=bad_id)


def test_unknown_assessment_method_is_rejected():
    with pytest.raises(ValidationError):
        make_control(assessment="guesswork")


def test_unknown_key_is_rejected_to_catch_yaml_typos():
    with pytest.raises(ValidationError, match="asessment"):
        make_control(asessment="automated")


def test_unknown_evidence_source_is_rejected():
    with pytest.raises(ValidationError):
        make_control(evidence=[{"source": "gut-feeling", "check": "x"}])


def test_automated_control_cannot_use_questionnaire_evidence():
    with pytest.raises(ValidationError, match="not allowed when assessment is 'automated'"):
        make_control(
            assessment="automated",
            evidence=[{"source": "questionnaire", "question": "CE-SC-Q1"}],
        )


def test_control_without_evidence_is_allowed_while_drafting():
    assert make_control(evidence=[]).evidence == ()


def test_controls_are_immutable():
    control = make_control()

    with pytest.raises(ValidationError):
        control.title = "changed"


def test_framework_rejects_duplicate_control_ids():
    control = make_control().model_dump()

    with pytest.raises(ValidationError, match="duplicate control id: CE-SC-01"):
        make_framework([control, control])


def test_framework_rejects_control_with_unknown_theme():
    with pytest.raises(ValidationError, match="unknown theme 'patching'"):
        make_framework([make_control(theme="patching").model_dump()])


def test_framework_get_returns_control_by_id():
    framework = make_framework([make_control().model_dump()])

    assert framework.get("CE-SC-01").title == "Unnecessary services are disabled"
    with pytest.raises(KeyError):
        framework.get("CE-XX-99")
