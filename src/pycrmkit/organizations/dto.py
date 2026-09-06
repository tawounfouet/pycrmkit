"""Typed Organization service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pycrmkit.core.ids import EntityId
from pycrmkit.organizations.entities import OrganizationStatus
from pycrmkit.organizations.value_objects import OrganizationAddress, OrganizationDomain


class UnsetType:
    """Sentinel type distinguishing an omitted update from an explicit None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class OrganizationUpdate:
    """Partial Organization update preserving explicit clearing semantics."""

    legal_name: str | UnsetType = UNSET
    trading_name: str | None | UnsetType = UNSET
    display_name: str | None | UnsetType = UNSET
    registration_number: str | None | UnsetType = UNSET
    tax_id: str | None | UnsetType = UNSET
    status: OrganizationStatus | UnsetType = UNSET
    owner_id: EntityId | None | UnsetType = UNSET
    source: str | None | UnsetType = UNSET
    domains: tuple[OrganizationDomain, ...] | UnsetType = UNSET
    addresses: tuple[OrganizationAddress, ...] | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
