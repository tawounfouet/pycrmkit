"""Main Typer application for PyCRMKit CLI."""

from __future__ import annotations

import typer

from pycrmkit import __version__
from pycrmkit.cli.commands.campaigns import campaigns_app
from pycrmkit.cli.commands.contacts import contacts_app
from pycrmkit.cli.commands.dashboard import dashboard_command
from pycrmkit.cli.commands.doctor import doctor_command
from pycrmkit.cli.commands.migrate import migrate_app
from pycrmkit.cli.commands.orgs import orgs_app
from pycrmkit.cli.commands.sales import sales_app
from pycrmkit.cli.commands.seed import reset_command, seed_command
from pycrmkit.cli.commands.tasks import tasks_app
from pycrmkit.cli.commands.tours import tours_command
from pycrmkit.cli.commands.version import version_command
from pycrmkit.cli.console import console

app = typer.Typer(
    name="pck",
    help="PyCRMKit - Headless CRM building blocks for Python applications.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

# Register top-level executive commands
app.command(
    name="dashboard",
    help="Executive CRM Command Center: KPI cards, visual sales funnel, campaigns, and action items.",
)(dashboard_command)
app.command(
    name="seed",
    help="Seed the local CRM store with realistic B2B enterprise demonstration data.",
)(seed_command)
app.command(
    name="reset",
    help="Clear the local CRM state file and reset storage.",
)(reset_command)

# Diagnostics and information
app.command(
    name="version",
    help="Show PyCRMKit version, runtime environment, and installed capability extras.",
)(version_command)
app.command(
    name="doctor",
    help="Run system diagnostics, environment variables audit, and in-memory engine smoke check.",
)(doctor_command)
app.command(
    name="tours",
    help="Execute the autonomous feature tours suite with Rich scorecard reporting.",
)(tours_command)
app.command(
    name="demo",
    help="Alias for tours: run feature tours demonstration.",
)(tours_command)

# Register domain sub-apps
app.add_typer(contacts_app)
app.add_typer(orgs_app)
app.add_typer(sales_app)
app.add_typer(campaigns_app)
app.add_typer(tasks_app)
app.add_typer(migrate_app)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold blue]PyCRMKit[/bold blue] [bold green]v{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """PyCRMKit command-line interface."""
