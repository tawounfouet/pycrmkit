"""Feature tours execution command for PyCRMKit CLI.

Tours are loaded from trusted package resources, not from the current
repository's examples/ directory.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer
from rich.table import Table

from pycrmkit import __version__
from pycrmkit._feature_tours_loader import TOUR_FILES, run_tour
from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode

TOURS = [
    ("01_core_crm.py", "Core CRM Foundations (Entities, Relations, Tags, Custom Fields)"),
    ("02_sales_pipelines.py", "Sales Pipelines & Conversions (Pipelines, Stages, Opportunities)"),
    ("03_events_and_webhooks.py", "Events, Audit Logs & Webhooks (Dispatches, Secrets, Retries)"),
    ("04_data_operations.py", "Data Operations & Quality (CSV Ingestion, Deduplication, Merge)"),
    ("05_segmentation_queries.py", "Segmentation & Saved Queries (Static, Dynamic, Snapshots)"),
    ("06_campaigns_v1_2.py", "Campaigns v1.2.0 & Linkage (Audience, Concurrency, Attribution)"),
]

assert tuple(name for name, _ in TOURS) == TOUR_FILES


def _load_and_run(filename: str) -> tuple[str, float, str]:
    start = time.perf_counter()
    try:
        run_tour(filename)
    except Exception as exc:  # noqa: BLE001 - report each tour separately
        return "FAIL", time.perf_counter() - start, str(exc)
    return "PASS", time.perf_counter() - start, ""


def tours_command(
    tour_filter: Annotated[
        str | None,
        typer.Option("--tour", "-t", help="Filter by tour index (e.g. 1, 01) or keyword."),
    ] = None,
) -> None:
    """Run six self-contained, in-memory PyCRMKit feature tours."""
    selected_tours: list[tuple[str, str]] = []
    for filename, desc in TOURS:
        if tour_filter:
            filt = tour_filter.strip().lower()
            if filt in filename.lower() or filt in desc.lower():
                selected_tours.append((filename, desc))
            elif filt.isdigit() and int(filt) == int(filename[:2]):
                selected_tours.append((filename, desc))
        else:
            selected_tours.append((filename, desc))

    if not selected_tours:
        console.print(f"[bold yellow]No tours matched filter:[/bold yellow] '{tour_filter}'")
        raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR))

    console.print(
        f"\\n[bold blue]Running {len(selected_tours)} PyCRMKit Feature Tour(s)[/bold blue] (v{__version__})...\\n"
    )

    results: list[tuple[str, str, str, float, str]] = []
    all_passed = True
    total_start = time.perf_counter()

    for filename, desc in selected_tours:
        with console.status(f"[cyan]Running {filename}...[/cyan]"):
            status, duration, error_msg = _load_and_run(filename)
        if status != "PASS":
            all_passed = False
        results.append((filename, desc, status, duration, error_msg))

    total_duration = time.perf_counter() - total_start
    table = Table(title="PyCRMKit Feature Tours - Execution Scorecard", border_style="dim")
    table.add_column("Script", style="bold cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Scope")

    for filename, desc, status, duration, _error_msg in results:
        label = (
            "[bold green]✓ PASS[/bold green]"
            if status == "PASS"
            else "[bold red]✗ FAIL[/bold red]"
        )
        table.add_row(filename, label, f"{duration:.3f}s", desc)

    console.print(table)
    console.print(f"[bold]Total Duration:[/bold] {total_duration:.3f}s")

    if not all_passed:
        for filename, _, status, _, error_msg in results:
            if status != "PASS":
                console.print(f"[red]{filename}: {error_msg}[/red]")
        console.print("[bold red]Some feature tours failed.[/bold red]")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE))
    console.print("[bold green]All feature tours passed successfully![/bold green]")
