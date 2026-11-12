"""Risks raised from failed controls, scored as in docs/risk-methodology.md (ADR-0013)."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from complyscope.models.base import NonEmptyStr, StrictModel
from complyscope.models.control import ControlId, FrameworkId
from complyscope.models.evidence import Severity


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Treatment(StrEnum):
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"


# The tables below are the methodology; a test checks they match the document.
LEVEL_BANDS: dict[RiskLevel, tuple[int, int]] = {
    RiskLevel.LOW: (1, 3),
    RiskLevel.MEDIUM: (4, 6),
    RiskLevel.HIGH: (8, 12),
    RiskLevel.CRITICAL: (15, 25),
}
REVIEW_DAYS: dict[RiskLevel, int] = {
    RiskLevel.LOW: 180,
    RiskLevel.MEDIUM: 90,
    RiskLevel.HIGH: 30,
    RiskLevel.CRITICAL: 14,
}
LIKELIHOOD_FROM_SEVERITY: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}
# Levels the organisation may accept without treatment (the risk appetite).
ACCEPTABLE_LEVELS = frozenset({RiskLevel.LOW, RiskLevel.MEDIUM})


def risk_level(score: int) -> RiskLevel:
    for level, (low, high) in LEVEL_BANDS.items():
        if low <= score <= high:
            return level
    raise ValueError(f"{score} is not a possible likelihood × impact score")


Scale = Annotated[int, Field(ge=1, le=5)]
RiskId = Annotated[str, StringConstraints(pattern=r"^R-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$")]


class Risk(StrictModel):
    id: RiskId
    framework: FrameworkId
    control_ids: tuple[ControlId, ...] = Field(min_length=1)
    title: NonEmptyStr
    likelihood: Scale
    impact: Scale
    impact_confirmed: bool = False
    owner: NonEmptyStr | None = None
    treatment: Treatment = Treatment.MITIGATE
    plan: str = ""
    raised_on: date
    review_by: date
    evidence_summary: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _review_after_raised(self) -> "Risk":
        if self.review_by < self.raised_on:
            raise ValueError("review_by cannot be earlier than raised_on")
        return self

    @property
    def score(self) -> int:
        return self.likelihood * self.impact

    @property
    def level(self) -> RiskLevel:
        return risk_level(self.score)

    def needs_attention(self) -> list[str]:
        """What the risk owner still has to do before this risk is properly managed."""
        reasons = []
        if self.owner is None:
            reasons.append("no risk owner")
        if not self.impact_confirmed:
            reasons.append("impact not confirmed")
        if not self.plan.strip():
            reasons.append("no treatment plan")
        if self.treatment is Treatment.ACCEPT and self.level not in ACCEPTABLE_LEVELS:
            reasons.append("accepted above the risk appetite")
        return reasons
