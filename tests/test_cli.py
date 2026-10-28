from click.testing import CliRunner

from complyscope import __version__
from complyscope.cli import AUTHORISED_USE_NOTICE, cli


def test_version_flag_prints_version():
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_shows_authorised_use_notice():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "AUTHORISED USE ONLY" in result.output


def test_controls_list_shows_cyber_essentials_by_default():
    result = CliRunner().invoke(cli, ["controls", "list"])

    assert result.exit_code == 0
    assert "Cyber Essentials v3.3: 27 controls" in result.stdout
    assert result.stdout.splitlines()[2].split() == ["ID", "THEME", "ASSESSMENT", "TITLE"]
    assert "CE-FW-01" in result.stdout
    assert "CE-MP-03" in result.stdout


def test_controls_list_filters_by_theme():
    result = CliRunner().invoke(cli, ["controls", "list", "--theme", "malware_protection"])

    assert result.exit_code == 0
    assert "3 controls" in result.stdout
    assert "CE-MP-01" in result.stdout
    assert "CE-FW-01" not in result.stdout


def test_controls_list_rejects_unknown_framework():
    result = CliRunner().invoke(cli, ["controls", "list", "--framework", "pci-dss"])

    assert result.exit_code == 2
    assert "unknown framework 'pci-dss'" in result.stderr


def test_controls_list_rejects_unknown_theme():
    result = CliRunner().invoke(cli, ["controls", "list", "--theme", "patching"])

    assert result.exit_code == 2
    assert "unknown theme 'patching'" in result.stderr


def test_every_command_prints_notice_to_stderr():
    result = CliRunner().invoke(cli, ["about"])

    assert result.exit_code == 0
    assert AUTHORISED_USE_NOTICE in result.stderr
    assert AUTHORISED_USE_NOTICE not in result.stdout
