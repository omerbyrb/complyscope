"""Command-line entry point for complyscope."""

import click

from complyscope import __version__

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
    click.echo("Frameworks: Cyber Essentials (in progress), ISO 27001:2022, NIST CSF 2.0 (planned)")
