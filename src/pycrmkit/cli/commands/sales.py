"""Sales pipelines and commercial opportunities commands for PyCRMKit CLI."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context, query_opportunities
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import InvalidStateError, NotFoundError, ValidationError
from pycrmkit.opportunities import OpportunityId, OpportunityStatus
from pycrmkit.opportunities.queries import OpportunityQuery
from pycrmkit.organizations import OrganizationId
from pycrmkit.pipelines.transitions import InvalidStageTransition

sales_app = typer.Typer(
    name="sales",
    help="Manage commercial pipelines, stages, and deal opportunities.",
    no_args_is_help=True,
)


@sales_app.command("pipelines")
def list_pipelines(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of pipelines to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List commercial sales pipelines and their ordered stages."""
    with get_crm_context(save=False) as crm:
        page = crm.pipelines.list(page=OffsetPageRequest(limit=limit, offset=offset))

    if not page.items:
        console.print(
            "[yellow]No pipelines defined. Run 'pck seed' to load default enterprise pipelines.[/yellow]"
        )
        return

    table = Table(title=f"Sales Pipelines ({page.total} total)", border_style="dim")
    table.add_column("Pipeline ID", style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Initial Stage", style="green")
    table.add_column("Stages & Probabilities", style="dim")

    for p in page.items:
        stages_summary = " ➔ ".join(
            f"{s.name} ({s.default_probability * 100:.0f}%)"
            if s.default_probability is not None
            else s.name
            for s in p.stages
        )
        table.add_row(
            p.id,
            p.name,
            p.initial_stage.name if p.initial_stage else "-",
            stages_summary,
        )

    console.print(table)


@sales_app.command("opps")
def list_opportunities(
    stage: Annotated[str | None, typer.Option("--stage", "-s", help="Filter by stage ID")] = None,
    status_filter: Annotated[
        str | None, typer.Option("--status", help="Filter by status (open, won, lost)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of deals to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List deal opportunities, stage progressions, and weighted values."""
    query = OpportunityQuery()
    if stage:
        query = query.in_stage(stage)
    if status_filter:
        try:
            query = query.with_status(OpportunityStatus(status_filter.lower()))
        except ValueError:
            console.print(
                f"[bold red]Unknown status:[/bold red] '{status_filter}'. Allowed: open, won, lost, cancelled."
            )
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from None

    with get_crm_context(save=False) as crm:
        page = query_opportunities(
            crm, query=query, page=OffsetPageRequest(limit=limit, offset=offset)
        )

    if not page.items:
        console.print(
            "[yellow]No opportunities found matching criteria. Use 'pck seed' to create demo deals.[/yellow]"
        )
        return

    table = Table(title=f"Deals & Opportunities ({page.total} total)", border_style="dim")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Deal Name", style="bold cyan")
    table.add_column("Stage", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Est. Value", justify="right", style="green")
    table.add_column("Prob", justify="right")
    table.add_column("Weighted", justify="right", style="bold green")

    for opp in page.items:
        val = (
            f"{opp.estimated_value:,.2f} {opp.currency}" if opp.estimated_value is not None else "-"
        )
        prob_pct = f"{opp.probability * 100:.0f}%" if opp.probability is not None else "-"
        weighted = (
            f"{(opp.estimated_value * opp.probability):,.2f} {opp.currency}"
            if opp.estimated_value is not None and opp.probability is not None
            else "-"
        )

        status_style = {
            OpportunityStatus.OPEN: "[cyan]OPEN[/cyan]",
            OpportunityStatus.WON: "[bold green]WON[/bold green]",
            OpportunityStatus.LOST: "[bold red]LOST[/bold red]",
            OpportunityStatus.CANCELLED: "[dim]CANCELLED[/dim]",
        }.get(opp.status, str(opp.status.value))

        table.add_row(
            str(opp.id)[:8] + "...",
            opp.name,
            opp.stage_id or "-",
            status_style,
            val,
            prob_pct,
            weighted,
        )

    console.print(table)


@sales_app.command("move")
def move_opportunity(
    opp_id: Annotated[str, typer.Argument(help="Opportunity UUID or prefix")],
    target_stage: Annotated[
        str, typer.Argument(help="Target stage slug/id (e.g. demo, proposal, won, lost)")
    ],
) -> None:
    """Transition an opportunity to a target stage respecting pipeline transition rules."""
    clean_opp = opp_id.strip().rstrip(".")
    with get_crm_context(save=True) as crm:
        # Resolve opportunity UUID prefix if short id provided
        resolved_id: OpportunityId | None = None
        if len(clean_opp) < 36:
            page = query_opportunities(crm)
            for item in page.items:
                if str(item.id).startswith(clean_opp):
                    resolved_id = item.id
                    break
            if resolved_id is None:
                console.print(f"[bold red]Opportunity prefix '{opp_id}' not found.[/bold red]")
                raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))
        else:
            try:
                resolved_id = OpportunityId(clean_opp)
            except Exception as exc:
                console.print(f"[bold red]Invalid opportunity UUID:[/bold red] {exc}")
                raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc

        try:
            updated = crm.opportunities.move(resolved_id, to=target_stage)
        except InvalidStageTransition as exc:
            console.print(f"[bold red]Invalid Pipeline Transition:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc
        except (NotFoundError, InvalidStateError) as exc:
            console.print(f"[bold red]Transition failed:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    status_str = (
        f"[bold green]{updated.status.value.upper()}[/bold green]"
        if updated.status == OpportunityStatus.WON
        else f"[bold]{updated.status.value.upper()}[/bold]"
    )
    prob_str = f"{updated.probability * 100:.0f}%" if updated.probability is not None else "-"
    console.print(
        Panel(
            f"[bold green]✓ Deal Advanced Successfully[/bold green]\n\n"
            f"[bold]Deal:[/bold] {updated.name} ({updated.id})\n"
            f"[bold]New Stage:[/bold] [magenta]{updated.stage_id}[/magenta]\n"
            f"[bold]Status:[/bold] {status_str}\n"
            f"[bold]Probability:[/bold] {prob_str}",
            border_style="green",
        )
    )


@sales_app.command("create")
def create_opportunity(
    name: Annotated[str, typer.Argument(help="Deal / Opportunity title")],
    contact_id: Annotated[str, typer.Option("--contact", "-c", help="Primary contact UUID")],
    org_id: Annotated[
        str | None, typer.Option("--org", "-o", help="Associated organization UUID")
    ] = None,
    pipeline_id: Annotated[
        str, typer.Option("--pipeline", "-p", help="Pipeline ID")
    ] = "b2b-enterprise",
    stage_id: Annotated[
        str | None,
        typer.Option("--stage", "-s", help="Initial stage ID (defaults to pipeline start)"),
    ] = None,
    value: Annotated[
        float | None, typer.Option("--value", "-v", help="Estimated deal value")
    ] = None,
    currency: Annotated[str, typer.Option("--currency", help="Currency code")] = "EUR",
) -> None:
    """Create a new commercial deal in a pipeline."""
    with get_crm_context(save=True) as crm:
        try:
            cid = ContactId(contact_id)
            oid = OrganizationId(org_id) if org_id else None
            est_val = Decimal(str(value)) if value is not None else None

            opp = crm.opportunities.create(
                name=name,
                contact_id=cid,
                organization_id=oid,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                estimated_value=est_val,
                currency=currency,
            )
        except (ValidationError, ValueError) as exc:
            console.print(f"[bold red]Validation error:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc
        except Exception as exc:
            console.print(f"[bold red]Failed to create deal:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Deal Created Successfully[/bold green]\n\n"
            f"[bold]ID:[/bold] {opp.id}\n"
            f"[bold]Name:[/bold] {opp.name}\n"
            f"[bold]Pipeline:[/bold] {opp.pipeline_id}\n"
            f"[bold]Stage:[/bold] {opp.stage_id}\n"
            f"[bold]Value:[/bold] {opp.estimated_value} {opp.currency}",
            border_style="green",
        )
    )
