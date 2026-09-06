"""Execute ContactRepository contracts against a test-only reference adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import (
    Contact,
    ContactEmail,
    ContactId,
    ContactQuery,
    ContactRepository,
    ContactStatus,
)
from pycrmkit.core import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from tests.contracts.contacts_repository import ContactRepositoryContract


class ReferenceContactRepository:
    """Test-only reference implementation, not the public Memory Adapter."""

    def __init__(self) -> None:
        self._contacts: dict[ContactId, Contact] = {}

    def get(self, contact_id: ContactId) -> Contact:
        contact = self.find(contact_id)
        if contact is None:
            raise NotFoundError(
                "Contact not found",
                code="contact.not_found",
                context={"contact_id": str(contact_id)},
            )
        return contact

    def find(self, contact_id: ContactId) -> Contact | None:
        contact = self._contacts.get(contact_id)
        return deepcopy(contact) if contact is not None else None

    def save(self, contact: Contact) -> None:
        self._contacts[contact.id] = deepcopy(contact)

    def archive(self, contact_id: ContactId, archived_at: datetime) -> Contact:
        contact = self.get(contact_id)
        contact.archive(archived_at)
        self.save(contact)
        return contact

    def search(self, query: ContactQuery, page: OffsetPageRequest) -> Page[Contact]:
        contacts = list(self._contacts.values())
        if not query.include_archived:
            contacts = [item for item in contacts if item.status is not ContactStatus.ARCHIVED]
        if query.status is not None:
            contacts = [item for item in contacts if item.status is query.status]
        if query.email is not None:
            contacts = [
                item for item in contacts if any(email.normalized == query.email for email in item.emails)
            ]
        if query.phone is not None:
            contacts = [
                item for item in contacts if any(phone.normalized == query.phone for phone in item.phones)
            ]
        if query.name is not None:
            needle = query.name.casefold()
            contacts = [
                item
                for item in contacts
                if needle
                in " ".join(
                    part
                    for part in (item.first_name, item.last_name, item.display_name)
                    if part
                ).casefold()
            ]
        if query.owner_id is not None:
            contacts = [item for item in contacts if item.owner_id == query.owner_id]
        if query.source is not None:
            source = query.source.casefold()
            contacts = [
                item
                for item in contacts
                if item.source is not None and item.source.casefold() == source
            ]
        contacts.sort(key=lambda item: (item.created_at, item.id))
        total = len(contacts)
        selected = contacts[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


@pytest.fixture
def repository() -> ContactRepository:
    repository = ReferenceContactRepository()
    assert isinstance(repository, ContactRepository)
    return repository


@pytest.fixture
def contact() -> Contact:
    now = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000000011")),
        created_at=now,
        updated_at=now,
        first_name="Alpha",
        emails=(ContactEmail("contact@example.com", is_primary=True),),
    )


@pytest.fixture
def second_contact() -> Contact:
    now = datetime(2026, 9, 6, 10, 1, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000000012")),
        created_at=now,
        updated_at=now,
        first_name="Beta",
    )


@pytest.fixture
def missing_contact_id() -> ContactId:
    return ContactId(UUID("00000000-0000-4000-8000-000000009999"))


class TestReferenceContactRepository(ContactRepositoryContract):
    """Concrete execution of the reusable contract suite."""
