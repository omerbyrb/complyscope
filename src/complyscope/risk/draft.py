"""Draft one risk per failed control (docs/risk-methodology.md, "How complyscope drafts")."""

from collections.abc import Sequence
from datetime import date, timedelta

from complyscope.models import ControlResult, ControlStatus, Framework, Risk
from complyscope.models.risk import LIKELIHOOD_FROM_SEVERITY, REVIEW_DAYS, risk_level

# A scan cannot measure business impact; the owner must confirm it.
DRAFT_IMPACT = 3
# Only used if a failed control somehow carries no present finding.
DEFAULT_LIKELIHOOD = 3


def draft_risks(
    framework: Framework, results: Sequence[ControlResult], *, today: date
) -> tuple[Risk, ...]:
    titles = {control.id: control.title for control in framework.controls}
    risks = []
    for result in results:
        if result.status is not ControlStatus.FAIL:
            continue
        present = [e for e in result.evidence if e.observed == "present"]
        likelihood = max(
            (LIKELIHOOD_FROM_SEVERITY[e.severity] for e in present), default=DEFAULT_LIKELIHOOD
        )
        level = risk_level(likelihood * DRAFT_IMPACT)
        risks.append(
            Risk(
                id=f"R-{result.control_id}",
                framework=framework.id,
                control_ids=(result.control_id,),
                title=f"Control not met: {titles[result.control_id]}",
                likelihood=likelihood,
                impact=DRAFT_IMPACT,
                raised_on=today,
                review_by=today + timedelta(days=REVIEW_DAYS[level]),
                evidence_summary=tuple(
                    sorted({f"{e.check} on {e.target} ({e.severity.value})" for e in present})
                ),
            )
        )
    return tuple(risks)
