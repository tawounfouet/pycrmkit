"""Database migrations commands for PyCRMKit CLI."""

from __future__ import annotations

import importlib.util
from typing import Annotated

import typer

from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode

migrate_app = typer.Typer(
    name="migrate",
    help="Manage PostgreSQL database schema migrations via Alembic.",
    no_args_is_help=True,
)


def _ensure_migrations_installed() -> None:
    if importlib.util.find_spec("alembic") is None:
        console.print(
            "[bold red]Alembic is not installed.[/bold red]\n"
            'Install migrations extra via: [cyan]pip install "pycrmkit[migrations]"[/cyan]'
        )
        raise typer.Exit(code=int(ExitCode.MISSING_OPTIONAL_DEPENDENCY))


@migrate_app.command("upgrade")
def upgrade_command(
    revision: Annotated[str, typer.Argument(help="Target revision or 'head'")] = "head",
    database_url: Annotated[
        str | None, typer.Option("--database-url", "-d", help="Database connection URL")
    ] = None,
) -> None:
    """Upgrade database schema to the specified revision or head."""
    _ensure_migrations_installed()
    from pycrmkit.storage.sqlalchemy.migrations.cli import main as migrate_main

    args = ["upgrade", revision]
    if database_url:
        args.extend(["--database-url", database_url])

    try:
        migrate_main(args)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Migration upgrade failed:[/bold red] {exc}")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE)) from exc


@migrate_app.command("downgrade")
def downgrade_command(
    revision: Annotated[str, typer.Argument(help="Target revision to downgrade to")],
    database_url: Annotated[
        str | None, typer.Option("--database-url", "-d", help="Database connection URL")
    ] = None,
) -> None:
    """Downgrade database schema to a previous revision."""
    _ensure_migrations_installed()
    from pycrmkit.storage.sqlalchemy.migrations.cli import main as migrate_main

    args = ["downgrade", revision]
    if database_url:
        args.extend(["--database-url", database_url])

    try:
        migrate_main(args)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Migration downgrade failed:[/bold red] {exc}")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE)) from exc


@migrate_app.command("check")
def check_command(
    database_url: Annotated[
        str | None, typer.Option("--database-url", "-d", help="Database connection URL")
    ] = None,
) -> None:
    """Check if the database schema is up-to-date with current migrations."""
    _ensure_migrations_installed()
    from pycrmkit.storage.sqlalchemy.migrations.cli import main as migrate_main

    args = ["check"]
    if database_url:
        args.extend(["--database-url", database_url])

    try:
        migrate_main(args)
        console.print("[bold green]Database schema is up-to-date.[/bold green]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Migration check failed:[/bold red] {exc}")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE)) from exc


@migrate_app.command("current")
def current_command(
    database_url: Annotated[
        str | None, typer.Option("--database-url", "-d", help="Database connection URL")
    ] = None,
) -> None:
    """Display the current revision applied to the database."""
    _ensure_migrations_installed()
    from pycrmkit.storage.sqlalchemy.migrations.cli import main as migrate_main

    args = ["current"]
    if database_url:
        args.extend(["--database-url", database_url])

    try:
        migrate_main(args)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Migration current failed:[/bold red] {exc}")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE)) from exc
