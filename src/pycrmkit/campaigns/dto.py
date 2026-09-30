"""Typed Campaign service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from pycrmkit.core.ids import EntityId


class UnsetType:
    """Sentinel distinguishing omission from explicit clearing."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class CampaignUpdate:
    """Editable Campaign metadata; lifecycle state uses explicit transitions."""

    name: str | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    starts_at: datetime | None | UnsetType = UNSET
    ends_at: datetime | None | UnsetType = UNSET
    owner_id: EntityId | None | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = field(default=UNSET)


__all__ = ["CampaignUpdate", "UNSET", "UnsetType"]
