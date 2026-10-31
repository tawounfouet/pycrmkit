"""Contacts management commands for PyCRMKit CLI."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit import CRM
from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context, query_opportunities
from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactPhone
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import NotFoundError
from pycrmkit.relationships import RelationshipEndpoint, RelationshipQuery
from pycrmkit.tasks import TaskQuery

contacts_app = typer.Typer(
    name="contacts",
    help="Manage contacts, phone/email attributes, tags, and custom fields.",
    no_args_is_help=True,
)


def _resolve_contact(crm: CRM, query_str: str) -> Contact:
    """Resolve a contact by exact UUID, UUID prefix, name, or email substring."""
    query_clean = query_str.strip().rstrip(".")

    try:
        cid = ContactId(query_clean)
        return crm.contacts.get(cid)
    except (ValueError, TypeError, NotFoundError):
        pass

    all_contacts = crm.contacts.search(page=OffsetPageRequest(limit=200)).items
    q_lower = query_clean.lower()

    uuid_matches = [c for c in all_contacts if str(c.id).lower().startswith(q_lower)]
    if len(uuid_matches) == 1:
        return uuid_matches[0]

    name_matches = [
        c
        for c in all_contacts
        if q_lower in c.display_name.lower()
        or (c.first_name and q_lower in c.first_name.lower())
        or (c.last_name and q_lower in c.last_name.lower())
    ]
    if len(name_matches) == 1:
        return name_matches[0]

    email_matches = [c for c in all_contacts if any(q_lower in e.value.lower() for e in c.emails)]
    if len(email_matches) == 1:
        return email_matches[0]

    matches = uuid_matches or name_matches or email_matches
    if len(matches) > 1:
        table = Table(
            title=f"Plusieurs contacts correspondent à '{query_str}'", border_style="yellow"
        )
        table.add_column("ID", style="dim")
        table.add_column("Nom", style="bold cyan")
        table.add_column("Email", style="green")
        for c in matches:
            email_val = c.emails[0].value if c.emails else "-"
            table.add_row(str(c.id)[:8] + "...", c.display_name, email_val)
        console.print(table)
        console.print("[yellow]Veuillez préciser le nom, l'email ou le préfixe UUID.[/yellow]")
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))

    console.print(f"[bold red]Contact introuvable :[/bold red] '{query_str}'")
    raise typer.Exit(code=int(ExitCode.GENERAL_ERROR))


@contacts_app.command("list")
def list_contacts(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of contacts to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List contacts in the CRM with contact channels and status."""
    with get_crm_context(save=False) as crm:
        page = crm.contacts.search(page=OffsetPageRequest(limit=limit, offset=offset))

    if not page.items:
        console.print(
            "[yellow]No contacts found in store. Use 'pck contacts create' or 'pck seed' to add contacts.[/yellow]"
        )
        return

    table = Table(title=f"Contacts Directory ({page.total} total)", border_style="dim")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Primary Email", style="green")
    table.add_column("Primary Phone", style="blue")
    table.add_column("Source", style="dim")
    table.add_column("Status", justify="center")

    for c in page.items:
        primary_email = c.emails[0].value if c.emails else "-"
        primary_phone = c.phones[0].value if c.phones else "-"
        status_badge = (
            "[bold green]ACTIVE[/bold green]"
            if c.status.value == "active"
            else f"[dim]{c.status.value.upper()}[/dim]"
        )

        table.add_row(
            str(c.id)[:8] + "...",
            c.display_name,
            primary_email,
            primary_phone,
            c.source or "-",
            status_badge,
        )

    console.print(table)


@contacts_app.command("create")
def create_contact(
    first_name: Annotated[str, typer.Argument(help="Contact first name")],
    last_name: Annotated[str, typer.Argument(help="Contact last name")],
    email: Annotated[
        str | None, typer.Option("--email", "-e", help="Primary email address")
    ] = None,
    phone: Annotated[str | None, typer.Option("--phone", "-p", help="Primary phone number")] = None,
    source: Annotated[str, typer.Option("--source", "-s", help="Origin or lead source")] = "cli",
) -> None:
    """Create a new contact with optional normalized email and phone channels."""
    emails = (ContactEmail(email, is_primary=True),) if email else ()
    phones = (ContactPhone(phone, is_primary=True),) if phone else ()

    with get_crm_context(save=True) as crm:
        contact = crm.contacts.create(
            first_name=first_name,
            last_name=last_name,
            source=source,
            emails=emails,
            phones=phones,
        )

    console.print(
        Panel(
            f"[bold green]✓ Contact Created Successfully[/bold green]\n\n"
            f"[bold]ID:[/bold] {contact.id}\n"
            f"[bold]Name:[/bold] {contact.display_name}\n"
            f"[bold]Email:[/bold] {email or '<none>'}\n"
            f"[bold]Phone:[/bold] {phone or '<none>'}\n"
            f"[bold]Source:[/bold] {source}",
            border_style="green",
        )
    )


