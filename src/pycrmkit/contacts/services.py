"""Application service for Contact lifecycle operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from pycrmkit.contacts.dto import ContactUpdate, UnsetType
from pycrmkit.contacts.entities import Contact, ContactId, ContactStatus
from pycrmkit.contacts.policies import resolve_display_name
from pycrmkit.contacts.queries import ContactQuery
from pycrmkit.contacts.repository import ContactRepository
from pycrmkit.contacts.value_objects import Address, ContactEmail, ContactPhone
from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import InvalidStateError

T = TypeVar("T")


@dataclass(slots=True)
class ContactService:
    """Framework-agnostic Contact application service."""

    repository: ContactRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
        status: ContactStatus = ContactStatus.ACTIVE,
        owner_id: EntityId | None = None,
        source: str | None = None,
        emails: Sequence[ContactEmail] = (),
        phones: Sequence[ContactPhone] = (),
        addresses: Sequence[Address] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Contact:
        """Create and persist a Contact after domain normalization/validation."""
        if status is ContactStatus.ARCHIVED:
            raise InvalidStateError(
                "contacts cannot be created directly as archived",
                code="contact.create.archived",
            )
        now = self.clock.now()
        contact = Contact(
            id=self.id_factory.new(ContactId),
            created_at=now,
            updated_at=now,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            status=status,
            owner_id=owner_id,
            source=source,
            emails=tuple(emails),
            phones=tuple(phones),
            addresses=tuple(addresses),
            metadata=dict(metadata or {}),
        )
        self.repository.save(contact)
        return contact

    def get(self, contact_id: ContactId) -> Contact:
        """Return a Contact using the repository's explicit not-found contract."""
        return self.repository.get(contact_id)

    def update(self, contact_id: ContactId, changes: ContactUpdate) -> Contact:
        """Validate a typed partial update and persist the resulting Contact."""
        current = self.repository.get(contact_id)
        current.ensure_mutable()
        now = self.clock.now()
        status = self._value(changes.status, current.status)
        if status is ContactStatus.ARCHIVED:
            raise InvalidStateError(
                "use ContactService.archive() to archive a contact",
                code="contact.update.archive_requires_archive_operation",
            )
        first_name = self._value(changes.first_name, current.first_name)
        last_name = self._value(changes.last_name, current.last_name)
        display_name = self._display_name_for_update(current, changes, first_name, last_name)
        candidate = Contact(
            id=current.id,
            created_at=current.created_at,
            updated_at=now,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            status=status,
            owner_id=self._value(changes.owner_id, current.owner_id),
            source=self._value(changes.source, current.source),
            emails=self._value(changes.emails, current.emails),
            phones=self._value(changes.phones, current.phones),
            addresses=self._value(changes.addresses, current.addresses),
            metadata=self._value(changes.metadata, current.metadata),
        )
        self.repository.save(candidate)
        return candidate

    def archive(self, contact_id: ContactId) -> Contact:
        """Archive a contact through the repository's shared semantic contract."""
        return self.repository.archive(contact_id, self.clock.now())

    def search(
        self,
        query: ContactQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Contact]:
        """Search contacts using backend-independent filters and pagination."""
        return self.repository.search(query or ContactQuery(), page or OffsetPageRequest())

    @staticmethod
    def _display_name_for_update(
        current: Contact,
        changes: ContactUpdate,
        first_name: str | None,
        last_name: str | None,
    ) -> str | None:
        if not isinstance(changes.display_name, UnsetType):
            return changes.display_name
        current_derived = resolve_display_name(
            first_name=current.first_name,
            last_name=current.last_name,
            explicit=None,
        )
        names_changed = not isinstance(changes.first_name, UnsetType) or not isinstance(
            changes.last_name, UnsetType
        )
        if names_changed and current.display_name == current_derived:
            return resolve_display_name(
                first_name=first_name,
                last_name=last_name,
                explicit=None,
            )
        return current.display_name

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
