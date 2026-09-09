from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityRepository
from pycrmkit.organizations import OrganizationId
from pycrmkit.storage.memory import MemoryOpportunityRepository

from ...contracts.opportunities_repository import OpportunityRepositoryContract

NOW = datetime(2026, 9, 9, 10, 0, tzinfo=UTC)


def build_opportunity(*, suffix: str, created_at: datetime, name: str) -> Opportunity:
    return Opportunity(
        id=OpportunityId(UUID(f"00000000-0000-4000-8000-000000004{suffix}")),
        created_at=created_at,
        updated_at=created_at,
        name=name,
        contact_id=ContactId(UUID(f"00000000-0000-4000-8000-000000005{suffix}")),
    )


@pytest.fixture
def repository() -> OpportunityRepository:
    repository = MemoryOpportunityRepository()
    assert isinstance(repository, OpportunityRepository)
    return repository


@pytest.fixture
def opportunity() -> Opportunity:
    return Opportunity(
        id=OpportunityId(UUID("00000000-0000-4000-8000-000000004101")),
        created_at=NOW,
        updated_at=NOW,
        name="Proposal",
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000005101")),
        organization_id=OrganizationId(UUID("00000000-0000-4000-8000-000000006101")),
        pipeline_id="sales",
        stage_id="proposal",
        estimated_value=Decimal("10000"),
        currency="EUR",
        probability=Decimal("0.6"),
        expected_close_date=date(2026, 11, 30),
        owner_id="seller-1",
    )


@pytest.fixture
def second_opportunity() -> Opportunity:
    return build_opportunity(
        suffix="102",
        created_at=NOW + timedelta(minutes=1),
        name="Later",
    )


@pytest.fixture
def closed_opportunity() -> Opportunity:
    item = build_opportunity(suffix="103", created_at=NOW, name="Won")
    item.mark_won(NOW + timedelta(minutes=2))
    return item


@pytest.fixture
def missing_opportunity_id() -> OpportunityId:
    return OpportunityId(UUID("00000000-0000-4000-8000-000000009996"))


class TestMemoryOpportunityRepository(OpportunityRepositoryContract):
    pass


def test_repository_isolates_saved_and_loaded_mutations(opportunity: Opportunity) -> None:
    repository = MemoryOpportunityRepository()
    repository.save(opportunity)
    opportunity.name = "changed-after-save"
    assert repository.get(opportunity.id).name == "Proposal"

    loaded = repository.get(opportunity.id)
    loaded.name = "changed-after-read"
    assert repository.get(opportunity.id).name == "Proposal"
