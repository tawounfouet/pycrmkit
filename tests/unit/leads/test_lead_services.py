from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.contacts import ContactId
from pycrmkit.core import FixedClock, OffsetPageRequest
from pycrmkit.leads import LeadQuery, LeadService, LeadStatus
from pycrmkit.organizations import OrganizationId
from pycrmkit.storage.memory import MemoryLeadRepository

NOW = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)


def test_lead_service_create_qualify_and_list() -> None:
    clock = FixedClock(NOW)
    repository = MemoryLeadRepository()
    service = LeadService(repository, clock=clock)
    contact_id = ContactId(UUID("00000000-0000-4000-8000-000000003011"))
    organization_id = OrganizationId(UUID("00000000-0000-4000-8000-000000003012"))

    lead = service.create(
        contact_id=contact_id,
        organization_id=organization_id,
        source="website",
    )
    assert lead.status is LeadStatus.NEW

    clock.advance(timedelta(minutes=1))
    lead = service.qualify(lead.id)
    assert lead.status is LeadStatus.QUALIFIED

    page = service.list(
        LeadQuery(status=LeadStatus.QUALIFIED, contact_id=contact_id),
        OffsetPageRequest(limit=10, offset=0),
    )
    assert page.items == (lead,)


def test_lead_service_disqualify() -> None:
    repository = MemoryLeadRepository()
    service = LeadService(repository, clock=FixedClock(NOW))
    lead = service.create(
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003013"))
    )
    lead = service.disqualify(lead.id)
    assert lead.status is LeadStatus.DISQUALIFIED
