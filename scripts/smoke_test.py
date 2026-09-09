"""Installed-package smoke test for the 0.3.0b1 Pipeline/Stage path."""

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
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.3.0b1":
        raise SystemExit(f"Expected PyCRMKit 0.3.0b1, got {version!r}")

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
    first_page = crm.timeline.for_contact(contact.id, OffsetPageRequest(limit=1, offset=0))
    if not first_page.has_next or str(first_page.items[0].event_type) != "task.completed":
        raise SystemExit("CRM.memory() Timeline pagination smoke failed")

    lead_events = []
    crm.events.subscribe("lead.qualified", lead_events.append)
    lead = crm.leads.create(contact_id=contact.id, organization_id=organization.id, source="website")
    lead = crm.leads.qualify(lead.id)
    if lead.status is not LeadStatus.QUALIFIED or len(lead_events) != 1:
        raise SystemExit("CRM.memory() Lead qualification smoke failed")
    if hasattr(crm.leads, "convert"):
        raise SystemExit("Lead conversion must remain deferred in 0.3.0b1")

    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome=OpportunityStatus.WON),
            Stage("lost", "Lost", 40, terminal=True, outcome=OpportunityStatus.LOST),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
            StageTransition("proposal", "lost"),
        ),
    )
    opportunity = crm.opportunities.create(
        name="Installed package opportunity",
        contact_id=contact.id,
        organization_id=organization.id,
        pipeline_id="sales",
        stage_id="new",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        probability=Decimal("0.10"),
        expected_close_date=date(2026, 12, 31),
        owner_id="seller-1",
    )
    if opportunity.money != Money(Decimal("25000.00"), "EUR"):
        raise SystemExit("CRM.memory() Opportunity Money smoke failed")
    if opportunity.stage_entered_at != clock.now():
        raise SystemExit("CRM.memory() initial stage timestamp smoke failed")

    try:
        crm.opportunities.move(opportunity.id, to="won")
    except InvalidStageTransition:
        pass
    else:
        raise SystemExit("Pipeline invalid-transition smoke failed")

    stage_events = []
    won_events = []
    crm.events.subscribe("opportunity.stage_changed", stage_events.append)
    crm.events.subscribe("opportunity.won", won_events.append)
    for stage in ("qualified", "proposal", "won"):
        clock.advance(timedelta(hours=1))
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    if opportunity.status is not OpportunityStatus.WON:
        raise SystemExit("CRM.memory() terminal Pipeline outcome smoke failed")
    if opportunity.probability != Decimal("1"):
        raise SystemExit("CRM.memory() terminal probability smoke failed")
    if len(stage_events) != 3 or len(won_events) != 1:
        raise SystemExit("CRM.memory() Pipeline events smoke failed")
    if crm.timeline.for_contact(contact.id).total != 4:
        raise SystemExit("Sales events must not project to Timeline in 0.3.0b1")

    print(f"PyCRMKit {version}: Pipeline/Stage transition smoke OK")


if __name__ == "__main__":
    main()
