from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from complyscope.models import Evidence, EvidenceCollection, Severity

WHEN = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def make_evidence(**overrides):
    data = {
        "source": "redscope",
        "check": "ssltls.deprecated_protocol",
        "target": "app.example.test",
        "observed": "present",
        "severity": "high",
        "title": "Deprecated Protocol Supported: TLSv1",
        "details": "Server accepted a TLS 1.0 handshake",
        "collected_at": WHEN,
        "collector": "redscope 2.0.0",
    }
    data.update(overrides)
    return Evidence.model_validate(data)


def make_collection(items):
    return EvidenceCollection(
        organisation="Acme Ltd (fictional)",
        complyscope_version="0.1.0",
        created_at=WHEN,
        items=items,
    )


def test_present_observation_keeps_severity_and_details():
    evidence = make_evidence()

    assert evidence.observed == "present"
    assert evidence.severity is Severity.HIGH
    assert evidence.check == "ssltls.deprecated_protocol"


def test_absent_observation_has_no_severity():
    evidence = make_evidence(observed="absent", severity=None, title="", details="")

    assert evidence.severity is None


def test_present_observation_requires_severity():
    with pytest.raises(ValidationError, match="present.*severity"):
        make_evidence(severity=None)


def test_absent_observation_rejects_severity():
    with pytest.raises(ValidationError, match="absent.*severity"):
        make_evidence(observed="absent")


@pytest.mark.parametrize("bad", ["", "ssltls", "SSLTLS.x", "ssltls.deprecated protocol"])
def test_malformed_check_id_is_rejected(bad):
    with pytest.raises(ValidationError):
        make_evidence(check=bad)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError):
        make_evidence(collected_at=datetime(2026, 11, 1, 9, 30))


def test_unknown_source_and_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        make_evidence(source="gut-feeling")
    with pytest.raises(ValidationError):
        make_evidence(confidence="high")


def test_collection_round_trips_through_json():
    collection = make_collection(
        [
            make_evidence(),
            make_evidence(check="headers.http_not_redirected", observed="absent", severity=None),
        ]
    )

    assert EvidenceCollection.from_json(collection.to_json()) == collection


def test_collection_rejects_contradictory_observations_for_same_check_and_target():
    present = make_evidence()
    absent = make_evidence(observed="absent", severity=None)

    with pytest.raises(ValidationError, match="ssltls.deprecated_protocol.*app.example.test"):
        make_collection([present, absent])


def test_collection_allows_several_findings_for_one_check():
    first = make_evidence(title="Deprecated Protocol Supported: TLSv1")
    second = make_evidence(title="Deprecated Protocol Supported: TLSv1.1")

    assert len(make_collection([first, second]).items) == 2
