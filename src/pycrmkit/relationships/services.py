"""Application service for Relationship lifecycle operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.relationships.dto import RelationshipUpdate, UnsetType
from pycrmkit.relationships.entities import Relationship, RelationshipId
from pycrmkit.relationships.queries import RelationshipQuery
from pycrmkit.relationships.repository import RelationshipRepository
from pycrmkit.relationships.value_objects import RelationshipEndpoint, RelationshipType

T = TypeVar("T")


@dataclass(slots=True)
class RelationshipService:
    """Framework-agnostic Relationship application service."""

    repository: RelationshipRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        source: RelationshipEndpoint,
        target: RelationshipEndpoint,
        relationship_type: RelationshipType,
        role: str | None = None,
        title: str | None = None,
        is_primary: bool = False,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Relationship:
        """Create and persist a directional CRM relationship."""
        now = self.clock.now()
        relationship = Relationship(
            id=self.id_factory.new(RelationshipId),
            created_at=now,
            updated_at=now,
            source=source,
            target=target,
            relationship_type=relationship_type,
            role=role,
            title=title,
            is_primary=is_primary,
            valid_from=valid_from or now,
            valid_until=valid_until,
            metadata=dict(metadata or {}),
        )
        self.repository.save(relationship)
        return relationship

    def get(self, relationship_id: RelationshipId) -> Relationship:
        """Return a relationship using the repository's not-found contract."""
        return self.repository.get(relationship_id)

    def update(
        self,
        relationship_id: RelationshipId,
        changes: RelationshipUpdate,
    ) -> Relationship:
        """Validate a typed partial update and persist the resulting relationship."""
        current = self.repository.get(relationship_id)
        current.ensure_mutable()
        candidate = Relationship(
            id=current.id,
            created_at=current.created_at,
            updated_at=self.clock.now(),
            source=self._value(changes.source, current.source),
            target=self._value(changes.target, current.target),
            relationship_type=self._value(
                changes.relationship_type,
                current.relationship_type,
            ),
            role=self._value(changes.role, current.role),
            title=self._value(changes.title, current.title),
            is_primary=self._value(changes.is_primary, current.is_primary),
            valid_from=self._value(changes.valid_from, current.valid_from),
            valid_until=current.valid_until,
            metadata=self._value(changes.metadata, current.metadata),
        )
        self.repository.save(candidate)
        return candidate

    def end(self, relationship_id: RelationshipId) -> Relationship:
        """End a relationship through the repository's shared semantic contract."""
        return self.repository.end(relationship_id, self.clock.now())

    def search(
        self,
        query: RelationshipQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Relationship]:
        """Search relationships using backend-independent filters and pagination."""
        return self.repository.search(
            query or RelationshipQuery(),
            page or OffsetPageRequest(),
        )

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
