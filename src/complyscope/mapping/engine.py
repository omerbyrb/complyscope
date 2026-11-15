"""Judge every control of a framework against collected evidence (see ADR-0012, ADR-0014)."""

from collections import Counter
from collections.abc import Sequence

from complyscope.mapping.rules import rule_status
from complyscope.models import (
    Answer,
    AnswerSheet,
    AssessmentMethod,
    ComplianceScore,
    Control,
    ControlResult,
    ControlStatus,
    Evidence,
    EvidenceCollection,
    Framework,
    QuestionnaireRule,
    RedscopeRule,
)

_EvidenceIndex = dict[tuple[str, str], list[Evidence]]

# A "no" fails a questionnaire rule; "yes" and a justified "not_applicable" pass it.
_ANSWER_OBSERVED = {"yes": "absent", "not_applicable": "absent", "no": "present"}


def evaluate(
    framework: Framework,
    collection: EvidenceCollection,
    hosts: Sequence[str],
    answers: AnswerSheet | None = None,
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
    sheet = answers or AnswerSheet(organisation="-", framework=framework.id)
    return tuple(_evaluate_control(c, index, hosts, sheet) for c in framework.controls)


def _evaluate_control(
    control: Control, index: _EvidenceIndex, hosts: Sequence[str], sheet: AnswerSheet
) -> ControlResult:
    if not control.evidence:
        return ControlResult(
            control_id=control.id,
            status=ControlStatus.NOT_ASSESSED,
            rationale="No evidence rules are defined for this control.",
        )

    # Each outcome is labelled the way it is reported: "check on host" or "question".
    outcomes: dict[str, str] = {}
    failures: dict[str, str] = {}
    evidence: list[Evidence] = []
    used_answers: list[Answer] = []
    for rule in control.evidence:
        if isinstance(rule, RedscopeRule):
            for host in hosts:
                items = index.get((rule.check, host), [])
                evidence.extend(items)
                label = f"{rule.check} on {host}"
                observed = items[0].observed if items else None
                outcomes[label] = rule_status(rule.fail_if, observed)
                failures[label] = label
        elif isinstance(rule, QuestionnaireRule):
            answer = sheet.get(rule.question)
            if answer:
                used_answers.append(answer)
            observed = _ANSWER_OBSERVED[answer.answer] if answer else None
            outcomes[rule.question] = rule_status("present", observed)
            failures[rule.question] = f"{rule.question} answered no"

    failed = sorted(failures[label] for label, s in outcomes.items() if s == "fail")
    missing = sum(status == "not_assessed" for status in outcomes.values())
    has_questions = any(isinstance(rule, QuestionnaireRule) for rule in control.evidence)

    if failed:
        status, rationale = ControlStatus.FAIL, "Failed: " + ", ".join(failed)
    elif missing == len(outcomes):
        status, rationale = ControlStatus.NOT_ASSESSED, "No evidence or answers were collected."
    elif missing:
        status = ControlStatus.PARTIAL
        rationale = f"{missing} of {len(outcomes)} results have no evidence or answer."
    elif control.assessment is AssessmentMethod.HYBRID and not has_questions:
        status = ControlStatus.PARTIAL
        rationale = "Technical checks are clean; the control has no questionnaire part yet."
    else:
        status, rationale = ControlStatus.PASS, "All evidence and answers meet the requirement."
    return ControlResult(
        control_id=control.id,
        status=status,
        rationale=rationale,
        evidence=tuple(evidence),
        answers=tuple(used_answers),
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
