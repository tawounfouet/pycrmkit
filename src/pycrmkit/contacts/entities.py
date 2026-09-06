"""Contact aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.contacts.policies import (
    normalize_optional_text,
    resolve_display_name,
    validate_contact_identity,
    validate_contact_points,
)
from pycrmkit.contacts.value_objects import Address, ContactEmail, ContactPhone
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError


class ContactId(UUIDId):
    """Strongly typed identifier for a Contact."""


class ContactStatus(StrEnum):
    """Lifecycle status for a contact record."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass(eq=False, slots=True)
class Contact(TimestampedEntity[ContactId]):
    """Headless CRM contact aggregate."""

    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    status: ContactStatus = ContactStatus.ACTIVE
    owner_id: EntityId | None = None
    source: str | None = None
    emails: tuple[ContactEmail, ...] = ()
    phones: tuple[ContactPhone, ...] = ()
    addresses: tuple[Address, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.first_name = normalize_optional_text(self.first_name)
        self.last_name = normalize_optional_text(self.last_name)
        self.display_name = resolve_display_name(
            first_name=self.first_name,
            last_name=self.last_name,
            explicit=self.display_name,
        )
        self.source = normalize_optional_text(self.source)
        self.emails = tuple(self.emails)
        self.phones = tuple(self.phones)
        self.addresses = tuple(self.addresses)
        self.metadata = dict(self.metadata)
        if self.archived_at is not None:
            self.archived_at = as_utc(self.archived_at)
            if self.archived_at < self.created_at:
                raise ValidationError(
                    "archived_at cannot be earlier than created_at",
                    code="contact.archive.invalid_timestamp",
                )
        if self.status is ContactStatus.ARCHIVED and self.archived_at is None:
            raise ValidationError(
                "archived contacts require archived_at",
                code="contact.archive.timestamp_required",
            )
        if self.status is not ContactStatus.ARCHIVED and self.archived_at is not None:
            raise ValidationError(
                "non-archived contacts cannot carry archived_at",
                code="contact.archive.status_mismatch",
            )
        validate_contact_points(
            emails=self.emails,
            phones=self.phones,
            addresses=self.addresses,
        )
        validate_contact_identity(
            first_name=self.first_name,
            last_name=self.last_name,
            display_name=self.display_name,
            emails=self.emails,
            phones=self.phones,
        )

    def archive(self, at: datetime) -> None:
        """Archive the contact idempotently at an explicit domain timestamp."""

        timestamp = as_utc(at)
        if timestamp < self.created_at:
            raise ValidationError(
                "archive timestamp cannot be earlier than contact creation",
                code="contact.archive.invalid_timestamp",
            )
        if self.status is ContactStatus.ARCHIVED:
            return
        self.status = ContactStatus.ARCHIVED
        self.archived_at = timestamp
        self.updated_at = timestamp

    def ensure_mutable(self) -> None:
        """Reject profile mutation after archival."""

        if self.status is ContactStatus.ARCHIVED:
            raise InvalidStateError(
                "archived contacts cannot be updated",
                code="contact.archived",
                context={"contact_id": str(self.id)},
            )
