import pytest

from complyscope.mapping.rules import rule_status


@pytest.mark.parametrize(
    "fail_if, observed, expected",
    [
        ("present", "present", "fail"),
        ("present", "absent", "pass"),
        ("absent", "absent", "fail"),
        ("absent", "present", "pass"),
        ("present", None, "not_assessed"),
        ("absent", None, "not_assessed"),
    ],
)
def test_rule_status(fail_if, observed, expected):
    assert rule_status(fail_if, observed) == expected
