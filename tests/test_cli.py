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


def test_every_command_prints_notice_to_stderr():
    result = CliRunner().invoke(cli, ["about"])

    assert result.exit_code == 0
    assert AUTHORISED_USE_NOTICE in result.stderr
    assert AUTHORISED_USE_NOTICE not in result.stdout
