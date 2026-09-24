"""Installed-package smoke test for the 0.4.0a2 Email Provider Protocol prerelease."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pycrmkit
from pycrmkit.activities import ActivityParticipant
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    EmailDeliveryStatus,
    EmailProviderResult,
)
from pycrmkit.core import Money
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.leads import LeadStatus
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition

SALES_EVENTS = (
    "lead.created",
    "lead.qualified",
    "lead.converted",
    "lead.disqualified",
    "opportunity.created",
    "opportunity.stage_changed",
    "opportunity.won",
    "opportunity.lost",
)


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.4.0a2":
        raise SystemExit(f"Expected PyCRMKit 0.4.0a2, got {version!r}")

    address = CommunicationAddress(
        CommunicationChannel.EMAIL,
        "Smoke.User@Example.COM",
    )
    if address.normalized != "smoke.user@example.com":
        raise SystemExit("Communication address normalization smoke failed")

    provider_result = EmailProviderResult(
        provider="installed-smoke",
        status=EmailDeliveryStatus.ACCEPTED,
        provider_message_id="smoke-message",
        provider_metadata={"transport": "fake"},
    )
    if provider_result.provider_message_id != "smoke-message":
        raise SystemExit("Email provider result smoke failed")

    amount = Money(Decimal("15000"), "eur")
    if amount.currency != "EUR" or amount.amount != Decimal("15000"):
        raise SystemExit("Money Decimal/currency smoke failed")

    clock = FixedClock(datetime(2026, 9, 24, 7, tzinfo=UTC))
    crm = pycrmkit.CRM.memory(clock=clock).with_context(
        actor_id="installed-smoke",
        correlation_id="communication-a2-smoke",
    )
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    organization = crm.organizations.create(legal_name="Smoke Org")
    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    crm.activities.log(
        type="meeting",
        subject="Stable 0.2 compatibility smoke",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )
    task = crm.tasks.create(
        title="Stable task compatibility smoke",
        references=(contact_ref, organization_ref),
    )
    crm.tasks.complete(task.id)
    if crm.timeline.for_contact(contact.id).total != 3:
        raise SystemExit("Stable Activity/Task/Timeline compatibility smoke failed")

    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome="won"),
            Stage("lost", "Lost", 40, terminal=True, outcome="lost"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
            StageTransition("proposal", "lost"),
        ),
    )

    events = []
    for event_type in SALES_EVENTS:
        crm.events.subscribe(event_type, events.append)

    won_lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    won_lead = crm.leads.qualify(won_lead.id)
    if won_lead.status is not LeadStatus.QUALIFIED:
        raise SystemExit("Lead qualification smoke failed")

    won_opportunity = crm.leads.convert(
        won_lead.id,
        name="Installed package won path",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="installed-smoke-won",
    )
    retry = crm.leads.convert(
        won_lead.id,
        name="Installed package won path",
        estimated_value=Decimal("25000.0"),
        currency="eur",
        pipeline_id="SALES",
        idempotency_key="installed-smoke-won",
    )
    if retry.id != won_opportunity.id:
        raise SystemExit("Lead conversion idempotent replay smoke failed")

    try:
        crm.opportunities.move(won_opportunity.id, to="won")
    except InvalidStageTransition:
        pass
    else:
        raise SystemExit("Pipeline invalid-transition smoke failed")

    for stage in ("qualified", "proposal", "won"):
        won_opportunity = crm.opportunities.move(won_opportunity.id, to=stage)
    if won_opportunity.status is not OpportunityStatus.WON:
        raise SystemExit("Won terminal outcome smoke failed")

    rejected = crm.leads.create(contact_id=contact.id, source="referral")
    rejected = crm.leads.disqualify(rejected.id)
    if rejected.status is not LeadStatus.DISQUALIFIED:
        raise SystemExit("Lead disqualification smoke failed")

    lost_lead = crm.leads.create(contact_id=contact.id, source="event")
    lost_lead = crm.leads.qualify(lost_lead.id)
    lost_opportunity = crm.leads.convert(
        lost_lead.id,
        pipeline_id="sales",
        idempotency_key="installed-smoke-lost",
    )
    for stage in ("qualified", "proposal", "lost"):
        lost_opportunity = crm.opportunities.move(lost_opportunity.id, to=stage)
    if lost_opportunity.status is not OpportunityStatus.LOST:
        raise SystemExit("Lost terminal outcome smoke failed")

    event_types = {str(event.type) for event in events}
    missing = set(SALES_EVENTS) - event_types
    if missing:
        raise SystemExit(f"Missing Sales RC events: {sorted(missing)!r}")
    if crm.timeline.for_contact(contact.id).total != 3:
        raise SystemExit("Sales events must remain outside Timeline in 0.4.0a2")

    print(f"PyCRMKit {version}: Email Provider Protocol + stable 0.3 smoke OK")


if __name__ == "__main__":
    main()
