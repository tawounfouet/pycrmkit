from datetime import UTC, date, datetime
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock


def test_contact_organization_to_opportunity_end_to_end() -> None:
    crm = CRM.memory(clock=FixedClock(datetime(2026, 9, 9, 13, 0, tzinfo=UTC))).with_context(
        correlation_id="opportunity-e2e"
    )
    contact = crm.contacts.create(first_name="Katherine", last_name="Johnson")
    organization = crm.organizations.create(legal_name="Orbital Systems")
    opportunity = crm.opportunities.create(
        name="Mission planning platform",
        contact_id=contact.id,
        organization_id=organization.id,
        estimated_value=Decimal("50000"),
        currency="USD",
        probability=Decimal("0.4"),
        expected_close_date=date(2027, 1, 31),
    )
    assert opportunity.contact_id == contact.id
    assert opportunity.organization_id == organization.id
    actions = [
        entry.action
        for entry in crm.audit.by_correlation("opportunity-e2e").items
        if entry.entity_type == "opportunity"
    ]
    assert actions == ["opportunity.created"]
