"""Demo data seeding and state reset commands for PyCRMKit CLI."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit.cli.console import console
from pycrmkit.cli.state import _resolve_store_path, get_crm_context, seed_demo_data


def seed_command() -> None:
    """Seed the local CRM state with a realistic enterprise B2B scenario."""
    with get_crm_context(save=True) as crm:
        counts = seed_demo_data(crm)

    table = Table(title="Demo Enterprise Scenario Loaded", border_style="green")
    table.add_column("Domain Aggregate", style="bold cyan")
    table.add_column("Entities Seeded", justify="right", style="bold green")

    table.add_row("Corporate Accounts & Organizations", str(counts["organizations"]))
    table.add_row("Contacts & Multi-channel Channels", str(counts["contacts"]))
    table.add_row("B2B Pipeline & Deals", str(counts["opportunities"]))
    table.add_row("Campaigns (v1.2.0) & Audiences", str(counts["campaigns"]))
    table.add_row("Operational Action Items & Tasks", str(counts["tasks"]))

    console.print(table)
    console.print(
        "\n[dim]Tip: Run [bold]pck dashboard[/bold] to explore the executive CRM overview.[/dim]\n"
    )


def reset_command(
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
) -> None:
    """Reset the local CRM state file and clear all stored records."""
    target = _resolve_store_path()
    if not target.exists():
        console.print("[dim]Local CRM store is already empty (no state file found).[/dim]")
        return

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete the local CRM state at {target}?")
        if not confirm:
            console.print("[yellow]Reset cancelled.[/yellow]")
            return

    target.unlink(missing_ok=True)
    console.print(
        Panel(
            f"[bold green]✓ CRM State Successfully Cleared[/bold green]\n\n"
            f"Removed store file: [dim]{target}[/dim]\n"
            f"Run [bold]pck seed[/bold] or create entities to initialize a new dataset.",
            border_style="green",
        )
    )
