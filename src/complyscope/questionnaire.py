"""Load an organisation's questionnaire answers (answers.yaml)."""

import textwrap
from pathlib import Path

import yaml
from pydantic import ValidationError

from complyscope.models import AnswerSheet, Framework

__all__ = ["AnswersError", "load_answers", "render_template"]


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
    if isinstance(data.get("answers"), list):
        # Template entries left blank are simply not answered yet.
        data["answers"] = [
            entry
            for entry in data["answers"]
            if not (isinstance(entry, dict) and entry.get("answer") in (None, ""))
        ]
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


TEMPLATE_HEADER = """\
# complyscope questionnaire answers
# For each question set answer to yes, no or (only where allowed) not_applicable with a
# note explaining why. Fill in answered_by and answered_on (YYYY-MM-DD). Leave answer empty
# for questions not answered yet: their controls stay not assessed.
"""


def render_template(framework: Framework, organisation: str) -> str:
    """A blank answers.yaml listing every question, grouped by control, as comments."""
    lines = [
        TEMPLATE_HEADER
        + yaml.safe_dump({"organisation": organisation, "framework": framework.id}, sort_keys=False)
        + "answers:"
    ]
    for control in framework.controls:
        for rule in control.evidence:
            if rule.source != "questionnaire":
                continue
            question = framework.question(rule.question)
            lines.append(f"  # {control.id} · {control.title}")
            lines.extend(
                textwrap.wrap(
                    question.text, width=92, initial_indent="  #   ", subsequent_indent="  #   "
                )
            )
            if question.allow_not_applicable:
                lines.append("  #   not_applicable allowed (needs a note)")
            lines += [
                f"  - question: {question.id}",
                "    answer:",
                "    answered_by:",
                "    answered_on:",
                "    note: ''",
                "",
            ]
    return "\n".join(lines)
