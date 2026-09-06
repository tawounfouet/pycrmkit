"""In-memory RelationshipRepository implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.relationships.entities import Relationship, RelationshipId
from pycrmkit.relationships.queries import RelationshipQuery
from pycrmkit.storage.memory._state import _MemoryState


class MemoryRelationshipRepository:
    """Copy-isolated, contract-conformant Relationship repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, relationship_id: RelationshipId) -> Relationship:
        relationship = self.find(relationship_id)
        if relationship is None:
            raise NotFoundError(
                "Relationship not found",
                code="relationship.not_found",
                context={"relationship_id": str(relationship_id)},
            )
        return relationship

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        relationship = self._state.relationships.get(relationship_id)
        return deepcopy(relationship) if relationship is not None else None

    def save(self, relationship: Relationship) -> None:
        self._state.relationships[relationship.id] = deepcopy(relationship)

    def end(self, relationship_id: RelationshipId, ended_at: datetime) -> Relationship:
        relationship = self.get(relationship_id)
        relationship.end(ended_at)
        self.save(relationship)
        return relationship

    def search(
        self,
        query: RelationshipQuery,
        page: OffsetPageRequest,
    ) -> Page[Relationship]:
        relationships = list(self._state.relationships.values())
        if query.active_at is not None:
            relationships = [item for item in relationships if item.is_active(query.active_at)]
        elif not query.include_ended:
            relationships = [item for item in relationships if not item.is_ended]
        if query.entity is not None:
            relationships = [
                item
                for item in relationships
                if item.source == query.entity or item.target == query.entity
            ]
        if query.source is not None:
            relationships = [item for item in relationships if item.source == query.source]
        if query.target is not None:
            relationships = [item for item in relationships if item.target == query.target]
        if query.relationship_type is not None:
            relationships = [
                item
                for item in relationships
                if item.relationship_type == query.relationship_type
            ]
        if query.is_primary is not None:
            relationships = [item for item in relationships if item.is_primary is query.is_primary]
        relationships.sort(key=lambda item: (item.created_at, item.id))
        total = len(relationships)
        selected = relationships[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
