from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pycrmkit import CRM
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import ValidationError
from pycrmkit.leads import LeadQuery, LeadStatus
from pycrmkit.opportunities import OpportunityQuery, OpportunityStatus
from pycrmkit.pipelines import Stage, StageTransition

NOW = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)


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


def test_conversion_commits_lead_opportunity_events_and_audit_atomically() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(
        actor_id="seller-1",
        correlation_id="corr-convert",
    )
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines")
    define_sales_pipeline(crm)
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    lead = crm.leads.qualify(lead.id)

    opportunity_events: list[DomainEvent] = []
    conversion_events: list[DomainEvent] = []
    crm.events.subscribe("opportunity.created", opportunity_events.append)
    crm.events.subscribe("lead.converted", conversion_events.append)

    opportunity = crm.leads.convert(
        lead.id,
        name="Enterprise rollout",
        estimated_value=Decimal("25000"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="convert-001",
    )

    assert opportunity.contact_id == contact.id
    assert opportunity.organization_id == organization.id
    assert opportunity.stage_id == "new"
    assert opportunity.probability == Decimal("0.10")
    assert len(opportunity_events) == 1
    assert len(conversion_events) == 1
    assert conversion_events[0].payload["opportunity_id"] == str(opportunity.id)

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        persisted_opportunity = uow.opportunities.get(opportunity.id)
    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == opportunity.id
    assert persisted_opportunity == opportunity

    audit = crm.audit.by_correlation("corr-convert")
    assert {entry.action for entry in audit.items} >= {
        "lead.converted",
        "opportunity.created",
    }


def test_retry_after_post_commit_subscriber_failure_returns_existing_opportunity() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock)
    contact = crm.contacts.create(first_name="Grace", last_name="Hopper")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)

    def fail_after_commit(event: DomainEvent) -> None:
        del event
        raise RuntimeError("simulated transport failure")

    crm.events.subscribe("opportunity.created", fail_after_commit)
    with pytest.raises(RuntimeError, match="simulated transport failure"):
        crm.leads.convert(
            lead.id,
            estimated_value=Decimal("15000.00"),
            currency="eur",
            idempotency_key="transport-retry",
        )

    crm.events.unsubscribe("opportunity.created", fail_after_commit)
    opportunity = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("15000.0"),
        currency="EUR",
        idempotency_key="transport-retry",
    )

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )
    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == opportunity.id
    assert opportunities.total == 1
    assert opportunities.items[0].id == opportunity.id


def test_invalid_conversion_rolls_back_lead_and_opportunity() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock)
    contact = crm.contacts.create(first_name="Katherine", last_name="Johnson")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)

    with pytest.raises(ValidationError):
        crm.leads.convert(
            lead.id,
            estimated_value=Decimal("10000"),
            currency="EU",
            idempotency_key="bad-currency",
        )

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        opportunities = uow.opportunities.list(
            OpportunityQuery(contact_id=contact.id),
            OffsetPageRequest(),
        )
    assert persisted_lead.status is LeadStatus.QUALIFIED
    assert opportunities.total == 0


def test_converted_opportunity_can_progress_to_won() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock)
    define_sales_pipeline(crm)
    contact = crm.contacts.create(first_name="Margaret", last_name="Hamilton")
    lead = crm.leads.create(contact_id=contact.id)
    lead = crm.leads.qualify(lead.id)

    opportunity = crm.leads.convert(
        lead.id,
        pipeline_id="sales",
        idempotency_key="pipeline-e2e",
    )
    for stage in ("qualified", "proposal", "won"):
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.stage_id == "won"
    assert opportunity.probability == Decimal("1")

    with crm._runtime.uow_factory() as uow:
        converted = uow.leads.list(
            LeadQuery(status=LeadStatus.CONVERTED),
            OffsetPageRequest(),
        )
    assert converted.items[0].converted_opportunity_id == opportunity.id
