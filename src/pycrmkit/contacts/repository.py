"""Persistence contract for Contact aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.contacts.entities import Contact, ContactId
from pycrmkit.contacts.queries import ContactQuery
from pycrmkit.core.pagination import OffsetPageRequest, Page


@runtime_checkable
class ContactRepository(Protocol):
    """Backend-neutral repository contract for contacts."""

    def get(self, contact_id: ContactId) -> Contact:
        """Return a contact or raise NotFoundError when it does not exist."""

    def find(self, contact_id: ContactId) -> Contact | None:
        """Return a contact or None when it does not exist."""

    def save(self, contact: Contact) -> None:
        """Persist the current contact state without committing an outer transaction."""

    def archive(self, contact_id: ContactId, archived_at: datetime) -> Contact:
        """Archive the contact and return the resulting domain entity."""

    def search(self, query: ContactQuery, page: OffsetPageRequest) -> Page[Contact]:
        """Search contacts with exact count and deterministic pagination."""
