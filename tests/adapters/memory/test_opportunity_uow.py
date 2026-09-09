from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.opportunities import OpportunityService
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 9, 11, 0, tzinfo=UTC)


def test_opportunity_uow_commit_persists() -> None:
    store = MemoryStore()
    with MemoryUnitOfWork(store) as uow:
        opportunity = OpportunityService(uow.opportunities).create(
            name="Committed",
            contact_id=ContactId(UUID(int=10)),
        )
        uow.commit()
    with MemoryUnitOfWork(store) as uow:
        assert uow.opportunities.get(opportunity.id).name == "Committed"


def test_opportunity_uow_exit_without_commit_rolls_back() -> None:
    store = MemoryStore()
    with MemoryUnitOfWork(store) as uow:
        opportunity = OpportunityService(uow.opportunities).create(
            name="Rolled back",
            contact_id=ContactId(UUID(int=10)),
        )
    with MemoryUnitOfWork(store) as uow:
        assert uow.opportunities.find(opportunity.id) is None


def test_opportunity_uow_exception_rolls_back() -> None:
    store = MemoryStore()
    opportunity_id = None
    with pytest.raises(RuntimeError):
        with MemoryUnitOfWork(store) as uow:
            opportunity = OpportunityService(uow.opportunities).create(
                name="Exception",
                contact_id=ContactId(UUID(int=10)),
            )
            opportunity_id = opportunity.id
            raise RuntimeError("boom")
    with MemoryUnitOfWork(store) as uow:
        assert opportunity_id is not None
        assert uow.opportunities.find(opportunity_id) is None
