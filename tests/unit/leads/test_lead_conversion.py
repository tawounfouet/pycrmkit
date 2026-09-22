from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import ConflictError, InvalidStateError
from pycrmkit.leads import LeadConversionService, LeadService, LeadStatus
from pycrmkit.opportunities import OpportunityQuery
from pycrmkit.organizations import OrganizationId
from pycrmkit.pipelines import PipelineService, Stage, StageTransition
from pycrmkit.storage.memory import (
    MemoryLeadRepository,
    MemoryOpportunityRepository,
    MemoryPipelineRepository,
)

NOW = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def make_service():
    clock = FixedClock(NOW)
    leads = MemoryLeadRepository()
    opportunities = MemoryOpportunityRepository()
    pipelines = MemoryPipelineRepository()
    conversion = LeadConversionService(
        leads=leads,
        opportunities=opportunities,
        pipelines=pipelines,
        id_factory=UUID4Factory(),
        clock=clock,
    )
    return clock, leads, opportunities, pipelines, conversion


def qualified_lead(leads: MemoryLeadRepository, clock: FixedClock):
    service = LeadService(leads, clock=clock)
    lead = service.create(
        contact_id=ContactId.parse("00000000-0000-4000-8000-000000004001"),
        organization_id=OrganizationId.parse("00000000-0000-4000-8000-000000004002"),
        source="website",
    )
    return service.qualify(lead.id)


def test_conversion_creates_opportunity_and_marks_lead_converted() -> None:
    clock, leads, opportunities, _, conversion = make_service()
    lead = qualified_lead(leads, clock)

    result = conversion.convert(
        lead.id,
        name="Enterprise rollout",
        estimated_value=Decimal("25000.00"),
        currency="eur",
        expected_close_date=date(2026, 12, 31),
        idempotency_key="lead-4001",
    )

    assert result.created is True
    assert result.lead.status is LeadStatus.CONVERTED
    assert result.lead.converted_opportunity_id == result.opportunity.id
    assert result.opportunity.contact_id == lead.contact_id
    assert result.opportunity.organization_id == lead.organization_id
    assert result.opportunity.estimated_value == Decimal("25000.00")
    assert result.opportunity.currency == "EUR"
    assert opportunities.get(result.opportunity.id) == result.opportunity


def test_same_key_and_equivalent_request_returns_same_opportunity() -> None:
    clock, leads, _, _, conversion = make_service()
    lead = qualified_lead(leads, clock)

    first = conversion.convert(
        lead.id,
        estimated_value=Decimal("25000.00"),
        currency="eur",
        idempotency_key="retry-key",
    )
    retry = conversion.convert(
        lead.id,
        estimated_value=Decimal("25000.0"),
        currency="EUR",
        idempotency_key="retry-key",
    )

    assert first.created is True
    assert retry.created is False
    assert retry.opportunity.id == first.opportunity.id


def test_same_key_with_conflicting_request_raises_conflict() -> None:
    clock, leads, _, _, conversion = make_service()
    lead = qualified_lead(leads, clock)
    conversion.convert(
        lead.id,
        estimated_value=Decimal("25000"),
        currency="EUR",
        idempotency_key="same-key",
    )

    with pytest.raises(ConflictError) as exc:
        conversion.convert(
            lead.id,
            estimated_value=Decimal("30000"),
            currency="EUR",
            idempotency_key="same-key",
        )

    assert exc.value.code == "lead.conversion.idempotency_conflict"


def test_converted_lead_rejects_different_idempotency_key() -> None:
    clock, leads, _, _, conversion = make_service()
    lead = qualified_lead(leads, clock)
    conversion.convert(lead.id, idempotency_key="first-key")

    with pytest.raises(InvalidStateError) as exc:
        conversion.convert(lead.id, idempotency_key="second-key")

    assert exc.value.code == "lead.conversion.already_converted"


def test_conversion_requires_qualified_lead() -> None:
    clock, leads, _, _, conversion = make_service()
    lead = LeadService(leads, clock=clock).create(
        contact_id=ContactId.parse("00000000-0000-4000-8000-000000004003")
    )

    with pytest.raises(InvalidStateError) as exc:
        conversion.convert(lead.id)

    assert exc.value.code == "lead.conversion.requires_qualified"


def test_conversion_enters_pipeline_initial_stage_and_probability() -> None:
    clock, leads, _, pipelines, conversion = make_service()
    lead = qualified_lead(leads, clock)
    PipelineService(pipelines).define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
        ),
        transitions=(StageTransition("new", "qualified"),),
    )

    result = conversion.convert(
        lead.id,
        pipeline_id="SALES",
        idempotency_key="pipeline-conversion",
    )

    assert result.opportunity.pipeline_id == "sales"
    assert result.opportunity.stage_id == "new"
    assert result.opportunity.probability == Decimal("0.10")
    page = conversion.opportunities.list(
        OpportunityQuery(pipeline_id="sales"),
        OffsetPageRequest(),
    )
    assert page.items == (result.opportunity,)
