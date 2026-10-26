"""Command-line entry point for complyscope."""

import click

from complyscope import __version__
from complyscope.controls import FrameworkLoadError, load_builtin_framework

AUTHORISED_USE_NOTICE = (
    "AUTHORISED USE ONLY: run technical checks only against systems you own "
    "or have written permission to assess."
)


@click.group(help=f"complyscope: compliance-as-code for SMEs.\n\n{AUTHORISED_USE_NOTICE}")
@click.version_option(__version__, prog_name="complyscope")
def cli() -> None:
    click.secho(AUTHORISED_USE_NOTICE, fg="yellow", err=True)


@cli.command()
def about() -> None:
    """Show what complyscope does and which frameworks it supports."""
    click.echo(f"complyscope {__version__}")
    click.echo("Frameworks: Cyber Essentials v3.3; ISO 27001:2022, NIST CSF 2.0 (planned)")


@cli.group()
def controls() -> None:
    """Browse framework control catalogues."""


@controls.command("list")
@click.option(
    "--framework",
    "-f",
    default="cyber-essentials",
    show_default=True,
    help="Framework id to list.",
)
@click.option("--theme", "-t", default=None, help="Only show controls in this theme.")
def list_controls(framework: str, theme: str | None) -> None:
    """List the controls of a framework as a table."""
    try:
        catalogue = load_builtin_framework(framework)
    except FrameworkLoadError as e:
        raise click.BadParameter(str(e), param_hint="--framework") from e

    if theme is not None and theme not in catalogue.themes:
        raise click.BadParameter(
            f"unknown theme '{theme}' (available: {', '.join(catalogue.themes)})",
            param_hint="--theme",
        )

    rows = [
        (c.id, c.theme, c.assessment.value, c.title)
        for c in catalogue.controls
        if theme is None or c.theme == theme
    ]
    click.echo(f"{catalogue.name} v{catalogue.version}: {len(rows)} controls\n")
    _echo_table(("ID", "THEME", "ASSESSMENT", "TITLE"), rows)


def _echo_table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header) - 1)]
    for row in [header, *rows]:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        click.echo("  ".join([*cells, row[-1]]))
