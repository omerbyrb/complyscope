"""Evidence: normalised observations produced by collectors (see ADR-0008)."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, model_validator

from complyscope.models.base import CheckId, NonEmptyStr, StrictModel


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Evidence(StrictModel):
    """One observation of one check against one target.

    ``present`` means the check found the issue; ``absent`` means the check ran
    successfully and did not find it. A check that did not run produces no
    evidence at all, so its controls stay ``not_assessed``.
    """

    source: Literal["redscope"]
    check: CheckId
    target: NonEmptyStr
    observed: Literal["present", "absent"]
    severity: Severity | None = None
    title: str = ""
    details: str = ""
    collected_at: AwareDatetime
    collector: NonEmptyStr

    @model_validator(mode="after")
    def _severity_matches_observation(self) -> "Evidence":
        if self.observed == "present" and self.severity is None:
            raise ValueError(f"{self.check}: a present observation needs a severity")
        if self.observed == "absent" and self.severity is not None:
            raise ValueError(f"{self.check}: an absent observation cannot have a severity")
        return self


class EvidenceCollection(StrictModel):
    """Everything collected in one run, as written to and read from JSON."""

    organisation: NonEmptyStr
    complyscope_version: NonEmptyStr
    created_at: AwareDatetime
    items: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def _no_contradictions(self) -> "EvidenceCollection":
        observed: dict[tuple[str, str], set[str]] = {}
        for item in self.items:
            observed.setdefault((item.check, item.target), set()).add(item.observed)
        for (check, target), values in observed.items():
            if len(values) > 1:
                raise ValueError(f"{check} on {target} is recorded as both present and absent")
        return self

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, text: str) -> "EvidenceCollection":
        return cls.model_validate_json(text)
