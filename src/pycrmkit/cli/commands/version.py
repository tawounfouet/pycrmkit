"""Version and installed capabilities command for PyCRMKit CLI."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import sys
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit import __version__
from pycrmkit.cli.console import console

EXTRAS = (
    ("cli", ("typer", "rich"), "Command-line interface & Rich terminal output"),
    ("sqlalchemy", ("sqlalchemy",), "SQLAlchemy 2.0 ORM & persistence adapter"),
    ("postgresql", ("sqlalchemy", "psycopg"), "PostgreSQL physical database driver"),
    ("migrations", ("alembic", "sqlalchemy"), "Alembic schema migrations runner"),
    ("fastapi", ("fastapi", "pydantic"), "FastAPI REST API integration & schemas"),
    ("django", ("django",), "Django 5.2 modulith PaaS integration"),
    ("drf", ("rest_framework",), "Django REST Framework serializers & views"),
    ("email", ("jinja2",), "Jinja2 templated email rendering"),
    ("resend", ("resend",), "Resend transactional email provider"),
)


def _check_extra(packages: tuple[str, ...]) -> tuple[bool, str]:
    versions = []
    all_ok = True
    for pkg in packages:
        spec = importlib.util.find_spec(pkg)
        if spec is None:
            all_ok = False
            versions.append(f"{pkg}: missing")
        else:
            try:
                ver = importlib.metadata.version(pkg)
                versions.append(f"{pkg}: {ver}")
            except importlib.metadata.PackageNotFoundError:
                versions.append(f"{pkg}: installed")
    return all_ok, ", ".join(versions)


def version_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Emit machine-readable JSON metadata."),
    ] = False,
) -> None:
    """Display PyCRMKit version, runtime environment, and installed capability extras."""
    extras_status = {}
    for extra_name, packages, description in EXTRAS:
        installed, details = _check_extra(packages)
        extras_status[extra_name] = {
            "installed": installed,
            "details": details,
            "description": description,
        }

    data = {
        "pycrmkit": {
            "version": __version__,
        },
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "extras": extras_status,
    }

    if json_output:
        print(json.dumps(data, indent=2))
        return

    # Rich formatted rendering
    banner = (
        f"[bold blue]PyCRMKit[/bold blue] [bold green]v{__version__}[/bold green] — "
        "Headless CRM Building Blocks for Python"
    )
    console.print(Panel(banner, border_style="blue"))

    # Runtime info
    console.print(f"[bold]Python:[/bold] {sys.version.split()[0]} ({platform.platform()})")
    console.print()

    # Capabilities Table
    table = Table(title="Installed Capabilities & Optional Extras", border_style="dim")
    table.add_column("Extra", style="bold cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Packages & Versions", style="dim")
    table.add_column("Scope")

    for extra_name, info in extras_status.items():
        status_badge = (
            "[bold green]INSTALLED[/bold green]"
            if info["installed"]
            else "[dim]NOT INSTALLED[/dim]"
        )
        table.add_row(
            extra_name,
            status_badge,
            str(info["details"]),
            str(info["description"]),
        )

    console.print(table)
