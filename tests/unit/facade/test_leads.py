from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import ConflictError, InvalidStateError
from pycrmkit.leads import LeadStatus
from pycrmkit.pipelines import Stage, StageTransition

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)


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


def test_lead_conversion_emits_once_and_is_idempotent() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(correlation_id="corr-conversion")
    contact = crm.contacts.create(first_name="Margaret", last_name="Hamilton")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)
    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
        ),
        transitions=(StageTransition("new", "qualified"),),
    )
    converted_events: list[DomainEvent] = []
    created_events: list[DomainEvent] = []
    crm.events.subscribe("lead.converted", converted_events.append)
    crm.events.subscribe("opportunity.created", created_events.append)

    first = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("20000.00"),
        currency="eur",
        pipeline_id="sales",
        idempotency_key="lead-conversion-1",
    )
    retry = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("20000.0"),
        currency="EUR",
        pipeline_id="SALES",
        idempotency_key="lead-conversion-1",
    )

    assert retry.id == first.id
    assert len(converted_events) == 1
    assert len(created_events) == 1
    actions = [entry.action for entry in crm.audit.by_correlation("corr-conversion").items]
    assert actions.count("lead.converted") == 1
    assert actions.count("opportunity.created") == 1


def test_lead_conversion_rejects_same_key_with_different_request() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    contact = crm.contacts.create(first_name="Dorothy", last_name="Vaughan")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)
    crm.leads.convert(
        lead.id,
        estimated_value=Decimal("10000"),
        currency="EUR",
        idempotency_key="same-key",
    )

    with pytest.raises(ConflictError) as exc:
        crm.leads.convert(
            lead.id,
            estimated_value=Decimal("12000"),
            currency="EUR",
            idempotency_key="same-key",
        )

    assert exc.value.code == "lead.conversion.idempotency_conflict"


def test_0_3_0b2_lead_facade_surface() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    assert hasattr(crm.leads, "create")
    assert hasattr(crm.leads, "qualify")
    assert hasattr(crm.leads, "disqualify")
    assert hasattr(crm.leads, "convert")
    assert not hasattr(crm.leads, "get")
    assert not hasattr(crm.leads, "list")
