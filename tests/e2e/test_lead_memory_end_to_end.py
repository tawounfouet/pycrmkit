from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock


def test_contact_organization_to_qualified_lead_end_to_end() -> None:
    clock = FixedClock(datetime(2026, 9, 8, 11, 0, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(correlation_id="lead-e2e")

    contact = crm.contacts.create(first_name="Margaret", last_name="Hamilton")
    organization = crm.organizations.create(legal_name="Apollo Software")
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    clock.advance(timedelta(hours=1))
    lead = crm.leads.qualify(lead.id)

    assert lead.contact_id == contact.id
    assert lead.organization_id == organization.id
    lead_actions = [
        entry.action
        for entry in crm.audit.by_correlation("lead-e2e").items
        if entry.entity_type == "lead"
    ]
    assert lead_actions == ["lead.created", "lead.qualified"]
