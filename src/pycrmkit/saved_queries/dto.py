"""Patch DTOs for SavedQuery revisions."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.core.ids import EntityId
from pycrmkit.saved_queries.enums import SavedQueryVisibility
from pycrmkit.segments.expressions import QueryExpression
from pycrmkit.segments.ordering import SortExpression


class UnsetType:
    """Sentinel distinguishing omitted patch fields from explicit nulls."""

    __slots__ = ()


UNSET = UnsetType()


@dataclass(frozen=True, slots=True)
class SavedQueryRevision:
    """Requested changes for a new SavedQuery revision."""

    name: str | UnsetType = UNSET
    expression: QueryExpression | UnsetType = UNSET
    ordering: tuple[SortExpression, ...] | UnsetType = UNSET
    owner_id: EntityId | None | UnsetType = UNSET
    visibility: SavedQueryVisibility | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = field(default=UNSET)


__all__ = ["UNSET", "SavedQueryRevision", "UnsetType"]
