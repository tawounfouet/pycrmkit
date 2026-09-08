"""Run Lead repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.leads import Lead, LeadId, LeadRepository
from pycrmkit.organizations import OrganizationId
from pycrmkit.storage.memory import MemoryLeadRepository

from ...contracts.leads_repository import LeadRepositoryContract

NOW = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)


@pytest.fixture
def later() -> datetime:
    return NOW + timedelta(minutes=5)


@pytest.fixture
def repository() -> LeadRepository:
    repository = MemoryLeadRepository()
    assert isinstance(repository, LeadRepository)
    return repository


@pytest.fixture
def lead() -> Lead:
    return Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003101")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003111")),
        organization_id=OrganizationId(UUID("00000000-0000-4000-8000-000000003121")),
        source="website",
    )


@pytest.fixture
def second_lead() -> Lead:
    return Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003102")),
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003112")),
        source="partner",
    )


@pytest.fixture
def disqualified_lead() -> Lead:
    item = Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003103")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003113")),
    )
    item.disqualify(NOW + timedelta(minutes=1))
    return item


@pytest.fixture
def converted_lead() -> Lead:
    item = Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003104")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003114")),
    )
    item.qualify(NOW + timedelta(minutes=1))
    item.mark_converted(NOW + timedelta(minutes=2))
    return item


@pytest.fixture
def missing_lead_id() -> LeadId:
    return LeadId(UUID("00000000-0000-4000-8000-000000009997"))


class TestMemoryLeadRepository(LeadRepositoryContract):
    """Official Memory adapter must satisfy the reusable Lead contract."""


def test_lead_repository_isolates_saved_and_loaded_mutations(lead: Lead) -> None:
    repository = MemoryLeadRepository()
    repository.save(lead)
    lead.source = "changed-after-save"
    assert repository.get(lead.id).source == "website"

    loaded = repository.get(lead.id)
    loaded.source = "changed-after-read"
    assert repository.get(lead.id).source == "website"
