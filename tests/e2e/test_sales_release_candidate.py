"""Stable qualification for the complete 0.3 Sales Foundation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

import pycrmkit
from pycrmkit import CRM
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.leads import LeadQuery, LeadStatus
from pycrmkit.opportunities import OpportunityQuery, OpportunityStatus
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition

NOW = datetime(2026, 9, 24, 7, 0, tzinfo=UTC)
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


def define_sales_pipeline(crm: CRM) -> None:
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


def subscribe_sales_events(crm: CRM) -> list[DomainEvent]:
    events: list[DomainEvent] = []
    for event_type in SALES_EVENTS:
        crm.events.subscribe(event_type, events.append)
    return events


def test_sales_stable_won_path_is_atomic_idempotent_and_auditable() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(
        actor_id="seller-rc",
        correlation_id="corr-sales-rc-won",
    )
    events = subscribe_sales_events(crm)
    define_sales_pipeline(crm)
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines")

    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    clock.advance(timedelta(minutes=1))
    lead = crm.leads.qualify(lead.id)

    clock.advance(timedelta(minutes=1))
    opportunity = crm.leads.convert(
        lead.id,
        name="Enterprise rollout",
        estimated_value=Decimal("25000.00"),
        currency="eur",
        pipeline_id="SALES",
        owner_id="seller-rc",
        idempotency_key="sales-rc-won",
    )
    retry = crm.leads.convert(
        lead.id,
        name="Enterprise rollout",
        estimated_value=Decimal("25000.0"),
        currency="EUR",
        pipeline_id="sales",
        owner_id="seller-rc",
        idempotency_key="sales-rc-won",
    )
    assert retry.id == opportunity.id

    with pytest.raises(InvalidStageTransition):
        crm.opportunities.move(opportunity.id, to="won")

    for stage in ("qualified", "proposal", "won"):
        clock.advance(timedelta(hours=1))
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.stage_id == "won"
    assert opportunity.probability == Decimal("1")

    event_types = [str(event.type) for event in events]
    assert event_types == [
        "lead.created",
        "lead.qualified",
        "opportunity.created",
        "lead.converted",
        "opportunity.stage_changed",
        "opportunity.stage_changed",
        "opportunity.stage_changed",
        "opportunity.won",
    ]
    assert all(event.actor_id == "seller-rc" for event in events)
    assert all(event.correlation_id == "corr-sales-rc-won" for event in events)

    audit = crm.audit.by_correlation("corr-sales-rc-won")
    actions = [entry.action for entry in audit.items]
    assert actions.count("lead.converted") == 1
    assert actions.count("opportunity.created") == 1
    assert actions.count("opportunity.stage_changed") == 3
    assert actions.count("opportunity.won") == 1

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )
    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == opportunity.id
    assert opportunities.total == 1


def test_sales_stable_qualifies_disqualified_and_lost_outcomes() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(correlation_id="corr-sales-rc-outcomes")
    events = subscribe_sales_events(crm)
    define_sales_pipeline(crm)
    contact = crm.contacts.create(first_name="Grace", last_name="Hopper")

    disqualified = crm.leads.create(contact_id=contact.id, source="referral")
    disqualified = crm.leads.disqualify(disqualified.id)
    assert disqualified.status is LeadStatus.DISQUALIFIED

    lead = crm.leads.create(contact_id=contact.id, source="event")
    lead = crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        lead.id,
        pipeline_id="sales",
        idempotency_key="sales-rc-lost",
    )
    for stage in ("qualified", "proposal", "lost"):
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert opportunity.status is OpportunityStatus.LOST
    assert opportunity.stage_id == "lost"
    assert opportunity.probability == Decimal("0")

    event_types = [str(event.type) for event in events]
    assert "lead.disqualified" in event_types
    assert "opportunity.lost" in event_types
    assert event_types.count("opportunity.stage_changed") == 3

    with crm._runtime.uow_factory() as uow:
        converted = uow.leads.list(
            LeadQuery(status=LeadStatus.CONVERTED),
            OffsetPageRequest(),
        )
        rejected = uow.leads.list(
            LeadQuery(status=LeadStatus.DISQUALIFIED),
            OffsetPageRequest(),
        )
    assert converted.total == 1
    assert rejected.total == 1


def test_0_3_stable_public_facade_surface_is_frozen() -> None:
    assert pycrmkit.__all__ == ["CRM", "CRMConfig", "CRMContext", "__version__"]
    crm = CRM.memory(clock=FixedClock(NOW))

    def public_methods(namespace: object) -> set[str]:
        return {
            name
            for name in dir(namespace)
            if not name.startswith("_") and callable(getattr(namespace, name))
        }

    assert public_methods(crm.leads) == {
        "create",
        "qualify",
        "disqualify",
        "convert",
    }
    assert public_methods(crm.opportunities) == {"create", "move"}
    assert public_methods(crm.pipelines) == {"define", "get", "list"}

    for stable_namespace in (
        "contacts",
        "organizations",
        "relationships",
        "tags",
        "custom_fields",
        "events",
        "audit",
        "activities",
        "tasks",
        "timeline",
    ):
        assert getattr(crm, stable_namespace) is not None
