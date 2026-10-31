"""Campaigns management commands for PyCRMKit CLI (v1.2.0 domain)."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit.campaigns import CampaignId, CampaignQuery, CampaignStatus
from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import InvalidStateError, NotFoundError, ValidationError

campaigns_app = typer.Typer(
    name="campaigns",
    help="Manage multi-channel campaigns, target audiences, and activations.",
    no_args_is_help=True,
)


def _resolve_campaign_id(crm, key_or_id: str) -> CampaignId:
    """Resolve a campaign by UUID or slug key."""
    if len(key_or_id) == 36 and "-" in key_or_id:
        try:
            return CampaignId(key_or_id)
        except (ValueError, TypeError):
            pass

    # Search by key or prefix
    page = crm.campaigns.list(page=OffsetPageRequest(limit=100))
    for camp in page.items:
        if camp.key == key_or_id.lower() or str(camp.id).startswith(key_or_id):
            return camp.id

    raise NotFoundError(f"Campaign with key or ID '{key_or_id}' not found.")


@campaigns_app.command("list")
def list_campaigns(
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status", "-s", help="Filter by status (draft, active, completed, archived)"
        ),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of campaigns to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List marketing campaigns with audience reach, status, and budget."""
    query = CampaignQuery()
    if status_filter:
        try:
            query = query.with_status(CampaignStatus(status_filter.lower()))
        except ValueError:
            console.print(
                f"[bold red]Unknown status:[/bold red] '{status_filter}'. Allowed: draft, active, completed, archived."
            )
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from None

    with get_crm_context(save=False) as crm:
        page = crm.campaigns.list(query=query, page=OffsetPageRequest(limit=limit, offset=offset))
        if not page.items:
            console.print(
                "[yellow]No campaigns found. Use 'pck campaigns create' or 'pck seed' to add campaigns.[/yellow]"
            )
            return

        table = Table(title=f"Campaigns Directory ({page.total} total)", border_style="dim")
        table.add_column("Key / Slug", style="bold cyan")
        table.add_column("Name", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Audience", justify="right", style="green")
        table.add_column("Budget", justify="right", style="yellow")
        table.add_column("Starts", style="dim")
        table.add_column("Ends", style="dim")

        for camp in page.items:
            reach = crm.campaigns.audience_count(camp.id)
            budget = camp.metadata.get("budget_allocated")
            budget_str = f"{budget:,.0f} €" if isinstance(budget, (int, float)) else "-"
            starts_str = camp.starts_at.strftime("%Y-%m-%d") if camp.starts_at else "-"
            ends_str = camp.ends_at.strftime("%Y-%m-%d") if camp.ends_at else "-"

            status_style = {
                CampaignStatus.DRAFT: "[dim]DRAFT[/dim]",
                CampaignStatus.ACTIVE: "[bold green]ACTIVE[/bold green]",
                CampaignStatus.COMPLETED: "[blue]COMPLETED[/blue]",
                CampaignStatus.ARCHIVED: "[dim red]ARCHIVED[/dim red]",
            }.get(camp.status, str(camp.status.value))

            table.add_row(
                camp.key,
                camp.name,
                status_style,
                str(reach),
                budget_str,
                starts_str,
                ends_str,
            )

    console.print(table)


@campaigns_app.command("create")
def create_campaign(
    key: Annotated[str, typer.Argument(help="Unique slug key (e.g. q4-executive-briefing)")],
    name: Annotated[str, typer.Argument(help="Campaign human title")],
    description: Annotated[
        str | None, typer.Option("--desc", "-d", help="Campaign objective")
    ] = None,
    budget: Annotated[
        float | None, typer.Option("--budget", "-b", help="Allocated budget amount")
    ] = None,
) -> None:
    """Create a new campaign in draft status."""
    meta = {}
    if budget is not None:
        meta["budget_allocated"] = budget

    with get_crm_context(save=True) as crm:
        try:
            camp = crm.campaigns.create(
                key=key,
                name=name,
                description=description,
                metadata=meta,
            )
        except (ValidationError, ValueError) as exc:
            console.print(f"[bold red]Validation error:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc
        except Exception as exc:
            console.print(f"[bold red]Failed to create campaign:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Campaign Created (Draft)[/bold green]\n\n"
            f"[bold]ID:[/bold] {camp.id}\n"
            f"[bold]Key:[/bold] [cyan]{camp.key}[/cyan]\n"
            f"[bold]Name:[/bold] {camp.name}\n"
            f"[bold]Status:[/bold] {camp.status.value.upper()}\n"
            f"[bold]Budget:[/bold] {budget or '<unspecified>'}",
            border_style="green",
        )
    )


@campaigns_app.command("activate")
def activate_campaign(
    campaign: Annotated[str, typer.Argument(help="Campaign key or UUID")],
) -> None:
    """Activate a draft campaign to begin member engagement."""
    with get_crm_context(save=True) as crm:
        try:
            cid = _resolve_campaign_id(crm, campaign)
            updated = crm.campaigns.activate(cid)
        except NotFoundError as exc:
            console.print(f"[bold red]Not found:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc
        except InvalidStateError as exc:
            console.print(f"[bold red]Invalid state transition:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Campaign Activated[/bold green]\n\n"
            f"[bold]Key:[/bold] {updated.key}\n"
            f"[bold]Name:[/bold] {updated.name}\n"
            f"[bold]Status:[/bold] [bold green]ACTIVE[/bold green]\n"
            f"[bold]Revision:[/bold] {updated.revision}",
            border_style="green",
        )
    )


@campaigns_app.command("complete")
def complete_campaign(
    campaign: Annotated[str, typer.Argument(help="Campaign key or UUID")],
) -> None:
    """Mark an active campaign as successfully completed."""
    with get_crm_context(save=True) as crm:
        try:
            cid = _resolve_campaign_id(crm, campaign)
            updated = crm.campaigns.complete(cid)
        except NotFoundError as exc:
            console.print(f"[bold red]Not found:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc
        except InvalidStateError as exc:
            console.print(f"[bold red]Invalid state transition:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Campaign Completed[/bold green]\n\n"
            f"[bold]Key:[/bold] {updated.key}\n"
            f"[bold]Name:[/bold] {updated.name}\n"
            f"[bold]Status:[/bold] [bold blue]COMPLETED[/bold blue]\n"
            f"[bold]Revision:[/bold] {updated.revision}",
            border_style="blue",
        )
    )


@campaigns_app.command("audience")
def show_audience(
    campaign: Annotated[str, typer.Argument(help="Campaign key or UUID")],
) -> None:
    """List members and target audience enrolled in a campaign."""
    with get_crm_context(save=False) as crm:
        try:
            cid = _resolve_campaign_id(crm, campaign)
            camp = crm.campaigns.get(cid)
            page = crm.campaigns.members(cid, page=OffsetPageRequest(limit=100))
        except NotFoundError as exc:
            console.print(f"[bold red]Not found:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    if not page.items:
        console.print(f"[yellow]No audience members enrolled in campaign '{camp.key}'.[/yellow]")
        return

    table = Table(
        title=f"Audience Members for '{camp.name}' ({page.total} enrolled)", border_style="dim"
    )
    table.add_column("Type", style="cyan")
    table.add_column("Entity ID", style="dim", no_wrap=True)
    table.add_column("Enrolled Source", style="green")

    for member in page.items:
        table.add_row(
            member.entity.kind.capitalize(),
            str(member.entity.id)[:18] + "...",
            member.source or "-",
        )

    console.print(table)
