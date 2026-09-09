"""Installed-package smoke test for the 0.3.0a2 Opportunity path."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pycrmkit
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core import Money
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.leads import LeadStatus


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.3.0a2":
        raise SystemExit(f"Expected PyCRMKit 0.3.0a2, got {version!r}")

    amount = Money(Decimal("15000"), "eur")
    if amount.currency != "EUR" or amount.amount != Decimal("15000"):
        raise SystemExit("Money Decimal/currency smoke failed")

    clock = FixedClock(datetime(2026, 9, 9, 9, tzinfo=UTC))
    crm = pycrmkit.CRM.memory(clock=clock)
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    organization = crm.organizations.create(legal_name="Smoke Org")
    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    historical_at = datetime(2025, 1, 2, 10, tzinfo=UTC)
    crm.activities.log(
        type="meeting",
        occurred_at=historical_at,
        subject="Installed package historical activity",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )

    clock.advance(timedelta(hours=1))
    task = crm.tasks.create(
        title="Installed package task smoke",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    clock.advance(timedelta(hours=1))
    crm.tasks.start(task.id)
    clock.advance(timedelta(hours=1))
    crm.tasks.complete(task.id)

    contact_timeline = crm.timeline.for_contact(contact.id)
    organization_timeline = crm.timeline.for_organization(organization.id)
    if contact_timeline.total != 4 or organization_timeline.items != contact_timeline.items:
        raise SystemExit("CRM.memory() multi-entity Timeline smoke failed")
    if contact_timeline.items[-1].occurred_at != historical_at:
        raise SystemExit("CRM.memory() historical occurrence Timeline smoke failed")

    first_page = crm.timeline.for_contact(
        contact.id,
        OffsetPageRequest(limit=1, offset=0),
    )
    if not first_page.has_next or str(first_page.items[0].event_type) != "task.completed":
        raise SystemExit("CRM.memory() Timeline pagination smoke failed")

    lead_events = []
    crm.events.subscribe("lead.qualified", lead_events.append)
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    lead = crm.leads.qualify(lead.id)
    if lead.status is not LeadStatus.QUALIFIED or len(lead_events) != 1:
        raise SystemExit("CRM.memory() Lead qualification smoke failed")
    if hasattr(crm.leads, "convert"):
        raise SystemExit("Lead conversion must remain deferred in 0.3.0a2")

    opportunity_events = []
    crm.events.subscribe("opportunity.created", opportunity_events.append)
    opportunity = crm.opportunities.create(
        name="Installed package opportunity",
        contact_id=contact.id,
        organization_id=organization.id,
        pipeline_id="sales",
        stage_id="proposal",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        probability=Decimal("0.65"),
        expected_close_date=date(2026, 12, 31),
        owner_id="seller-1",
    )
    if opportunity.money != Money(Decimal("25000.00"), "EUR"):
        raise SystemExit("CRM.memory() Opportunity Money smoke failed")
    if len(opportunity_events) != 1 or opportunity_events[0].payload["status"] != "open":
        raise SystemExit("CRM.memory() Opportunity event smoke failed")
    if hasattr(crm.opportunities, "move") or hasattr(crm.opportunities, "mark_won"):
        raise SystemExit("Opportunity transition facade must remain deferred in 0.3.0a2")
    if crm.timeline.for_contact(contact.id).total != 4:
        raise SystemExit("Opportunity must not project to Timeline in 0.3.0a2")

    print(f"PyCRMKit {version}: stable 0.2 + Lead + Opportunity alpha smoke OK")


if __name__ == "__main__":
    main()
