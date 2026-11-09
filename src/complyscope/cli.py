"""Command-line entry point for complyscope."""

from datetime import UTC, datetime
from pathlib import Path

import click
from pydantic import ValidationError

from complyscope import __version__
from complyscope.collectors import redscope_adapter
from complyscope.controls import FrameworkLoadError, load_builtin_framework
from complyscope.mapping.engine import evaluate, score
from complyscope.models import ControlStatus, EvidenceCollection
from complyscope.scoping import OutOfScopeError, ScopeError, load_scope

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


@cli.command()
@click.option(
    "--scope",
    "scope_path",
    type=click.Path(path_type=Path),
    default="scope.yaml",
    show_default=True,
    help="Scope file listing the organisation, its authorisation and the hosts.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path, dir_okay=False),
    default="evidence.json",
    show_default=True,
    help="Where to write the evidence collection (JSON).",
)
@click.option("--host", "hosts", multiple=True, help="Only this in-scope host (repeatable).")
@click.option("--yes", "-y", is_flag=True, help="Run without asking for confirmation.")
@click.option("--force", is_flag=True, help="Overwrite the output file if it exists.")
def collect(scope_path: Path, output: Path, hosts: tuple[str, ...], yes: bool, force: bool) -> None:
    """Run technical checks against in-scope hosts and save the evidence."""
    # Every check that can stop the run happens before any traffic is sent.
    try:
        scope = load_scope(scope_path)
    except ScopeError as e:
        raise click.BadParameter(str(e), param_hint="--scope") from e
    try:
        targets = [scope.ensure_in_scope(h) for h in hosts] if hosts else list(scope.hosts)
    except OutOfScopeError as e:
        raise click.BadParameter(str(e), param_hint="--host") from e
    if output.exists() and not force:
        raise click.BadParameter(
            f"{output} already exists; use --force to overwrite it", param_hint="--output"
        )

    auth = scope.authorisation
    reference = f" ({auth.reference})" if auth.reference else ""
    click.echo(f"Organisation:  {scope.organisation}")
    click.echo(f"Authorised by: {auth.confirmed_by} on {auth.confirmed_on.isoformat()}{reference}")
    click.echo("Targets:")
    for target in targets:
        click.echo(f"  - {target}")
    if not yes:
        click.confirm(f"Run active checks against {len(targets)} host(s)?", abort=True)

    collector = redscope_adapter.RedscopeCollector(
        scope,
        runner=redscope_adapter.run_redscope_module,
        collector=redscope_adapter.redscope_version(),
    )
    evidence = []
    for target in targets:
        click.echo(f"Collecting from {target} ...")
        try:
            run = collector.collect(target)
        except redscope_adapter.RedscopeUnavailableError as e:
            raise click.ClickException(
                "redscope is not installed. Install it with: pip install 'complyscope[scan]'"
            ) from e
        for module, reason in run.skipped.items():
            click.echo(f"  {target}: {module} skipped ({reason})")
        evidence.extend(run.evidence)

    collection = EvidenceCollection(
        organisation=scope.organisation,
        complyscope_version=__version__,
        created_at=datetime.now(UTC),
        items=evidence,
    )
    output.write_text(collection.to_json(), encoding="utf-8")
    present = sum(e.observed == "present" for e in evidence)
    click.echo(
        f"Wrote {len(evidence)} evidence items "
        f"({present} present, {len(evidence) - present} absent) to {output}"
    )


@cli.command()
@click.option(
    "--scope",
    "scope_path",
    type=click.Path(path_type=Path),
    default="scope.yaml",
    show_default=True,
    help="Scope file the evidence was collected under.",
)
@click.option(
    "--evidence",
    "evidence_path",
    type=click.Path(path_type=Path),
    default="evidence.json",
    show_default=True,
    help="Evidence file written by the collect command.",
)
@click.option(
    "--framework",
    "-f",
    default="cyber-essentials",
    show_default=True,
    help="Framework id to assess against.",
)
def assess(scope_path: Path, evidence_path: Path, framework: str) -> None:
    """Judge controls against collected evidence and show the score."""
    try:
        scope = load_scope(scope_path)
    except ScopeError as e:
        raise click.BadParameter(str(e), param_hint="--scope") from e
    try:
        catalogue = load_builtin_framework(framework)
    except FrameworkLoadError as e:
        raise click.BadParameter(str(e), param_hint="--framework") from e
    collection = _load_evidence(evidence_path)

    # Evidence from another engagement must not be judged against this scope.
    if collection.organisation != scope.organisation:
        raise click.BadParameter(
            f"{evidence_path} belongs to {collection.organisation!r}, "
            f"but the scope is for {scope.organisation!r}",
            param_hint="--evidence",
        )
    outside = sorted({item.target for item in collection.items} - set(scope.hosts))
    if outside:
        raise click.BadParameter(
            f"{evidence_path} has evidence for hosts outside the scope: {', '.join(outside)}",
            param_hint="--evidence",
        )

    results = evaluate(catalogue, collection, scope.hosts)
    titles = {control.id: control.title for control in catalogue.controls}
    click.echo(f"{catalogue.name} v{catalogue.version} assessment for {scope.organisation}\n")
    _echo_table(
        ("ID", "STATUS", "TITLE"),
        [(r.control_id, r.status.value, titles[r.control_id]) for r in results],
    )

    failed = [r for r in results if r.status is ControlStatus.FAIL]
    if failed:
        click.echo("\nFailed controls:")
        for result in failed:
            click.echo(f"{result.control_id}: {result.rationale}")

    summary = score(results)
    assessed = summary.total - summary.not_assessed
    click.echo(
        f"\nCompliance: {summary.compliance_percent}% "
        f"({summary.passed} of {summary.total} controls pass)"
    )
    click.echo(
        f"Coverage:   {summary.coverage_percent}% ({assessed} of {summary.total} controls assessed)"
    )
    click.echo("These figures show progress; this is not a certification.")


def _load_evidence(path: Path) -> EvidenceCollection:
    if not path.is_file():
        raise click.BadParameter(f"{path}: file not found", param_hint="--evidence")
    try:
        return EvidenceCollection.from_json(path.read_text(encoding="utf-8"))
    except ValidationError as e:
        raise click.BadParameter(f"{path}: invalid evidence: {e}", param_hint="--evidence") from e


def _echo_table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header) - 1)]
    for row in [header, *rows]:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        click.echo("  ".join([*cells, row[-1]]))
