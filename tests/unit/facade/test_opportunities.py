from datetime import UTC, date, datetime
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def test_opportunity_facade_creates_with_event_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW)).with_context(
        actor_id="seller-1",
        correlation_id="corr-opportunity",
    )
    events: list[DomainEvent] = []
    crm.events.subscribe("opportunity.created", events.append)
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines")

    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
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

    assert opportunity.currency == "EUR"
    assert len(events) == 1
    assert events[0].aggregate_id == str(opportunity.id)
    assert events[0].payload["status"] == "open"
    assert events[0].actor_id == "seller-1"
    audit = [
        entry
        for entry in crm.audit.by_correlation("corr-opportunity").items
        if entry.entity_type == "opportunity"
    ]
    assert len(audit) == 1
    assert audit[0].action == "opportunity.created"
    assert "25000" not in repr(audit[0].changes)


def test_opportunity_event_is_not_projected_to_timeline_yet() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    contact = crm.contacts.create(first_name="Grace", last_name="Hopper")
    crm.opportunities.create(name="Compiler deal", contact_id=contact.id)
    assert crm.timeline.for_contact(contact.id).total == 0


def test_opportunity_facade_is_deliberately_creation_only() -> None:
    crm = CRM.memory()
    assert hasattr(crm.opportunities, "create")
    assert not hasattr(crm.opportunities, "move")
    assert not hasattr(crm.opportunities, "mark_won")
    assert not hasattr(crm.opportunities, "mark_lost")
    assert not hasattr(crm.opportunities, "get")
    assert not hasattr(crm.opportunities, "list")
