"""Backend-independent Contact query objects."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.contacts.entities import ContactStatus
from pycrmkit.contacts.policies import normalize_optional_text
from pycrmkit.contacts.value_objects import normalize_email, normalize_phone
from pycrmkit.core.ids import EntityId


@dataclass(frozen=True, slots=True)
class ContactQuery:
    """Normalized semantic filters understood by every ContactRepository adapter."""
    status: ContactStatus | None = None
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    owner_id: EntityId | None = None
    source: str | None = None
    include_archived: bool = False

    def __post_init__(self) -> None:
        if self.email is not None:
            object.__setattr__(self, "email", normalize_email(self.email))
        if self.phone is not None:
            object.__setattr__(self, "phone", normalize_phone(self.phone))
        if self.name is not None:
            object.__setattr__(self, "name", normalize_optional_text(self.name))
        if self.source is not None:
            object.__setattr__(self, "source", normalize_optional_text(self.source))
