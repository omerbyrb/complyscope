import shutil
from pathlib import Path

import pytest

from complyscope.controls import FrameworkLoadError, load_framework
from complyscope.models import AssessmentMethod

MINI = Path(__file__).parent / "fixtures" / "frameworks" / "mini"


@pytest.fixture
def mini_copy(tmp_path):
    """A writable copy of the mini framework that a test can break."""
    target = tmp_path / "mini"
    shutil.copytree(MINI, target)
    return target


def test_load_framework_reads_metadata_and_all_control_files():
    framework = load_framework(MINI)

    assert framework.id == "mini"
    assert framework.version == "1.0"
    assert [c.id for c in framework.controls] == ["MINI-FW-01", "MINI-SC-01", "MINI-SC-02"]
    assert framework.get("MINI-SC-02").assessment is AssessmentMethod.QUESTIONNAIRE


def test_missing_framework_file_is_reported(tmp_path):
    with pytest.raises(FrameworkLoadError, match="framework.yaml"):
        load_framework(tmp_path)


def test_framework_file_must_be_a_mapping(mini_copy):
    (mini_copy / "framework.yaml").write_text("- mini\n")

    with pytest.raises(FrameworkLoadError, match="framework.yaml.*mapping"):
        load_framework(mini_copy)


def test_yaml_syntax_error_names_the_file(mini_copy):
    (mini_copy / "controls" / "firewalls.yaml").write_text("controls: [unclosed\n")

    with pytest.raises(FrameworkLoadError, match="firewalls.yaml"):
        load_framework(mini_copy)


def test_control_file_without_controls_list_is_rejected(mini_copy):
    (mini_copy / "controls" / "firewalls.yaml").write_text("- id: MINI-FW-01\n")

    with pytest.raises(FrameworkLoadError, match="firewalls.yaml.*'controls' list"):
        load_framework(mini_copy)


def test_invalid_control_error_names_file_and_control_id(mini_copy):
    path = mini_copy / "controls" / "firewalls.yaml"
    path.write_text(path.read_text().replace("assessment: automated", "assessment: guesswork"))

    with pytest.raises(FrameworkLoadError, match="firewalls.yaml.*MINI-FW-01"):
        load_framework(mini_copy)


def test_duplicate_control_id_across_files_names_both_files(mini_copy):
    path = mini_copy / "controls" / "secure_configuration.yaml"
    path.write_text(path.read_text().replace("MINI-SC-02", "MINI-FW-01"))

    with pytest.raises(
        FrameworkLoadError, match="MINI-FW-01.*firewalls.yaml.*secure_configuration"
    ):
        load_framework(mini_copy)


def test_control_with_undeclared_theme_is_rejected(mini_copy):
    path = mini_copy / "controls" / "firewalls.yaml"
    path.write_text(path.read_text().replace("theme: firewalls", "theme: patching"))

    with pytest.raises(FrameworkLoadError, match="unknown theme 'patching'"):
        load_framework(mini_copy)


def test_controls_must_not_be_declared_in_framework_file(mini_copy):
    with (mini_copy / "framework.yaml").open("a") as f:
        f.write("controls: []\n")

    with pytest.raises(FrameworkLoadError, match="controls/"):
        load_framework(mini_copy)


def test_yaml_tags_that_construct_python_objects_are_refused(mini_copy):
    (mini_copy / "controls" / "firewalls.yaml").write_text(
        "controls: !!python/object/apply:os.system ['echo pwned']\n"
    )

    with pytest.raises(FrameworkLoadError, match="firewalls.yaml"):
        load_framework(mini_copy)
