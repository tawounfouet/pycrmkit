"""Typed Relationship service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pycrmkit.relationships.value_objects import RelationshipEndpoint, RelationshipType


class UnsetType:
    """Sentinel type distinguishing an omitted update from an explicit None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class RelationshipUpdate:
    """Partial relationship update preserving explicit clearing semantics."""

    source: RelationshipEndpoint | UnsetType = UNSET
    target: RelationshipEndpoint | UnsetType = UNSET
    relationship_type: RelationshipType | UnsetType = UNSET
    role: str | None | UnsetType = UNSET
    title: str | None | UnsetType = UNSET
    is_primary: bool | UnsetType = UNSET
    valid_from: datetime | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