@contacts_app.command("show")
def show_contact(
    query: Annotated[
        str, typer.Argument(help="Contact UUID, UUID prefix, name, or email substring")
    ],
) -> None:
    """Show 360° executive contact sheet with accounts, deals, campaigns, and timeline."""
    with get_crm_context(save=False) as crm:
        contact = _resolve_contact(crm, query)
        contact_ref = EntityReference("contact", contact.id)

        # 1. Associated Organizations (Relationships)
        rel_page = crm.relationships.search(
            RelationshipQuery(entity=RelationshipEndpoint.contact(contact.id)),
            page=OffsetPageRequest(limit=50),
        )
        org_rows = []
        for rel in rel_page.items:
            endpoint = rel.source if rel.source.kind == "organization" else rel.target
            if endpoint.kind == "organization":
                try:
                    org = crm.organizations.get(endpoint.id)
                    role = rel.role or rel.title or rel.relationship_type.value
                    org_rows.append((org, role, rel.is_primary))
                except NotFoundError:
                    pass

        # 2. Deals / Opportunities
        opps = [
            opp
            for opp in query_opportunities(crm, page=OffsetPageRequest(limit=100)).items
            if opp.contact_id == contact.id
        ]
        total_pipeline = sum((o.estimated_value for o in opps), start=0)
        total_weighted = sum((o.estimated_value * o.probability for o in opps), start=0)

        # 3. Enrolled Campaigns
        all_camps = crm.campaigns.list(page=OffsetPageRequest(limit=50)).items
        enrolled_camps = [
            camp for camp in all_camps if crm.campaigns.contains(camp.id, contact_ref)
        ]

        # 4. Pending Tasks
        tasks = crm.tasks.list(
            TaskQuery(reference=contact_ref, unresolved_only=True),
            page=OffsetPageRequest(limit=10),
        ).items

        # 5. Tags
        tags = [
            str(t.name.value)
            for t in crm.tags.list_for_entity(contact_ref, page=OffsetPageRequest(limit=50)).items
        ]
        tags_str = (
            " ".join(f"[bold cyan]#{t}[/bold cyan]" for t in tags)
            if tags
            else "[dim]Aucun tag[/dim]"
        )

        # 6. Custom fields
        cf_values = crm.custom_fields.list_values(
            contact_ref, page=OffsetPageRequest(limit=50)
        ).items
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

        # 7. Timeline
        timeline_entries = crm.timeline.for_contact(
            contact.id, page=OffsetPageRequest(limit=5)
        ).items

    # --- Header Banner ---
    initials = (
        f"{contact.first_name[:1]}{contact.last_name[:1]}".upper()
        if contact.first_name and contact.last_name
        else "👤"
    )
    status_badge = (
        "[bold black on green] CLIENT ACTIF [/bold black on green]"
        if contact.status.value == "active"
        else f"[bold white on blue] {contact.status.value.upper()} [/bold white on blue]"
    )
    primary_org_str = (
        f" • {org_rows[0][1]} chez [bold cyan]{org_rows[0][0].trading_name or org_rows[0][0].legal_name}[/bold cyan]"
        if org_rows
        else ""
    )
    primary_email = contact.emails[0].value if contact.emails else "-"
    primary_phone = contact.phones[0].value if contact.phones else "-"

    header_panel = Panel(
        f"[bold white on blue] {initials} [/bold white on blue]  "
        f"[bold white]{contact.display_name}[/bold white]{primary_org_str}   {status_badge}   [dim]ID: {contact.id}[/dim]\n"
        f"[dim]Email : {primary_email} • Tél : {primary_phone} • Source : {contact.source or 'Direct'}[/dim]",
        style="bold blue",
        border_style="bright_blue",
    )
    console.print(header_panel)

    # --- Top Row: AI Summary & Profile ---
    status_label = "Interlocuteur VIP / C-Level" if "vip" in tags else "Contact Opérationnel"
    next_task_text = (
        f"Action requise : {tasks[0].title}" if tasks else "Aucune action critique urgente."
    )
    summary_text = (
        f"[bold]{contact.display_name}[/bold] est un {status_label}.\n\n"
        f"• [bold]Engagement :[/bold] Rattaché à {len(org_rows)} compte(s), inscrit à {len(enrolled_camps)} campagne(s).\n"
        f"• [bold]Opportunités :[/bold] {len(opps)} deal(s) actif(s) pour un total de "
        f"[bold green]{total_pipeline:,.2f} €[/bold green] (Pondéré : {total_weighted:,.2f} €).\n\n"
        f"👉 [bold yellow]{next_task_text}[/bold yellow]"
    )

    ai_panel = Panel(
        summary_text,
        title="💡 Résumé Exécutif (360° Intelligence)",
        border_style="cyan",
    )

    emails_formatted = ", ".join(e.value for e in contact.emails) if contact.emails else "-"
    phones_formatted = ", ".join(p.value for p in contact.phones) if contact.phones else "-"
    info_panel = Panel(
        f"• [bold]Emails :[/bold] {emails_formatted}\n"
        f"• [bold]Téléphones :[/bold] {phones_formatted}\n"
        f"• [bold]Origine / Source :[/bold] {contact.source or '-'}\n"
        f"• [bold]Tags :[/bold] {tags_str}\n"
        f"{cf_text}",
        title="📋 Coordonnées & Profil",
        border_style="blue",
    )

    top_grid = Table.grid(expand=True, padding=(0, 1))
    top_grid.add_column(ratio=1)
    top_grid.add_column(ratio=1)
    top_grid.add_row(ai_panel, info_panel)
    console.print(top_grid)

    # --- Organizations Table ---
    org_table = Table(
        title=f"🏢 Organisations & Rattachements ({len(org_rows)})",
        border_style="dim",
        expand=True,
    )
    org_table.add_column("ID", style="dim", no_wrap=True)
    org_table.add_column("Organisation", style="bold cyan")
    org_table.add_column("Rôle / Fonction", style="white")
    org_table.add_column("Compte Principal", justify="center")
    org_table.add_column("Statut", justify="center")

    if org_rows:
        for org, role, is_pri in org_rows:
            pri_badge = "[bold yellow]⭐ OUI[/bold yellow]" if is_pri else "[dim]-[/dim]"
            org_status = (
                "[bold green]Actif[/bold green]"
                if org.status.value == "active"
                else f"[dim]{org.status.value}[/dim]"
            )
            org_name = (
                f"{org.trading_name} ({org.legal_name})" if org.trading_name else org.legal_name
            )
            org_table.add_row(str(org.id)[:8] + "...", org_name, role, pri_badge, org_status)
    else:
        org_table.add_row("-", "Aucune organisation rattachée", "-", "-", "-")
    console.print(org_table)

    # --- Deals / Opportunities Table ---
    o_table = Table(
        title=f"💼 Deals & Opportunités Associés ({len(opps)})", border_style="dim", expand=True
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
            "[bold]TOTAL PIPELINE ASSOCIE[/bold]",
            "",
            f"[bold green]{total_pipeline:,.2f} EUR[/bold green]",
            "",
            f"[bold green]{total_weighted:,.2f} EUR[/bold green]",
            "",
        )
    else:
        o_table.add_row("-", "-", "0.00 EUR", "0 %", "0.00 EUR", "[dim]Aucun deal associé[/dim]")
    console.print(o_table)

    # --- Bottom Row: Campaigns, Tasks & Timeline ---
    left_blocks = []
    if enrolled_camps:
        camp_lines = []
        for camp in enrolled_camps:
            status_badge = (
                "[bold green]ACTIF[/bold green]"
                if camp.status.value == "active"
                else f"[dim]{camp.status.value.upper()}[/dim]"
            )
            camp_lines.append(
                f"• [bold]{camp.name}[/bold] ({status_badge})\n  [dim]{camp.key}[/dim]"
            )
        left_blocks.append("[bold green]Campagnes actives :[/bold green]\n" + "\n".join(camp_lines))

    if tasks:
        task_lines = []
        for t in tasks:
            prio_name = getattr(t.priority, "name", str(t.priority)).upper()
            prio_style = "bold red" if prio_name in ("URGENT", "HIGH") else "yellow"
            due_str = t.due_at.strftime("%d/%m/%Y") if t.due_at else "Non définie"
            task_lines.append(
                f" [ ] [bold]{t.title}[/bold] ([{prio_style}]{prio_name}[/{prio_style}] • {due_str})"
            )
        left_blocks.append("[bold yellow]Tâches à venir :[/bold yellow]\n" + "\n".join(task_lines))

    if left_blocks:
        camp_panel = Panel(
            "\n\n".join(left_blocks),
            title=f"📣 Inscriptions & Actions ({len(enrolled_camps)} camp., {len(tasks)} tâches)",
            border_style="green",
        )
    else:
        camp_panel = Panel(
            "[dim]Aucune inscription ni tâche active[/dim]",
            title="📣 Inscriptions & Actions",
            border_style="dim",
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
    bottom_grid.add_row(camp_panel, tl_panel)
    console.print(bottom_grid)
