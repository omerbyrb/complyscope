"""Questionnaire answers: the evidence for what a scan cannot see (see ADR-0014)."""

from datetime import date
from typing import Any, Literal

from pydantic import field_validator, model_validator

from complyscope.models.base import NonEmptyStr, StrictModel
from complyscope.models.control import ControlId, FrameworkId


class Answer(StrictModel):
    question: ControlId
    answer: Literal["yes", "no", "not_applicable"]
    answered_by: NonEmptyStr
    answered_on: date
    note: str = ""

    @field_validator("answer", mode="before")
    @classmethod
    def _yaml_booleans(cls, value: Any) -> Any:
        # YAML 1.1 turns an unquoted yes/no into True/False.
        if isinstance(value, bool):
            return "yes" if value else "no"
        return value

    @field_validator("answered_on")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("an answer cannot be dated in the future")
        return value

    @model_validator(mode="after")
    def _justify_not_applicable(self) -> "Answer":
        if self.answer == "not_applicable" and not self.note.strip():
            raise ValueError(f"{self.question}: not_applicable needs a note explaining why")
        return self


class AnswerSheet(StrictModel):
    """The organisation's answers (answers.yaml), written and owned by people."""

    organisation: NonEmptyStr
    framework: FrameworkId
    answers: tuple[Answer, ...] = ()

    @model_validator(mode="after")
    def _one_answer_per_question(self) -> "AnswerSheet":
        seen: set[str] = set()
        for answer in self.answers:
            if answer.question in seen:
                raise ValueError(f"question answered twice: {answer.question}")
            seen.add(answer.question)
        return self

    def get(self, question_id: str) -> Answer | None:
        return next((a for a in self.answers if a.question == question_id), None)
