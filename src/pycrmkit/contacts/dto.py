"""Typed Contact service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pycrmkit.contacts.entities import ContactStatus
from pycrmkit.contacts.value_objects import Address, ContactEmail, ContactPhone
from pycrmkit.core.ids import EntityId


class UnsetType:
    """Sentinel type distinguishing an omitted update from an explicit None."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class ContactUpdate:
    """Partial Contact update preserving explicit field clearing semantics."""
    first_name: str | None | UnsetType = UNSET
    last_name: str | None | UnsetType = UNSET
    display_name: str | None | UnsetType = UNSET
    status: ContactStatus | UnsetType = UNSET
    owner_id: EntityId | None | UnsetType = UNSET
    source: str | None | UnsetType = UNSET
    emails: tuple[ContactEmail, ...] | UnsetType = UNSET
    phones: tuple[ContactPhone, ...] | UnsetType = UNSET
    addresses: tuple[Address, ...] | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
