from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import TypeVar
from uuid import UUID

from pycrmkit.contacts import (
    Contact,
    ContactEmail,
    ContactId,
    ContactQuery,
    ContactRepository,
    ContactService,
    ContactStatus,
    ContactUpdate,
)
from pycrmkit.core import EntityId, FixedClock, OffsetPageRequest, Page, UUIDId
from pycrmkit.exceptions import NotFoundError

TId = TypeVar("TId", bound=UUIDId)


class DeterministicIdFactory:
    def new(self, id_type: type[TId]) -> TId:
        return id_type(UUID("00000000-0000-4000-8000-000000000021"))


class ServiceRepository:
    def __init__(self) -> None:
        self.contacts: dict[ContactId, Contact] = {}

    def get(self, contact_id: ContactId) -> Contact:
        contact = self.find(contact_id)
        if contact is None:
            raise NotFoundError("Contact not found", code="contact.not_found")
        return contact

    def find(self, contact_id: ContactId) -> Contact | None:
        contact = self.contacts.get(contact_id)
        return deepcopy(contact) if contact else None

    def save(self, contact: Contact) -> None:
        self.contacts[contact.id] = deepcopy(contact)

    def archive(self, contact_id: ContactId, archived_at: datetime) -> Contact:
        contact = self.get(contact_id)
        contact.archive(archived_at)
        self.save(contact)
        return contact

    def search(self, query: ContactQuery, page: OffsetPageRequest) -> Page[Contact]:
        items = [
            item
            for item in self.contacts.values()
            if query.include_archived or item.status is not ContactStatus.ARCHIVED
        ]
        items.sort(key=lambda item: (item.created_at, item.id))
        selected = items[page.offset : page.offset + page.limit]
        return Page(tuple(deepcopy(selected)), page.limit, page.offset, len(items))


def test_contact_service_create_update_archive_and_search() -> None:
    repository = ServiceRepository()
    assert isinstance(repository, ContactRepository)
    clock = FixedClock(datetime(2026, 9, 6, 10, 0, tzinfo=UTC))
    service = ContactService(
        repository=repository,
        id_factory=DeterministicIdFactory(),
        clock=clock,
    )
    contact = service.create(
        first_name=" Thomas ",
        emails=(ContactEmail("THOMAS@example.com", is_primary=True),),
        source=" Web ",
        metadata={"campaign": "launch"},
    )
    assert str(contact.id) == "00000000-0000-4000-8000-000000000021"
    assert contact.display_name == "Thomas"
    assert service.get(contact.id) == contact
    clock.advance(timedelta(minutes=5))
    owner_id = EntityId(UUID("00000000-0000-4000-8000-000000000099"))
    updated = service.update(
        contact.id,
        ContactUpdate(last_name="Awounfouet", owner_id=owner_id, source=None),
    )
    assert updated.display_name == "Thomas Awounfouet"
    assert updated.owner_id == owner_id
    assert updated.source is None
    assert updated.updated_at == clock.now()
    assert service.search().items == (updated,)
    clock.advance(timedelta(minutes=5))
    archived = service.archive(contact.id)
    assert archived.status is ContactStatus.ARCHIVED
    assert service.search().items == ()
    assert service.search(ContactQuery(include_archived=True)).items == (archived,)
