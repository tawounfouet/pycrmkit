"""Feature tours execution command for PyCRMKit CLI."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from pycrmkit import __version__
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


def _load_and_run(script_path: Path) -> tuple[str, float, str]:
    t0 = time.perf_counter()
    module_name = f"tour_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    if spec is None or spec.loader is None:
        return "FAIL", 0.0, f"Cannot load spec for {script_path}"

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        if hasattr(module, "run_tour"):
            module.run_tour()
        else:
            return "FAIL", 0.0, "Missing run_tour() entrypoint"
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        return "FAIL", elapsed, str(exc)

    elapsed = time.perf_counter() - t0
    return "PASS", elapsed, ""


def tours_command(
    tour_filter: Annotated[
        str | None,
        typer.Option("--tour", "-t", help="Filter by tour index (e.g. 1, 01) or keyword."),
    ] = None,
) -> None:
    """Run autonomous, in-memory PyCRMKit feature tours with Rich scorecard reporting."""
    # Resolve examples/feature_tours relative to repo root or package root
    repo_root = Path(__file__).resolve().parents[4]
    tours_dir = repo_root / "examples" / "feature_tours"

    selected_tours = []
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
        f"\n[bold blue]Running {len(selected_tours)} PyCRMKit Feature Tour(s)[/bold blue] (v{__version__})...\n"
    )

    results = []
    all_passed = True
    total_start = time.perf_counter()

    for filename, desc in selected_tours:
        script_file = tours_dir / filename
        if not script_file.is_file():
            results.append((filename, desc, "FAIL", 0.0, "File not found"))
            all_passed = False
            continue

        with console.status(f"[cyan]Running {filename}...[/cyan]"):
            status, duration, error_msg = _load_and_run(script_file)

        if status != "PASS":
            all_passed = False

        results.append((filename, desc, status, duration, error_msg))

    total_duration = time.perf_counter() - total_start

    # Scorecard
    table = Table(title="PyCRMKit Feature Tours — Execution Scorecard", border_style="dim")
    table.add_column("Script", style="bold cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Scope")

    for filename, desc, status, duration, _error_msg in results:
        status_badge = (
            "[bold green]✓ PASS[/bold green]" if status == "PASS" else "[bold red]✗ FAIL[/bold red]"
        )
        table.add_row(
            filename,
            status_badge,
            f"{duration:.3f}s",
            desc,
        )

    console.print(table)
    console.print(f"[bold]Total Duration:[/bold] {total_duration:.3f}s")

    if not all_passed:
        console.print("\n[bold red]Some feature tours failed.[/bold red]")
        raise typer.Exit(code=int(ExitCode.EXECUTION_FAILURE))

    console.print("\n[bold green]All feature tours passed successfully![/bold green]")
