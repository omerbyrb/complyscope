"""Command-line entry point for complyscope."""

from datetime import UTC, date, datetime
from pathlib import Path

import click

from complyscope import __version__
from complyscope.assessment import AssessmentInputError, load_assessment
from complyscope.collectors import redscope_adapter
from complyscope.controls import FrameworkLoadError, load_builtin_framework
from complyscope.mapping.engine import score
from complyscope.models import (
    ControlResult,
    ControlStatus,
    EvidenceCollection,
    Framework,
    Scope,
)
from complyscope.questionnaire import render_template
from complyscope.risk import ACCEPTABLE_LEVELS, draft_risks
from complyscope.risk.register import (
    RegisterError,
    load_register,
    merge_register,
    write_register,
)
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


@cli.group()
def questions() -> None:
    """Questionnaire for the parts of a framework a scan cannot see."""


def _framework_or_usage_error(framework: str) -> Framework:
    try:
        return load_builtin_framework(framework)
    except FrameworkLoadError as e:
        raise click.BadParameter(str(e), param_hint="--framework") from e


@questions.command("list")
@click.option("--framework", "-f", default="cyber-essentials", show_default=True)
@click.option("--theme", "-t", default=None, help="Only questions for controls in this theme.")
def list_questions(framework: str, theme: str | None) -> None:
    """List the questions and the control each one belongs to."""
    catalogue = _framework_or_usage_error(framework)
    if theme is not None and theme not in catalogue.themes:
        raise click.BadParameter(
            f"unknown theme '{theme}' (available: {', '.join(catalogue.themes)})",
            param_hint="--theme",
        )
    entries = [
        (control, catalogue.question(rule.question))
        for control in catalogue.controls
        if theme is None or control.theme == theme
        for rule in control.evidence
        if rule.source == "questionnaire"
    ]
    click.echo(f"{catalogue.name} v{catalogue.version}: {len(entries)} questions")
    for control, question in entries:
        allowed = "  [not_applicable allowed]" if question.allow_not_applicable else ""
        click.echo(f"\n{question.id}  ({control.id}){allowed}\n    {question.text}")


@questions.command("template")
@click.option(
    "--scope",
    "scope_path",
    type=click.Path(path_type=Path),
    default="scope.yaml",
    show_default=True,
    help="Scope file naming the organisation.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path, dir_okay=False),
    default="answers.yaml",
    show_default=True,
)
@click.option("--framework", "-f", default="cyber-essentials", show_default=True)
@click.option("--force", is_flag=True, help="Overwrite the output file if it exists.")
def questions_template(scope_path: Path, output: Path, framework: str, force: bool) -> None:
    """Write a blank answers file for the organisation to fill in."""
    try:
        scope = load_scope(scope_path)
    except ScopeError as e:
        raise click.BadParameter(str(e), param_hint="--scope") from e
    catalogue = _framework_or_usage_error(framework)
    if output.exists() and not force:
        raise click.BadParameter(
            f"{output} already exists; use --force to overwrite it", param_hint="--output"
        )
    output.write_text(render_template(catalogue, scope.organisation), encoding="utf-8")
    click.echo(
        f"Wrote {len(catalogue.questions)} questions to {output}. "
        f"Answer them, then run: complyscope assess --answers {output}"
    )


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
@click.option(
    "--answers",
    "answers_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default="answers.yaml",
    show_default=True,
    help="Questionnaire answers. Without it, questionnaire parts stay not assessed.",
)
def assess(scope_path: Path, evidence_path: Path, framework: str, answers_path: Path) -> None:
    """Judge controls against collected evidence and answers, and show the score."""
    scope, catalogue, results = _load_assessment(scope_path, evidence_path, framework, answers_path)
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
    "--register",
    "register_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default="risks.yaml",
    show_default=True,
    help="Risk register to create or update. Owner decisions in it are kept.",
)
@click.option(
    "--framework",
    "-f",
    default="cyber-essentials",
    show_default=True,
    help="Framework id to assess against.",
)
@click.option(
    "--answers",
    "answers_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default="answers.yaml",
    show_default=True,
    help="Questionnaire answers. Without it, questionnaire parts stay not assessed.",
)
def risks(
    scope_path: Path, evidence_path: Path, register_path: Path, framework: str, answers_path: Path
) -> None:
    """Draft risks from failed controls and update the risk register."""
    scope, catalogue, results = _load_assessment(scope_path, evidence_path, framework, answers_path)
    try:
        existing = load_register(register_path)
        register, changes = merge_register(
            existing,
            draft_risks(catalogue, results, today=date.today()),
            results,
            organisation=scope.organisation,
            framework=catalogue.id,
        )
    except RegisterError as e:
        raise click.BadParameter(str(e), param_hint="--register") from e
    write_register(register_path, register)

    click.echo(f"Risk register for {scope.organisation} ({catalogue.name}): {register_path}")
    for label, ids in [
        ("Added", changes.added),
        ("Reopened", changes.reopened),
        ("No longer failing (review for closure)", changes.no_longer_failing),
        ("Could not be reassessed", changes.not_reassessed),
    ]:
        if ids:
            click.echo(f"{label}: {', '.join(ids)}")

    open_risks = sorted(
        (r for r in register.risks if r.status.value == "open"), key=lambda r: (-r.score, r.id)
    )
    if not open_risks:
        click.echo("\nNo open risks.")
        return
    click.echo()
    _echo_table(
        ("ID", "LEVEL", "SCORE", "OWNER", "TITLE"),
        [(r.id, r.level.value, str(r.score), r.owner or "-", r.title) for r in open_risks],
    )

    attention = [(r.id, r.needs_attention()) for r in open_risks if r.needs_attention()]
    if attention:
        click.echo("\nNeeds attention:")
        for risk_id, reasons in attention:
            click.echo(f"{risk_id}: {', '.join(reasons)}")
    above = sum(r.level not in ACCEPTABLE_LEVELS for r in open_risks)
    click.echo(f"\n{above} open risk(s) above the risk appetite (high or critical).")


def _load_assessment(
    scope_path: Path, evidence_path: Path, framework: str, answers_path: Path
) -> tuple[Scope, Framework, tuple[ControlResult, ...]]:
    try:
        assessment = load_assessment(scope_path, evidence_path, framework, answers_path)
    except AssessmentInputError as e:
        raise click.BadParameter(str(e), param_hint=f"--{e.source}") from e
    if assessment.answers is None:
        click.echo(f"No answers file ({answers_path}): questionnaire parts are not assessed.\n")
    return assessment.scope, assessment.framework, assessment.results


def _echo_table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header) - 1)]
    for row in [header, *rows]:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        click.echo("  ".join([*cells, row[-1]]))
