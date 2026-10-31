"""Executive CRM Dashboard command for PyCRMKit CLI."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import nullcontext
from decimal import Decimal
from typing import Annotated

import typer
from rich.columns import Columns
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from pycrmkit import CRM, __version__
from pycrmkit.campaigns import CampaignStatus
from pycrmkit.cli.console import console
from pycrmkit.cli.state import (
    get_crm_context,
    get_database_url,
    query_opportunities,
    seed_demo_data,
)
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.opportunities import Opportunity, OpportunityStatus
from pycrmkit.tasks import TaskPriority, TaskStatus


def _format_currency(value: Decimal | float, currency: str = "EUR") -> str:
    symbol = "€" if currency == "EUR" else f"{currency} "
    return f"{value:,.2f} {symbol}".strip()


def _sum_by_currency(
    opportunities: Iterable[Opportunity],
    *,
    weighted: bool = False,
) -> dict[str, Decimal]:
    """Sum monetary amounts by currency, without fictitious FX conversion."""
    amounts: dict[str, Decimal] = {}
    for opportunity in opportunities:
        if opportunity.estimated_value is None:
            continue
        currency = opportunity.currency or "UNKNOWN"
        factor = (
            opportunity.probability if opportunity.probability is not None else Decimal(0)
        ) if weighted else Decimal(1)
        amounts[currency] = (
            amounts.get(currency, Decimal(0)) + opportunity.estimated_value * factor
        )
    return amounts


def _display_amounts(amounts: dict[str, Decimal]) -> str:
    """Keep multiple currencies separate and missing values distinct from zero."""
    if not amounts:
        return "N/A (no priced deals)"
    return " | ".join(
        _format_currency(value, currency) for currency, value in sorted(amounts.items())
    )


def _render_bar(percentage: float, width: int = 20) -> str:
    """Render a proportional Unicode block bar chart."""
    clamped = max(0.0, min(1.0, percentage))
    filled = int(round(clamped * width))
    empty = width - filled
    return "█" * filled + "░" * empty


def dashboard_command(
    demo: Annotated[
        bool, typer.Option("--demo", "-d", help="Automatically seed demo data if store is empty")
    ] = False,
) -> None:
    """Executive CRM Command Center: KPI cards, visual sales funnel, campaigns, and action items."""
    # --demo always uses an ephemeral CRM, even when PostgreSQL is configured.
    context = nullcontext(CRM.memory()) if demo else get_crm_context(save=False)
    with context as crm:
        # Check if store has records
        contact_page = crm.contacts.search(page=OffsetPageRequest(limit=1))
        opp_page = query_opportunities(crm, page=OffsetPageRequest(limit=100))

        if contact_page.total == 0 and opp_page.total == 0:
            if demo:
                seed_demo_data(crm)
            else:
                console.print(
                    Panel(
                        "[bold yellow]Your PyCRMKit database is currently empty.[/bold yellow]\n\n"
                        "Run with [bold cyan]--demo[/bold cyan] or execute [bold cyan]pck seed[/bold cyan] "
                        "to initialize the realistic B2B enterprise demonstration dataset.",
                        title="Welcome to PyCRMKit",
                        border_style="yellow",
                    )
                )
                return

        # Fetch aggregated metrics across all core domains
        contacts_total = crm.contacts.search(page=OffsetPageRequest(limit=1)).total
        orgs_total = crm.organizations.search(page=OffsetPageRequest(limit=1)).total
        opportunity_page = query_opportunities(crm, page=OffsetPageRequest(limit=100))
        campaign_page = crm.campaigns.list(page=OffsetPageRequest(limit=50))
        task_page = crm.tasks.list(page=OffsetPageRequest(limit=50))
        opps = opportunity_page.items
        campaigns = campaign_page.items
        tasks = task_page.items
        activities = crm.activities.list(page=OffsetPageRequest(limit=10)).items
        is_partial = (
            opportunity_page.total > len(opps)
            or campaign_page.total > len(campaigns)
            or task_page.total > len(tasks)
        )

        # 1. Pipeline & Deal Calculations
        open_opps = [o for o in opps if o.status == OpportunityStatus.OPEN]
        won_opps = [o for o in opps if o.status == OpportunityStatus.WON]
        lost_opps = [o for o in opps if o.status == OpportunityStatus.LOST]

        active_pipeline_val = _display_amounts(_sum_by_currency(open_opps))
        weighted_forecast_val = _display_amounts(
            _sum_by_currency(open_opps, weighted=True)
        )
        won_val = _display_amounts(_sum_by_currency(won_opps))

        total_closed = len(won_opps) + len(lost_opps)
        win_rate = (len(won_opps) / total_closed * 100) if total_closed > 0 else 0.0

        # 2. Campaigns Reach
        total_audience_reach = sum(crm.campaigns.audience_count(c.id) for c in campaigns)

        # 3. Action Items Pending
        open_tasks = [t for t in tasks if t.status in (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)]

        # --- HEADER BANNER ---
        db_url = None if demo else get_database_url()
        if demo:
            mode_text = "  •  Mode: Ephemeral demo (no persistence)\n"
        elif db_url:
            mode_text = "  •  Mode: configured database (connection details redacted)\n"
        else:
            mode_text = "  •  Mode: Headless In-Memory / Local State\n"

        header_text = Text()
        header_text.append("🏢 PyCRMKit Executive Command Center", style="bold cyan")
        header_text.append(f"  •  v{__version__}", style="dim")
        header_text.append(mode_text, style="dim green")
        header_text.append(
            "Observed read-only CRM snapshot; not a complete Customer 360 read model", style="italic white"
        )
        console.print(Panel(header_text, border_style="cyan", padding=(0, 2)))
        if is_partial:
            console.print(
                Panel(
                    "[bold yellow]PARTIAL RESULTS[/bold yellow]: "
                    f"opportunities {len(opps)}/{opportunity_page.total}, "
                    f"campaigns {len(campaigns)}/{campaign_page.total}, "
                    f"tasks {len(tasks)}/{task_page.total}. "
                    "All sampled KPI figures, win rates and reach counts are incomplete.",
                    border_style="yellow",
                )
            )

        # --- KPI CARDS ROW 1 ---
        kpi_cards_1 = [
            Panel(
                f"[bold green]{active_pipeline_val}[/bold green]\n"
                f"[dim]{len(open_opps)} active deals in flight[/dim]",
                title="💼 Active Pipeline",
                border_style="green",
            ),
            Panel(
                f"[bold cyan]{weighted_forecast_val}[/bold cyan]\n"
                f"[dim]Observed probability-weighted forecast[/dim]",
                title="🎯 Weighted Revenue",
                border_style="cyan",
            ),
            Panel(
                f"[bold magenta]{won_val}[/bold magenta]\n"
                f"[dim]Observed Win Rate: {win_rate:.0f}% ({len(won_opps)} won)[/dim]",
                title="🏆 Closed Won",
                border_style="magenta",
            ),
        ]
        console.print(Columns(kpi_cards_1, equal=True))

        # --- KPI CARDS ROW 2 ---
        kpi_cards_2 = [
            Panel(
                f"[bold yellow]{total_audience_reach} memberships[/bold yellow]\n"
                f"[dim]{len(campaigns)} observed campaigns (not deduplicated)[/dim]",
                title="📣 Audience Reach",
                border_style="yellow",
            ),
            Panel(
                f"[bold blue]{orgs_total} Accounts[/bold blue]\n"
                f"[dim]Corporate B2B organizations[/dim]",
                title="🏢 Organizations",
                border_style="blue",
            ),
            Panel(
                f"[bold white]{contacts_total} People[/bold white]\n"
                f"[dim]{len(open_tasks)} observed pending action items[/dim]",
                title="👥 Key Contacts",
                border_style="white",
            ),
        ]
        console.print(Columns(kpi_cards_2, equal=True))
        console.print()

        # --- SALES PIPELINE FUNNEL (VISUAL BARS) ---
        pipeline_table = Table(
            title="Commercial Sales Funnel & Deal Velocity",
            title_style="bold magenta",
            border_style="dim",
            expand=True,
        )
        pipeline_table.add_column("Pipeline Stage", style="bold white", width=24)
        pipeline_table.add_column("Deals", justify="center", width=8)
        pipeline_table.add_column("Stage Value", justify="right", style="green", width=18)
        pipeline_table.add_column("Weighted", justify="right", style="cyan", width=18)
        pipeline_table.add_column("Funnel Distribution Bar", style="magenta")

        # Real pipeline/stage identifiers. No fixed demo stages or invented probabilities.
        stage_keys = sorted(
            {(o.pipeline_id or "unassigned", o.stage_id or "unassigned") for o in opps}
        )
        for pipeline_id, stage_id in stage_keys:
            stage_deals = [
                o for o in opps
                if (o.pipeline_id or "unassigned", o.stage_id or "unassigned")
                == (pipeline_id, stage_id)
            ]
            ratio = len(stage_deals) / len(opps) if opps else 0.0
            pipeline_table.add_row(
                f"{pipeline_id} / {stage_id}",
                str(len(stage_deals)),
                _display_amounts(_sum_by_currency(stage_deals)),
                _display_amounts(_sum_by_currency(stage_deals, weighted=True)),
                f"[magenta]{_render_bar(ratio, width=22)}[/magenta] "
                f"[dim]{ratio * 100:.0f}% of sampled deals[/dim]",
            )

        console.print(pipeline_table)
        console.print()

        # --- CAMPAIGNS & ACTION ITEMS SIDE-BY-SIDE ---
        camp_table = Table(
            title="Active Multi-Channel Campaigns (v1.2.0)",
            title_style="bold yellow",
            border_style="dim",
            expand=True,
        )
        camp_table.add_column("Campaign", style="bold cyan")
        camp_table.add_column("Status", justify="center")
        camp_table.add_column("Audience", justify="right", style="green")
        camp_table.add_column("Budget", justify="right", style="yellow")

        for c in campaigns[:4]:
            reach = crm.campaigns.audience_count(c.id)
            budget = c.metadata.get("budget_allocated")
            budget_str = f"{budget:,.0f} (currency unspecified)" if isinstance(budget, (int, float)) else "-"
            status_style = {
                CampaignStatus.DRAFT: "[dim]DRAFT[/dim]",
                CampaignStatus.ACTIVE: "[bold green]ACTIVE[/bold green]",
                CampaignStatus.COMPLETED: "[blue]COMPLETED[/blue]",
            }.get(c.status, str(c.status.value))
            camp_table.add_row(c.name, status_style, f"{reach} VIPs", budget_str)

        task_table = Table(
            title="Priority Action Items & Follow-ups",
            title_style="bold red",
            border_style="dim",
            expand=True,
        )
        task_table.add_column("Task Title", style="white")
        task_table.add_column("Priority", justify="center")
        task_table.add_column("Due Date", justify="center")
        task_table.add_column("Status", justify="center")

        for t in open_tasks[:4]:
            due_str = t.due_at.strftime("%Y-%m-%d") if t.due_at else "-"
            prio_style = {
                TaskPriority.LOW: "[dim]LOW[/dim]",
                TaskPriority.NORMAL: "[white]NORMAL[/white]",
                TaskPriority.HIGH: "[yellow]HIGH[/yellow]",
                TaskPriority.URGENT: "[bold red]URGENT[/bold red]",
            }.get(t.priority, str(t.priority.name))
            status_style = (
                "[cyan]OPEN[/cyan]" if t.status == TaskStatus.OPEN else "[blue]IN PROGRESS[/blue]"
            )
            task_table.add_row(
                t.title[:38] + "..." if len(t.title) > 38 else t.title,
                prio_style,
                due_str,
                status_style,
            )

        console.print(
            Columns(
                [Panel(camp_table, border_style="yellow"), Panel(task_table, border_style="red")],
                equal=True,
            )
        )
        console.print()

        # --- RECENT ENGAGEMENTS & TIMELINE ACTIVITY STREAM ---
        if activities:
            console.print(Rule(title="Recent Customer Interactions & Engagements", style="dim"))
            for act in activities[:3]:
                occ = act.occurred_at.strftime("%Y-%m-%d %H:%M") if act.occurred_at else "-"
                ref_str = ", ".join(f"{r.kind}:{str(r.id)[:6]}" for r in act.references)
                console.print(
                    f"  [dim]{occ}[/dim]  [bold cyan]● {act.type.value.upper()}[/bold cyan]  "
                    f"[white]{act.subject}[/white]  [dim]({ref_str})[/dim]"
                )
            console.print()
