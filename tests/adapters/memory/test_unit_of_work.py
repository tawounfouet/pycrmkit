"""Transaction and copy-isolation qualification for MemoryUnitOfWork."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.exceptions import InvalidStateError, NotFoundError
from pycrmkit.organizations import Organization, OrganizationId
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 6, 17, 0, tzinfo=UTC)


def _contact() -> Contact:
    return Contact(
        id=ContactId(UUID(int=501)),
        created_at=NOW,
        updated_at=NOW,
        first_name="Committed",
    )


def _organization() -> Organization:
    return Organization(
        id=OrganizationId(UUID(int=601)),
        created_at=NOW,
        updated_at=NOW,
        legal_name="Committed SAS",
    )


def test_memory_uow_is_a_unit_of_work() -> None:
    uow = MemoryUnitOfWork()
    assert isinstance(uow, UnitOfWork)


def test_uow_requires_context_before_repository_access() -> None:
    uow = MemoryUnitOfWork()
    with pytest.raises(InvalidStateError):
        _ = uow.contacts
    with pytest.raises(InvalidStateError):
        uow.commit()


def test_commit_persists_multiple_repositories_atomically() -> None:
    store = MemoryStore()
    contact = _contact()
    organization = _organization()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.organizations.save(organization)
        uow.commit()

    with MemoryUnitOfWork(store) as uow:
        assert uow.contacts.get(contact.id) == contact
        assert uow.organizations.get(organization.id) == organization


def test_exit_without_commit_rolls_back_all_repositories() -> None:
    store = MemoryStore()
    contact = _contact()
    organization = _organization()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.organizations.save(organization)

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)
        with pytest.raises(NotFoundError):
            uow.organizations.get(organization.id)


def test_explicit_rollback_discards_staged_state() -> None:
    store = MemoryStore()
    contact = _contact()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.rollback()
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)


def test_exception_rolls_back_staged_state() -> None:
    store = MemoryStore()
    contact = _contact()

    with pytest.raises(RuntimeError):
        with MemoryUnitOfWork(store) as uow:
            uow.contacts.save(contact)
            raise RuntimeError("boom")

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)


def test_mutating_loaded_entity_without_save_does_not_persist() -> None:
    store = MemoryStore()
    contact = _contact()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.commit()

    with MemoryUnitOfWork(store) as uow:
        loaded = uow.contacts.get(contact.id)
        loaded.source = "not-saved"
        assert uow.contacts.get(contact.id).source is None


def test_nested_transactions_on_same_store_are_rejected() -> None:
    store = MemoryStore()
    with MemoryUnitOfWork(store):
        with pytest.raises(InvalidStateError):
            with MemoryUnitOfWork(store):
                pass
