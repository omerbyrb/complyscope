"""Evaluate one evidence rule against what was observed on one host."""


def rule_status(fail_if: str, observed: str | None) -> str:
    """Return "pass", "fail" or "not_assessed".

    fail_if: the observation that makes the rule fail ("present" or "absent").
    observed: "present", "absent", or None when the check produced no evidence.
    """
    if observed is None:
        return "not_assessed"
    return "fail" if observed == fail_if else "pass"
