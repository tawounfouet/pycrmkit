from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.leads import LeadStatus

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)


def test_lead_facade_create_emits_post_commit_event_and_audit() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(
        actor_id="seller-1",
        correlation_id="corr-lead",
    )
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines")
    events: list[DomainEvent] = []
    crm.events.subscribe("lead.created", events.append)

    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )

    assert lead.status is LeadStatus.NEW
    assert len(events) == 1
    assert events[0].payload["status"] == "new"
    assert events[0].actor_id == "seller-1"
    audit = crm.audit.by_correlation("corr-lead")
    assert {entry.action for entry in audit.items} >= {"lead.created"}
    assert "website" not in repr(audit.items[0].changes)


def test_lead_facade_qualify_and_disqualify_emit_declared_events() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(correlation_id="corr-lead-life")
    contact = crm.contacts.create(first_name="Grace", last_name="Hopper")
    qualified_events: list[DomainEvent] = []
    disqualified_events: list[DomainEvent] = []
    crm.events.subscribe("lead.qualified", qualified_events.append)
    crm.events.subscribe("lead.disqualified", disqualified_events.append)

    lead = crm.leads.create(contact_id=contact.id)
    clock.advance(timedelta(minutes=1))
    lead = crm.leads.qualify(lead.id)
    assert lead.status is LeadStatus.QUALIFIED
    clock.advance(timedelta(minutes=1))
    lead = crm.leads.disqualify(lead.id)
    assert lead.status is LeadStatus.DISQUALIFIED
    assert len(qualified_events) == 1
    assert len(disqualified_events) == 1


def test_lead_facade_rejects_invalid_terminal_transition() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    contact = crm.contacts.create(first_name="Katherine", last_name="Johnson")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.disqualify(lead.id)
    with pytest.raises(InvalidStateError):
        crm.leads.qualify(lead.id)


def test_public_lead_conversion_is_deferred() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    assert not hasattr(crm.leads, "get")
    assert not hasattr(crm.leads, "list")
    assert not hasattr(crm.leads, "convert")
