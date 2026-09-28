"""Portable SavedQuery repository filters."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import normalize_entity_kind
from pycrmkit.saved_queries.enums import SavedQueryStatus, SavedQueryVisibility


@dataclass(frozen=True, slots=True)
class SavedQueryQuery:
    """Backend-independent filters for SavedQuery definitions."""

    status: SavedQueryStatus | None = None
    visibility: SavedQueryVisibility | None = None
    entity_kind: str | None = None
    owner_id: EntityId | None = None
    include_archived: bool = False

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", SavedQueryStatus(self.status))
        if self.visibility is not None:
            object.__setattr__(
                self,
                "visibility",
                SavedQueryVisibility(self.visibility),
            )
        if self.entity_kind is not None:
            object.__setattr__(
                self,
                "entity_kind",
                normalize_entity_kind(self.entity_kind),
            )


__all__ = ["SavedQueryQuery"]
