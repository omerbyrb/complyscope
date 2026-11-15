"""Load an organisation's questionnaire answers (answers.yaml)."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from complyscope.models import AnswerSheet, Framework

__all__ = ["AnswersError", "load_answers"]


class AnswersError(Exception):
    """The answers file is invalid or does not fit the framework; the message names the file."""


def load_answers(path: Path, framework: Framework) -> AnswerSheet | None:
    """Read and check answers.yaml; a missing file means nothing has been answered yet."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise AnswersError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise AnswersError(f"{path}: expected a mapping with organisation, framework, answers")
    try:
        sheet = AnswerSheet.model_validate(data)
    except ValidationError as e:
        raise AnswersError(f"{path}: invalid answers: {e}") from e

    if sheet.framework != framework.id:
        raise AnswersError(f"{path}: answers are for {sheet.framework}, not {framework.id}")
    for answer in sheet.answers:
        question = framework.question(answer.question)
        if question is None:
            raise AnswersError(f"{path}: unknown question {answer.question}")
        if answer.answer == "not_applicable" and not question.allow_not_applicable:
            raise AnswersError(f"{path}: {answer.question} cannot be answered not_applicable")
    return sheet
