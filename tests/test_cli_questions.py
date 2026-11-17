from pathlib import Path

import yaml
from click.testing import CliRunner

from complyscope.cli import cli
from complyscope.controls import load_builtin_framework
from complyscope.questionnaire import load_answers

EXAMPLE_SCOPE = Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml"


def run(*args):
    return CliRunner().invoke(cli, list(args))


def test_list_shows_every_question_with_its_control():
    result = run("questions", "list")

    assert result.exit_code == 0, result.output
    assert "27 questions" in result.stdout
    assert "CE-UA-04-Q1  (CE-UA-04)" in result.stdout
    assert "Is MFA turned on for every service" in result.stdout


def test_list_marks_questions_that_allow_not_applicable():
    result = run("questions", "list", "--theme", "malware_protection")

    assert result.exit_code == 0, result.output
    assert "3 questions" in result.stdout
    assert "CE-MP-02-Q1  (CE-MP-02)  [not_applicable allowed]" in result.stdout
    assert "CE-UA-04-Q1" not in result.stdout


def test_list_rejects_unknown_theme():
    result = run("questions", "list", "--theme", "patching")

    assert result.exit_code == 2
    assert "unknown theme" in result.stderr


def template(tmp_path, *extra):
    out = tmp_path / "answers.yaml"
    result = run(
        "questions", "template", "--scope", str(EXAMPLE_SCOPE), "--output", str(out), *extra
    )
    return result, out


def test_template_is_a_valid_answers_file_with_nothing_answered(tmp_path):
    result, out = template(tmp_path)

    assert result.exit_code == 0, result.output
    sheet = load_answers(out, load_builtin_framework("cyber-essentials"))
    assert sheet.organisation == "Acme Ltd (fictional)"
    assert sheet.answers == ()
    assert "Wrote 27 questions" in result.stdout


def test_template_shows_each_question_as_a_comment(tmp_path):
    _, out = template(tmp_path)
    text = out.read_text()

    assert "# CE-UA-04 · MFA is used wherever available, and always for cloud services" in text
    assert "#   Is MFA turned on for every service that supports it" in text
    assert "not_applicable allowed (needs a note)" in text
    assert len(yaml.safe_load(text)["answers"]) == 27


def test_filling_in_one_answer_makes_it_count(tmp_path):
    _, out = template(tmp_path)
    text = out.read_text()
    filled = text.replace(
        "  - question: CE-UA-04-Q1\n    answer:\n    answered_by:\n    answered_on:\n",
        "  - question: CE-UA-04-Q1\n    answer: no\n    answered_by: Jane Doe\n"
        "    answered_on: 2026-11-17\n",
    )
    assert filled != text
    out.write_text(filled)

    sheet = load_answers(out, load_builtin_framework("cyber-essentials"))

    assert [(a.question, a.answer) for a in sheet.answers] == [("CE-UA-04-Q1", "no")]


def test_template_does_not_overwrite_without_force(tmp_path):
    out = tmp_path / "answers.yaml"
    out.write_text("keep me")

    refused, _ = template(tmp_path)
    assert refused.exit_code == 2
    assert out.read_text() == "keep me"

    forced, _ = template(tmp_path, "--force")
    assert forced.exit_code == 0, forced.output
    assert "keep me" not in out.read_text()


def test_template_needs_a_valid_scope(tmp_path):
    result = run(
        "questions",
        "template",
        "--scope",
        str(tmp_path / "missing.yaml"),
        "--output",
        str(tmp_path / "answers.yaml"),
    )

    assert result.exit_code == 2
    assert "not found" in result.stderr
