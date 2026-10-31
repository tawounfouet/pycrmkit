"""Organizations management commands for PyCRMKit CLI."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit import CRM
from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context, query_opportunities
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import Organization, OrganizationId
from pycrmkit.relationships import RelationshipEndpoint, RelationshipQuery
from pycrmkit.tasks import TaskQuery

orgs_app = typer.Typer(
    name="orgs",
    help="Manage enterprise accounts, legal organizations, and trade names.",
    no_args_is_help=True,
)


def _resolve_organization(crm: CRM, query_str: str) -> Organization:
    """Resolve an organization by exact UUID, UUID prefix, or name substring."""
    query_clean = query_str.strip().rstrip(".")

    try:
        oid = OrganizationId(query_clean)
        return crm.organizations.get(oid)
    except (ValueError, TypeError, NotFoundError):
        pass

    all_orgs = crm.organizations.search(page=OffsetPageRequest(limit=200)).items
    q_lower = query_clean.lower()

    uuid_matches = [o for o in all_orgs if str(o.id).lower().startswith(q_lower)]
    if len(uuid_matches) == 1:
        return uuid_matches[0]

    name_matches = [
        o
        for o in all_orgs
        if q_lower in o.legal_name.lower() or (o.trading_name and q_lower in o.trading_name.lower())
    ]
    if len(name_matches) == 1:
        return name_matches[0]

    matches = uuid_matches or name_matches
    if len(matches) > 1:
        table = Table(
            title=f"Plusieurs organisations correspondent à '{query_str}'", border_style="yellow"
        )
        table.add_column("ID", style="dim")
        table.add_column("Nom Légal", style="bold cyan")
        table.add_column("Nom Commercial", style="blue")
        for o in matches:
            table.add_row(str(o.id)[:8] + "...", o.legal_name, o.trading_name or "-")
        console.print(table)
        console.print("[yellow]Veuillez préciser le nom ou le préfixe UUID.[/yellow]")
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))

    console.print(f"[bold red]Organisation introuvable :[/bold red] '{query_str}'")
    raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))


@orgs_app.command("list")
def list_organizations(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of records to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List organizations in the CRM directory."""
    with get_crm_context(save=False) as crm:
        page = crm.organizations.search(page=OffsetPageRequest(limit=limit, offset=offset))

    if not page.items:
        console.print(
            "[yellow]No organizations found in store. Use 'pck orgs create' or 'pck seed' to add records.[/yellow]"
        )
        return

    table = Table(title=f"Organizations & Accounts ({page.total} total)", border_style="dim")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Legal Name", style="bold cyan")
    table.add_column("Trade Name", style="blue")
    table.add_column("Source", style="dim")
    table.add_column("Status", justify="center")

    for org in page.items:
        status_badge = (
            "[bold green]ACTIVE[/bold green]"
            if org.status.value == "active"
            else f"[dim]{org.status.value.upper()}[/dim]"
        )
        table.add_row(
            str(org.id)[:8] + "...",
            org.legal_name,
            org.trading_name or "-",
            org.source or "-",
            status_badge,
        )

    console.print(table)


@orgs_app.command("create")
def create_organization(
    legal_name: Annotated[str, typer.Argument(help="Official registered legal company name")],
    trade_name: Annotated[
        str | None, typer.Option("--trade-name", "-t", help="Commercial brand / trading name")
    ] = None,
    source: Annotated[
        str, typer.Option("--source", "-s", help="Account acquisition source")
    ] = "cli",
) -> None:
    """Create a new corporate account / organization."""
    with get_crm_context(save=True) as crm:
        org = crm.organizations.create(
            legal_name=legal_name,
            trading_name=trade_name,
            source=source,
        )

    console.print(
        Panel(
            f"[bold green]✓ Organization Created Successfully[/bold green]\n\n"
            f"[bold]ID:[/bold] {org.id}\n"
            f"[bold]Legal Name:[/bold] {org.legal_name}\n"
            f"[bold]Trade Name:[/bold] {trade_name or '<none>'}\n"
            f"[bold]Source:[/bold] {source}",
            border_style="green",
        )
    )


