"""Load everything an assessment needs and check it belongs together.

Shared by the CLI and the API so both refuse the same mismatched inputs.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from complyscope.controls import FrameworkLoadError, load_builtin_framework
from complyscope.mapping.engine import evaluate
from complyscope.models import AnswerSheet, ControlResult, EvidenceCollection, Framework, Scope
from complyscope.questionnaire import AnswersError, load_answers
from complyscope.scoping import ScopeError, load_scope


class AssessmentInputError(Exception):
    """One input is missing, invalid or from another engagement.

    ``source`` names the input: scope, framework, evidence or answers.
    """

    def __init__(self, source: str, message: str):
        super().__init__(message)
        self.source = source


@dataclass(frozen=True)
class Assessment:
    scope: Scope
    framework: Framework
    results: tuple[ControlResult, ...]
    answers: AnswerSheet | None


def load_assessment(
    scope_path: Path, evidence_path: Path, framework: str, answers_path: Path
) -> Assessment:
    try:
        scope = load_scope(scope_path)
    except ScopeError as e:
        raise AssessmentInputError("scope", str(e)) from e
    try:
        catalogue = load_builtin_framework(framework)
    except FrameworkLoadError as e:
        raise AssessmentInputError("framework", str(e)) from e
    collection = _load_evidence(Path(evidence_path))

    # Inputs from another engagement must not be judged against this scope.
    if collection.organisation != scope.organisation:
        raise AssessmentInputError(
            "evidence",
            f"{evidence_path} belongs to {collection.organisation!r}, "
            f"but the scope is for {scope.organisation!r}",
        )
    outside = sorted({item.target for item in collection.items} - set(scope.hosts))
    if outside:
        raise AssessmentInputError(
            "evidence",
            f"{evidence_path} has evidence for hosts outside the scope: {', '.join(outside)}",
        )

    try:
        answers = load_answers(answers_path, catalogue)
    except AnswersError as e:
        raise AssessmentInputError("answers", str(e)) from e
    if answers is not None and answers.organisation != scope.organisation:
        raise AssessmentInputError(
            "answers",
            f"{answers_path} belongs to {answers.organisation!r}, "
            f"but the scope is for {scope.organisation!r}",
        )

    results = evaluate(catalogue, collection, scope.hosts, answers)
    return Assessment(scope=scope, framework=catalogue, results=results, answers=answers)


def _load_evidence(path: Path) -> EvidenceCollection:
    if not path.is_file():
        raise AssessmentInputError("evidence", f"{path}: file not found")
    try:
        return EvidenceCollection.from_json(path.read_text(encoding="utf-8"))
    except ValidationError as e:
        raise AssessmentInputError("evidence", f"{path}: invalid evidence: {e}") from e
