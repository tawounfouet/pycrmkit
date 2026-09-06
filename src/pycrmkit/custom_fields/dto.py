"""Typed Custom Field service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pycrmkit.custom_fields.value_objects import CustomFieldOption


class UnsetType:
    """Sentinel distinguishing an omitted definition revision field."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class CustomFieldDefinitionRevision:
    """Partial definition revision; every successful revision increments schema version."""

    label: str | UnsetType = UNSET
    required: bool | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    applies_to: tuple[str, ...] | UnsetType = UNSET
    options: tuple[CustomFieldOption, ...] | UnsetType = UNSET
    reference_kinds: tuple[str, ...] | UnsetType = UNSET
    active: bool | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
