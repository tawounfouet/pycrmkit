"""Environment diagnostics and system health check command for PyCRMKit CLI."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit import CRM, __version__
from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode


def _redact_value(value: str | None) -> str:
    if not value:
        return "[dim]<not set>[/dim]"
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}...{value[-3:]}"


def doctor_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Emit machine-readable JSON health report."),
    ] = False,
) -> None:
    """Run comprehensive diagnostics on environment, configuration, and CRM in-memory engine."""
    checks: list[dict[str, object]] = []

    # 1. Configuration & Dotenv Discovery
    from pycrmkit.cli.config import find_config_file, find_dotenv_file, resolve_database_url

    cfg_file = find_config_file()
    checks.append(
        {
            "category": "Configuration",
            "name": "Config File (YAML)",
            "status": "PASS" if cfg_file else "INFO",
            "details": f"{cfg_file.name} ({cfg_file})" if cfg_file else "<none> (using environment or defaults)",
        }
    )

    dot_file = find_dotenv_file()
    checks.append(
        {
            "category": "Configuration",
            "name": "Environment File (.env)",
            "status": "PASS" if dot_file else "INFO",
            "details": f"{dot_file.name} ({dot_file})" if dot_file else "<none> (using process environment)",
        }
    )

    # 2. Python version check
    py_ver = sys.version_info
    py_supported = (3, 11) <= (py_ver.major, py_ver.minor) < (3, 15)
    checks.append(
        {
            "category": "Runtime",
            "name": "Python Version",
            "status": "PASS" if py_supported else "WARNING",
            "details": f"{platform.python_version()} (Supported: 3.11 - 3.14)",
        }
    )

    # 3. In-Memory Core Engine Smoke Test
    in_memory_healthy = True
    in_memory_detail = "In-memory UnitOfWork, Contact and Organization operational"
    try:
        crm = CRM.memory().with_context(actor_id="cli-doctor")
        org = crm.organizations.create(legal_name="Doctor Diagnostic Org", source="cli-doctor")
        c = crm.contacts.create(first_name="Doctor", last_name="Check", source="cli-doctor")
        assert org.id is not None
        assert c.id is not None
    except Exception as exc:  # noqa: BLE001
        in_memory_healthy = False
        in_memory_detail = f"Failed: {exc}"

    checks.append(
        {
            "category": "Engine",
            "name": "In-Memory CRM Core",
            "status": "PASS" if in_memory_healthy else "FAIL",
            "details": in_memory_detail,
        }
    )

    # 4. Environment & Secrets Check
    resolved_db_url, db_source = resolve_database_url()
    env_vars = (
        ("DATABASE_URL", "PostgreSQL database connection URI", resolved_db_url, db_source),
        ("CRM_SIGNING_SECRET", "HMAC webhook verification secret", os.getenv("CRM_SIGNING_SECRET"), "env"),
        ("RESEND_API_KEY", "Resend email provider API key", os.getenv("RESEND_API_KEY"), "env"),
        ("CRM_ACTOR_ID", "Default audit trail actor identifier", os.getenv("CRM_ACTOR_ID"), "env"),
    )
    for var_name, var_desc, val, source in env_vars:
        checks.append(
            {
                "category": "Environment",
                "name": var_name,
                "status": "SET" if val else "NOT SET",
                "details": f"{_redact_value(val)} ({var_desc})" + (f" [{source}]" if val else ""),
            }
        )

    # 5. Storage & Migrations assets check
    migrations_dir = Path.cwd() / "migrations"
    alembic_ini = Path.cwd() / "alembic.ini"
    checks.append(
        {
            "category": "Storage",
            "name": "Migrations Workspace",
            "status": "FOUND" if (migrations_dir.is_dir() or alembic_ini.is_file()) else "INFO",
            "details": "Alembic migrations configuration present in workspace"
            if alembic_ini.is_file()
            else "No local alembic.ini (using memory or custom config)",
        }
    )

    # 6. Live PostgreSQL connectivity check (if URL available)
    if resolved_db_url:
        try:
            from sqlalchemy import create_engine, inspect, text

            test_engine = create_engine(resolved_db_url, pool_pre_ping=True)
            with test_engine.connect() as conn:
                inspector = inspect(conn)
                table_count = len(inspector.get_table_names())
                pg_ver = conn.execute(text("SHOW server_version;")).scalar() or "Unknown"
            checks.append(
                {
                    "category": "Storage",
                    "name": "PostgreSQL Live Ping",
                    "status": "PASS",
                    "details": f"Connected to server {pg_ver} ({table_count} tables detected)",
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                {
                    "category": "Storage",
                    "name": "PostgreSQL Live Ping",
                    "status": "WARNING",
                    "details": f"Connection check failed: {exc}",
                }
            )

    overall_healthy = in_memory_healthy and py_supported

    if json_output:
        report = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "pycrmkit_version": __version__,
            "checks": checks,
        }
        print(json.dumps(report, indent=2))
        return

    # Rich Terminal Output
    status_style = "bold green" if overall_healthy else "bold red"
    status_text = "SYSTEM HEALTHY" if overall_healthy else "ISSUES DETECTED"
    console.print(
        Panel(
            f"[{status_style}]PyCRMKit Doctor Diagnostic — {status_text}[/{status_style}]",
            border_style="blue",
        )
    )

    table = Table(title="Diagnostic Checks Summary", border_style="dim")
    table.add_column("Category", style="bold cyan")
    table.add_column("Check")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    for check in checks:
        st = str(check["status"])
        if st in ("PASS", "FOUND"):
            badge = "[bold green]✓ PASS[/bold green]"
        elif st == "SET":
            badge = "[bold cyan]SET[/bold cyan]"
        elif st in ("WARNING", "NOT SET", "INFO"):
            badge = f"[yellow]{st}[/yellow]"
        else:
            badge = f"[bold red]✗ {st}[/bold red]"

        table.add_row(
            str(check["category"]),
            str(check["name"]),
            badge,
            str(check["details"]),
        )

    console.print(table)

    if not overall_healthy:
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))
