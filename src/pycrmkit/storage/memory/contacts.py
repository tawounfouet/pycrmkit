"""In-memory ContactRepository implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pycrmkit.contacts.entities import Contact, ContactId, ContactStatus
from pycrmkit.contacts.queries import ContactQuery
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


class MemoryContactRepository:
    """Copy-isolated, contract-conformant Contact repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

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
        contact = self._state.contacts.get(contact_id)
        return deepcopy(contact) if contact is not None else None

    def save(self, contact: Contact) -> None:
        self._state.contacts[contact.id] = deepcopy(contact)

    def archive(self, contact_id: ContactId, archived_at: datetime) -> Contact:
        contact = self.get(contact_id)
        contact.archive(archived_at)
        self.save(contact)
        return contact

    def search(self, query: ContactQuery, page: OffsetPageRequest) -> Page[Contact]:
        contacts = list(self._state.contacts.values())
        if not query.include_archived:
            contacts = [item for item in contacts if item.status is not ContactStatus.ARCHIVED]
        if query.status is not None:
            contacts = [item for item in contacts if item.status is query.status]
        if query.email is not None:
            contacts = [
                item
                for item in contacts
                if any(email.normalized == query.email for email in item.emails)
            ]
        if query.phone is not None:
            contacts = [
                item
                for item in contacts
                if any(phone.normalized == query.phone for phone in item.phones)
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
