from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.leads import Lead, LeadId
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)


def make_lead() -> Lead:
    return Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003201")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003202")),
    )


def test_lead_uow_commit_persists() -> None:
    store = MemoryStore()
    lead = make_lead()
    with MemoryUnitOfWork(store) as uow:
        uow.leads.save(lead)
        uow.commit()
    with MemoryUnitOfWork(store) as uow:
        assert uow.leads.get(lead.id) == lead


def test_lead_uow_rollback_discards() -> None:
    store = MemoryStore()
    lead = make_lead()
    with MemoryUnitOfWork(store) as uow:
        uow.leads.save(lead)
    with MemoryUnitOfWork(store) as uow:
        assert uow.leads.find(lead.id) is None


def test_lead_uow_exception_rolls_back() -> None:
    store = MemoryStore()
    lead = make_lead()
    with pytest.raises(RuntimeError):
        with MemoryUnitOfWork(store) as uow:
            uow.leads.save(lead)
            raise RuntimeError("boom")
    with MemoryUnitOfWork(store) as uow:
        assert uow.leads.find(lead.id) is None
