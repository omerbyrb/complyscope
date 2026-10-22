"""Data model for framework controls loaded from YAML (see ADR-0002)."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Framework ids are slugs, e.g. "cyber-essentials", "iso27001-2022", "nist-csf-2.0".
FrameworkId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")]

# Control ids follow each publisher's style: "CE-FW-01", "A.8.9", "PR.PS-01".
ControlId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$")]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _StrictModel(BaseModel):
    # Reject unknown keys so a typo in YAML (e.g. "asessment") fails loudly
    # instead of being silently ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class AssessmentMethod(StrEnum):
    AUTOMATED = "automated"
    QUESTIONNAIRE = "questionnaire"
    HYBRID = "hybrid"


class RedscopeRule(_StrictModel):
    """Evidence from a redscope technical check, identified by its stable check_id."""

    source: Literal["redscope"]
    check: NonEmptyStr
    fail_if: Literal["present", "absent"] = "present"


class QuestionnaireRule(_StrictModel):
    """Evidence from an answer in the questionnaire module."""

    source: Literal["questionnaire"]
    question: NonEmptyStr


EvidenceRule = Annotated[RedscopeRule | QuestionnaireRule, Field(discriminator="source")]

_ALLOWED_SOURCES = {
    AssessmentMethod.AUTOMATED: {"redscope"},
    AssessmentMethod.QUESTIONNAIRE: {"questionnaire"},
    AssessmentMethod.HYBRID: {"redscope", "questionnaire"},
}


class Control(_StrictModel):
    id: ControlId
    theme: NonEmptyStr
    title: NonEmptyStr
    description: str = ""
    assessment: AssessmentMethod
    # An empty list is allowed while a catalogue is being drafted; such a
    # control can only ever be reported as not assessed.
    evidence: tuple[EvidenceRule, ...] = ()
    crosswalk: dict[FrameworkId, tuple[ControlId, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _evidence_matches_assessment(self) -> "Control":
        allowed = _ALLOWED_SOURCES[self.assessment]
        for rule in self.evidence:
            if rule.source not in allowed:
                raise ValueError(
                    f"control {self.id}: '{rule.source}' evidence is not allowed "
                    f"when assessment is '{self.assessment.value}'"
                )
        return self


class Framework(_StrictModel):
    id: FrameworkId
    name: NonEmptyStr
    version: NonEmptyStr
    publisher: NonEmptyStr
    source_url: NonEmptyStr
    themes: tuple[NonEmptyStr, ...] = Field(min_length=1)
    controls: tuple[Control, ...] = ()

    @model_validator(mode="after")
    def _controls_are_consistent(self) -> "Framework":
        seen: set[str] = set()
        for control in self.controls:
            if control.id in seen:
                raise ValueError(f"duplicate control id: {control.id}")
            seen.add(control.id)
            if control.theme not in self.themes:
                raise ValueError(f"control {control.id}: unknown theme '{control.theme}'")
        return self

    def get(self, control_id: str) -> Control:
        for control in self.controls:
            if control.id == control_id:
                return control
        raise KeyError(control_id)
