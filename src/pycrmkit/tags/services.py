"""Application service for Tag lifecycle and assignment operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.tags.entities import Tag, TagAssignment, TagAssignmentId, TagId
from pycrmkit.tags.queries import TagQuery
from pycrmkit.tags.repository import TagRepository
from pycrmkit.tags.value_objects import TagName


@dataclass(slots=True)
class TagService:
    """Framework-agnostic Tag application service."""

    repository: TagRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        name: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> Tag:
        """Create a normalized Tag; repository uniqueness is authoritative."""
        now = self.clock.now()
        tag = Tag(
            id=self.id_factory.new(TagId),
            created_at=now,
            updated_at=now,
            name=TagName(name),
            metadata=dict(metadata or {}),
        )
        self.repository.save(tag)
        return tag

    def get(self, tag_id: TagId) -> Tag:
        return self.repository.get(tag_id)

    def search(
        self,
        query: TagQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Tag]:
        return self.repository.search(query or TagQuery(), page or OffsetPageRequest())

    def assign(self, tag_id: TagId, entity: EntityReference) -> TagAssignment:
        """Assign an existing Tag to an entity exactly once."""
        self.repository.get(tag_id)
        now = self.clock.now()
        assignment = TagAssignment(
            id=self.id_factory.new(TagAssignmentId),
            created_at=now,
            updated_at=now,
            tag_id=tag_id,
            entity=entity,
        )
        return self.repository.assign(assignment)

    def remove(self, tag_id: TagId, entity: EntityReference) -> bool:
        """Remove an assignment idempotently."""
        return self.repository.remove(tag_id, entity, self.clock.now())

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest | None = None,
    ) -> Page[Tag]:
        return self.repository.list_for_entity(entity, page or OffsetPageRequest())