@orgs_app.command("show")
def show_organization(
    query: Annotated[str, typer.Argument(help="Organization UUID, UUID prefix, or name substring")],
) -> None:
    """Show 360° executive customer sheet for an enterprise organization."""
    with get_crm_context(save=False) as crm:
        org = _resolve_organization(crm, query)
        org_ref = EntityReference("organization", org.id)

        # 1. Contacts associated through relationships
        rel_page = crm.relationships.search(
            RelationshipQuery(entity=RelationshipEndpoint.organization(org.id)),
            page=OffsetPageRequest(limit=50),
        )
        contact_rows = []
        for rel in rel_page.items:
            endpoint = rel.source if rel.source.kind == "contact" else rel.target
            if endpoint.kind == "contact":
                try:
                    c = crm.contacts.get(endpoint.id)
                    role = rel.role or rel.title or rel.relationship_type.value
                    contact_rows.append((c, role, rel.is_primary))
                except NotFoundError:
                    pass

        # 2. Active opportunities
        opps = [
            opp
            for opp in query_opportunities(crm, page=OffsetPageRequest(limit=100)).items
            if opp.organization_id == org.id
        ]
        total_pipeline = sum((o.estimated_value for o in opps), start=0)
        total_weighted = sum((o.estimated_value * o.probability for o in opps), start=0)

        # 3. Pending tasks
        tasks = crm.tasks.list(
            TaskQuery(reference=org_ref, unresolved_only=True),
            page=OffsetPageRequest(limit=10),
        ).items

        # 4. Tags
        tags = [
            str(t.name.value)
            for t in crm.tags.list_for_entity(org_ref, page=OffsetPageRequest(limit=50)).items
        ]
        tags_str = (
            " ".join(f"[bold cyan]#{t}[/bold cyan]" for t in tags)
            if tags
            else "[dim]Aucun tag[/dim]"
        )

        # 5. Custom fields
        cf_values = crm.custom_fields.list_values(org_ref, page=OffsetPageRequest(limit=50)).items
        cf_lines = []
        for cfv in cf_values:
            try:
                defn = crm.custom_fields.get_definition(cfv.definition_id)
                cf_lines.append(f"• [bold]{defn.label} :[/bold] {cfv.value}")
            except NotFoundError:
                pass
        cf_text = (
            "\n".join(cf_lines) if cf_lines else "[dim]Aucun champ personnalisé configuré[/dim]"
        )

        # 6. Timeline
        timeline_entries = crm.timeline.for_organization(
            org.id, page=OffsetPageRequest(limit=5)
        ).items

    # --- Render Executive 360° Header ---
    status_badge = (
        "[bold black on green] CLIENT ACTIF [/bold black on green]"
        if org.status.value == "active"
        else f"[bold white on blue] {org.status.value.upper()} [/bold white on blue]"
    )
    header_title = f"🏢  [bold white]{org.legal_name.upper()}[/bold white]"
    if org.trading_name:
        header_title += f" [bold cyan]({org.trading_name})[/bold cyan]"

    header_panel = Panel(
        f"{header_title}   {status_badge}   [dim]ID: {org.id}[/dim]\n"
        f"[dim]Origine : {org.source or 'Direct'} • Enregistré le : {org.created_at.strftime('%d/%m/%Y %H:%M UTC')}[/dim]",
        style="bold blue",
        border_style="bright_blue",
    )
    console.print(header_panel)

    # --- Top Row: AI Summary & Key Info ---
    status_label = "Client Stratégique (VIP)" if "vip" in tags else "Compte Entreprise Actif"
    next_task_text = (
        f"Action requise : {tasks[0].title}" if tasks else "Aucune action critique urgente."
    )
    summary_text = (
        f"[bold]{org.legal_name}[/bold] est un {status_label} "
        f"(Canal : [italic]{org.source or 'Direct'}[/italic]).\n\n"
        f"• [bold]Interlocuteurs :[/bold] {len(contact_rows)} contact(s) clé(s) identifié(s).\n"
        f"• [bold]Pipeline Commercial :[/bold] {len(opps)} deal(s) en cours, totalisant "
        f"[bold green]{total_pipeline:,.2f} €[/bold green] (Pondéré : {total_weighted:,.2f} €).\n\n"
        f"👉 [bold yellow]{next_task_text}[/bold yellow]"
    )

    ai_panel = Panel(
        summary_text,
        title="💡 Résumé Exécutif (360° Intelligence)",
        border_style="cyan",
    )
    info_panel = Panel(
        f"• [bold]Nom légal :[/bold] {org.legal_name}\n"
        f"• [bold]Nom commercial :[/bold] {org.trading_name or '-'}\n"
        f"• [bold]Statut commercial :[/bold] {org.status.value.capitalize()}\n"
        f"• [bold]Tags :[/bold] {tags_str}\n"
        f"{cf_text}",
        title="📋 Informations Clés & Profil",
        border_style="blue",
    )

    top_grid = Table.grid(expand=True, padding=(0, 1))
    top_grid.add_column(ratio=1)
    top_grid.add_column(ratio=1)
    top_grid.add_row(ai_panel, info_panel)
    console.print(top_grid)

    # --- Contacts Table ---
    c_table = Table(
        title=f"👥 Contacts & Interlocuteurs Clés ({len(contact_rows)})",
        border_style="dim",
        expand=True,
    )
    c_table.add_column("ID", style="dim", no_wrap=True)
    c_table.add_column("Nom Complet", style="bold cyan")
    c_table.add_column("Rôle / Fonction", style="white")
    c_table.add_column("Principal", justify="center")
    c_table.add_column("Email", style="green")
    c_table.add_column("Téléphone", style="blue")

    if contact_rows:
        for c, role, is_pri in contact_rows:
            pri_badge = "[bold yellow]⭐ OUI[/bold yellow]" if is_pri else "[dim]-[/dim]"
            email_str = c.emails[0].value if c.emails else "-"
            phone_str = c.phones[0].value if c.phones else "-"
            c_table.add_row(
                str(c.id)[:8] + "...", c.display_name, role, pri_badge, email_str, phone_str
            )
    else:
        c_table.add_row("-", "Aucun contact associé", "-", "-", "-", "-")
    console.print(c_table)

    # --- Deals / Opportunities Table ---
    o_table = Table(
        title=f"💼 Deals & Opportunités en cours ({len(opps)})", border_style="dim", expand=True
    )
    o_table.add_column("Nom du Deal", style="bold white")
    o_table.add_column("Étape (Stage)", style="cyan")
    o_table.add_column("Valeur", justify="right", style="green")
    o_table.add_column("Probabilité", justify="right", style="dim")
    o_table.add_column("Pondéré", justify="right", style="bold green")
    o_table.add_column("Statut", justify="center")

    if opps:
        for opp in opps:
            weighted = opp.estimated_value * opp.probability
            stage_badge = f"[bold cyan]{opp.stage_id.upper()}[/bold cyan]"
            status_text = (
                "[bold green]En cours[/bold green]" if opp.probability > 0 else "[dim]Terminé[/dim]"
            )
            o_table.add_row(
                opp.name,
                stage_badge,
                f"{opp.estimated_value:,.2f} {opp.currency}",
                f"{int(opp.probability * 100)} %",
                f"{weighted:,.2f} {opp.currency}",
                status_text,
            )
        o_table.add_section()
        o_table.add_row(
            "[bold]TOTAL PIPELINE ACTIF[/bold]",
            "",
            f"[bold green]{total_pipeline:,.2f} EUR[/bold green]",
            "",
            f"[bold green]{total_weighted:,.2f} EUR[/bold green]",
            "",
        )
    else:
        o_table.add_row("-", "-", "0.00 EUR", "0 %", "0.00 EUR", "[dim]Aucun deal actif[/dim]")
    console.print(o_table)

    # --- Bottom Row: Tasks & Timeline ---
    if tasks:
        t_content = []
        for t in tasks:
            prio_name = getattr(t.priority, "name", str(t.priority)).upper()
            prio_style = "bold red" if prio_name in ("URGENT", "HIGH") else "yellow"
            due_str = t.due_at.strftime("%d/%m/%Y") if t.due_at else "Non définie"
            t_content.append(
                f" [ ] [bold]{t.title}[/bold]\n"
                f"     Priorité : [{prio_style}]{prio_name}[/{prio_style}] • Échéance : {due_str}"
            )
        task_panel = Panel(
            "\n\n".join(t_content),
            title=f"⏱️ Tâches à venir ({len(tasks)})",
            border_style="yellow",
        )
    else:
        task_panel = Panel(
            "[dim]Aucune tâche en attente[/dim]", title="⏱️ Tâches à venir", border_style="dim"
        )

    if timeline_entries:
        tl_content = []
        for entry in timeline_entries:
            act_type = entry.metadata.get("activity_type") if entry.metadata else None
            kind_val = entry.kind.value if hasattr(entry.kind, "value") else str(entry.kind)
            icon = {
                "meeting": "📅 Réunion",
                "call": "📞 Appel",
                "email": "✉️ E-mail",
                "note": "📝 Note",
            }.get(act_type)
            if not icon:
                icon = {
                    "activity": "⚡ Activité",
                    "task": "⚙️ Tâche",
                    "stage_change": "🔄 Deal",
                    "audit": "📋 Audit",
                }.get(kind_val, f"• {kind_val}")

            date_str = entry.occurred_at.strftime("%d/%m %H:%M")
            tl_content.append(f"[bold]{icon}[/bold] [dim]({date_str})[/dim]\n  {entry.title}")
        tl_panel = Panel(
            "\n".join(tl_content),
            title=f"📜 Activités Récentes ({len(timeline_entries)})",
            border_style="magenta",
        )
    else:
        tl_panel = Panel(
            "[dim]Aucune activité enregistrée[/dim]",
            title="📜 Activités Récentes",
            border_style="dim",
        )

    bottom_grid = Table.grid(expand=True, padding=(0, 1))
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_row(task_panel, tl_panel)
    console.print(bottom_grid)
