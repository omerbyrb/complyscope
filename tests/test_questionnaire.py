from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from complyscope.controls import FrameworkLoadError, load_builtin_framework, load_framework
from complyscope.models import Answer, AnswerSheet, Framework
from complyscope.questionnaire import AnswersError, load_answers

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "tests" / "fixtures" / "frameworks" / "mini"
EXAMPLE_ANSWERS = ROOT / "examples" / "answers.example.yaml"


@pytest.fixture(scope="module")
def ce():
    return load_builtin_framework("cyber-essentials")


def make_answer(**overrides):
    data = {
        "question": "CE-UA-04-Q1",
        "answer": "yes",
        "answered_by": "Jane Doe (fictional)",
        "answered_on": date(2026, 11, 15),
    }
    return Answer.model_validate(data | overrides)


# --- Questions in the catalogue -----------------------------------------------------------


def test_every_cyber_essentials_control_has_a_question(ce):
    assert len(ce.questions) == 27
    for control in ce.controls:
        assert any(rule.source == "questionnaire" for rule in control.evidence), control.id


def test_every_question_is_used_by_a_control(ce):
    used = {r.question for c in ce.controls for r in c.evidence if r.source == "questionnaire"}

    assert used == {q.id for q in ce.questions}


def test_mini_fixture_loads_its_questions():
    assert [q.id for q in load_framework(MINI).questions] == ["MINI-SC-Q1", "MINI-SC-Q2"]


def test_rule_pointing_at_an_unknown_question_is_rejected():
    with pytest.raises(ValidationError, match="unknown question 'Q-404'"):
        Framework.model_validate(
            {
                "id": "mini",
                "name": "Mini",
                "version": "1",
                "publisher": "tests",
                "source_url": "https://example.org",
                "themes": ["t"],
                "controls": [
                    {
                        "id": "C-1",
                        "theme": "t",
                        "title": "t",
                        "assessment": "questionnaire",
                        "evidence": [{"source": "questionnaire", "question": "Q-404"}],
                    }
                ],
            }
        )


def test_framework_with_questionnaire_rules_but_no_questions_file_fails_to_load(tmp_path):
    import shutil

    shutil.copytree(MINI, tmp_path / "mini")
    (tmp_path / "mini" / "questions.yaml").unlink()

    with pytest.raises(FrameworkLoadError, match="unknown question"):
        load_framework(tmp_path / "mini")


# --- Answers -------------------------------------------------------------------------------


def test_not_applicable_needs_a_justification():
    with pytest.raises(ValidationError, match="note"):
        make_answer(answer="not_applicable")

    assert make_answer(answer="not_applicable", note="No admin interface exists").note


@pytest.mark.parametrize("raw, expected", [(True, "yes"), (False, "no")])
def test_unquoted_yaml_yes_and_no_are_understood(raw, expected):
    # YAML 1.1 reads a bare yes/no as a boolean.
    assert make_answer(answer=raw).answer == expected


def test_unknown_answer_and_future_date_are_rejected():
    with pytest.raises(ValidationError):
        make_answer(answer="maybe")
    with pytest.raises(ValidationError, match="future"):
        make_answer(answered_on=date(2999, 1, 1))


def test_answer_sheet_rejects_two_answers_to_one_question():
    with pytest.raises(ValidationError, match="answered twice: CE-UA-04-Q1"):
        AnswerSheet(
            organisation="Acme Ltd (fictional)",
            framework="cyber-essentials",
            answers=(make_answer(), make_answer(answer="no")),
        )


def test_example_answers_load_against_the_catalogue(ce):
    sheet = load_answers(EXAMPLE_ANSWERS, ce)

    assert len(sheet.answers) == 27
    assert sheet.get("CE-UA-04-Q1").answer == "no"
    assert sheet.get("CE-NOT-ASKED") is None


def test_missing_answers_file_means_no_answers(ce, tmp_path):
    assert load_answers(tmp_path / "answers.yaml", ce) is None


def write(tmp_path, body):
    path = tmp_path / "answers.yaml"
    path.write_text(body)
    return path


HEADER = "organisation: Acme Ltd (fictional)\nframework: cyber-essentials\n"


@pytest.mark.parametrize(
    "body, message",
    [
        (
            HEADER + "answers:\n  - {question: CE-XX-99-Q1, answer: 'yes', answered_by: J,"
            " answered_on: 2026-11-15}\n",
            "unknown question CE-XX-99-Q1",
        ),
        (
            HEADER + "answers:\n  - {question: CE-UA-04-Q1, answer: not_applicable,"
            " answered_by: J, answered_on: 2026-11-15, note: x}\n",
            "CE-UA-04-Q1 cannot be answered not_applicable",
        ),
        ("organisation: Acme\nframework: iso27001-2022\nanswers: []\n", "iso27001-2022"),
        ("answers: !!python/object/apply:os.system ['echo pwned']\n", "invalid YAML"),
        ("- a list\n", "expected a mapping"),
        (HEADER + "answers: [{question: CE-UA-04-Q1}]\n", "invalid answers"),
    ],
)
def test_invalid_answers_files_are_refused_with_the_file_name(ce, tmp_path, body, message):
    with pytest.raises(AnswersError, match=message) as error:
        load_answers(write(tmp_path, body), ce)
    assert "answers.yaml" in str(error.value)
