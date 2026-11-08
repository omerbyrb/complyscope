"""The outcome of judging controls against evidence (see ADR-0012)."""

from enum import StrEnum

from complyscope.models.base import NonEmptyStr, StrictModel
from complyscope.models.evidence import Evidence


class ControlStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_ASSESSED = "not_assessed"


class ControlResult(StrictModel):
    control_id: NonEmptyStr
    status: ControlStatus
    rationale: NonEmptyStr
    evidence: tuple[Evidence, ...] = ()


class ComplianceScore(StrictModel):
    total: int
    passed: int
    failed: int
    partial: int
    not_assessed: int
    compliance_percent: float
    coverage_percent: float
