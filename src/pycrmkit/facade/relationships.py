"""Relationships facade namespace."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.facade._runtime import CRMRuntime, revision_fields
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipQuery,
    RelationshipService,
    RelationshipType,
    RelationshipUpdate,
)


class RelationshipsAPI:
    """Transactional facade namespace for Relationships."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

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
        with self._runtime.uow_factory() as uow:
            relationship = RelationshipService(
                uow.relationships,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                source=source,
                target=target,
                relationship_type=relationship_type,
                role=role,
                title=title,
                is_primary=is_primary,
                valid_from=valid_from,
                valid_until=valid_until,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="relationship.created",
                aggregate_type="relationship",
                aggregate_id=relationship.id,
                changes={"fields": ["source", "target", "relationship_type"]},
            )
            uow.commit()
            return relationship

    def get(self, relationship_id: RelationshipId) -> Relationship:
        with self._runtime.uow_factory() as uow:
            return uow.relationships.get(relationship_id)

    def update(
        self,
        relationship_id: RelationshipId,
        changes: RelationshipUpdate,
    ) -> Relationship:
        with self._runtime.uow_factory() as uow:
            relationship = RelationshipService(
                uow.relationships,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).update(relationship_id, changes)
            self._runtime.record_change(
                uow,
                event_type="relationship.updated",
                aggregate_type="relationship",
                aggregate_id=relationship.id,
                changes={"fields": revision_fields(changes)},
            )
            uow.commit()
            return relationship

    def end(self, relationship_id: RelationshipId) -> Relationship:
        with self._runtime.uow_factory() as uow:
            relationship = RelationshipService(
                uow.relationships,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).end(relationship_id)
            self._runtime.record_change(
                uow,
                event_type="relationship.ended",
                aggregate_type="relationship",
                aggregate_id=relationship.id,
                changes={"fields": ["valid_until"]},
            )
            uow.commit()
            return relationship

    def search(
        self,
        query: RelationshipQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Relationship]:
        with self._runtime.uow_factory() as uow:
            return RelationshipService(uow.relationships).search(query, page)
