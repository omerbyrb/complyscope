"""Judge every control of a framework against collected evidence (see ADR-0012)."""

from collections import Counter
from collections.abc import Iterable, Sequence

from complyscope.mapping.rules import rule_status
from complyscope.models import (
    AssessmentMethod,
    ComplianceScore,
    Control,
    ControlResult,
    ControlStatus,
    Evidence,
    EvidenceCollection,
    Framework,
    RedscopeRule,
)

_EvidenceIndex = dict[tuple[str, str], list[Evidence]]


def evaluate(
    framework: Framework, collection: EvidenceCollection, hosts: Sequence[str]
) -> tuple[ControlResult, ...]:
    """Return one result per control.

    ``hosts`` is every host that should have been assessed. It cannot be derived from the
    evidence, because a host that produced no evidence would then simply disappear.
    """
    if not hosts:
        raise ValueError("evaluate needs at least one host")
    index: _EvidenceIndex = {}
    for item in collection.items:
        index.setdefault((item.check, item.target), []).append(item)
    return tuple(_evaluate_control(control, index, hosts) for control in framework.controls)


def _evaluate_control(
    control: Control, index: _EvidenceIndex, hosts: Sequence[str]
) -> ControlResult:
    rules = [rule for rule in control.evidence if isinstance(rule, RedscopeRule)]
    if not rules:
        return _result(
            control, ControlStatus.NOT_ASSESSED, "No technical checks; needs the questionnaire."
        )

    outcomes: dict[tuple[str, str], str] = {}
    evidence: list[Evidence] = []
    for rule in rules:
        for host in hosts:
            items = index.get((rule.check, host), [])
            evidence.extend(items)
            observed = items[0].observed if items else None
            outcomes[(rule.check, host)] = rule_status(rule.fail_if, observed)

    failed = sorted(f"{check} on {host}" for (check, host), s in outcomes.items() if s == "fail")
    missing = sum(status == "not_assessed" for status in outcomes.values())

    if failed:
        status, rationale = ControlStatus.FAIL, "Failed: " + ", ".join(failed)
    elif missing == len(outcomes):
        status, rationale = ControlStatus.NOT_ASSESSED, "No evidence was collected for its checks."
    elif missing:
        status = ControlStatus.PARTIAL
        rationale = f"{missing} of {len(outcomes)} check results have no evidence."
    elif control.assessment is AssessmentMethod.HYBRID:
        status = ControlStatus.PARTIAL
        rationale = "Technical checks are clean; the questionnaire part is not assessed yet."
    else:
        status, rationale = ControlStatus.PASS, "All technical checks are clean on every host."
    return _result(control, status, rationale, evidence)


def _result(
    control: Control,
    status: ControlStatus,
    rationale: str,
    evidence: Iterable[Evidence] = (),
) -> ControlResult:
    return ControlResult(
        control_id=control.id, status=status, rationale=rationale, evidence=tuple(evidence)
    )


def score(results: Sequence[ControlResult]) -> ComplianceScore:
    """Compliance counts only passes; coverage says how much could be assessed at all."""
    counts = Counter(result.status for result in results)
    total = len(results)
    assessed = total - counts[ControlStatus.NOT_ASSESSED]

    def percent(part: int) -> float:
        return round(100 * part / total, 1) if total else 0.0

    return ComplianceScore(
        total=total,
        passed=counts[ControlStatus.PASS],
        failed=counts[ControlStatus.FAIL],
        partial=counts[ControlStatus.PARTIAL],
        not_assessed=counts[ControlStatus.NOT_ASSESSED],
        compliance_percent=percent(counts[ControlStatus.PASS]),
        coverage_percent=percent(assessed),
    )
