"""Backend-independent Relationship query objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pycrmkit.core.time import as_utc
from pycrmkit.relationships.value_objects import RelationshipEndpoint, RelationshipType


@dataclass(frozen=True, slots=True)
class RelationshipQuery:
    """Semantic filters understood by every RelationshipRepository adapter."""

    entity: RelationshipEndpoint | None = None
    source: RelationshipEndpoint | None = None
    target: RelationshipEndpoint | None = None
    relationship_type: RelationshipType | None = None
    is_primary: bool | None = None
    active_at: datetime | None = None
    include_ended: bool = False

    def __post_init__(self) -> None:
        if self.active_at is not None:
            object.__setattr__(self, "active_at", as_utc(self.active_at))
