"""Application service for reusable, versioned CRM queries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeVar

from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import ConflictError
from pycrmkit.saved_queries.dto import SavedQueryRevision, UnsetType
from pycrmkit.saved_queries.entities import SavedQuery, SavedQueryId
from pycrmkit.saved_queries.enums import SavedQueryStatus, SavedQueryVisibility
from pycrmkit.saved_queries.queries import SavedQueryQuery
from pycrmkit.saved_queries.repository import SavedQueryRepository
from pycrmkit.segments.expressions import QueryExpression
from pycrmkit.segments.ordering import SortExpression
from pycrmkit.segments.repository import SegmentQueryExecutor

T = TypeVar("T")


@dataclass(slots=True)
class SavedQueryService:
    """Framework-independent SavedQuery lifecycle and execution."""

    repository: SavedQueryRepository
    query_executor: SegmentQueryExecutor
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
        owner_id: EntityId | None = None,
        visibility: SavedQueryVisibility = SavedQueryVisibility.PRIVATE,
        metadata: Mapping[str, object] | None = None,
    ) -> SavedQuery:
        self.query_executor.validate(entity_kind, expression, tuple(ordering))
        now = self.clock.now()
        query = SavedQuery(
            id=self.id_factory.new(SavedQueryId),
            created_at=now,
            updated_at=now,
            key=key,
            name=name,
            entity_kind=entity_kind,
            expression=expression,
            ordering=tuple(ordering),
            owner_id=owner_id,
            visibility=visibility,
            metadata=dict(metadata or {}),
        )
        self.repository.save(query)
        return query

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        return self.repository.get(query_id, revision)

    def list(
        self,
        query: SavedQueryQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[SavedQuery]:
        return self.repository.search(
            query or SavedQueryQuery(),
            page or OffsetPageRequest(),
        )

    def update(
        self,
        query_id: SavedQueryId,
        changes: SavedQueryRevision,
        *,
        expected_revision: int | None = None,
    ) -> SavedQuery:
        current = self.repository.get(query_id)
        current.ensure_active()
        if expected_revision is not None and current.revision != expected_revision:
            raise ConflictError(
                "saved-query revision has changed",
                code="saved_query.revision.conflict",
                context={
                    "expected": expected_revision,
                    "actual": current.revision,
                },
            )
        expression = self._value(changes.expression, current.expression)
        ordering = tuple(self._value(changes.ordering, current.ordering))
        self.query_executor.validate(current.entity_kind, expression, ordering)
        revised = SavedQuery(
            id=current.id,
            created_at=current.created_at,
            updated_at=self.clock.now(),
            key=current.key,
            name=self._value(changes.name, current.name),
            entity_kind=current.entity_kind,
            expression=expression,
            ordering=ordering,
            owner_id=self._value(changes.owner_id, current.owner_id),
            visibility=self._value(changes.visibility, current.visibility),
            status=current.status,
            revision=current.revision + 1,
            metadata=dict(self._value(changes.metadata, current.metadata)),
            archived_at=current.archived_at,
        )
        self.repository.save(revised)
        return revised

    def archive(
        self,
        query_id: SavedQueryId,
        *,
        expected_revision: int | None = None,
    ) -> SavedQuery:
        current = self.repository.get(query_id)
        if current.status is SavedQueryStatus.ARCHIVED:
            return current
        if expected_revision is not None and current.revision != expected_revision:
            raise ConflictError(
                "saved-query revision has changed",
                code="saved_query.revision.conflict",
                context={
                    "expected": expected_revision,
                    "actual": current.revision,
                },
            )
        now = self.clock.now()
        archived = SavedQuery(
            id=current.id,
            created_at=current.created_at,
            updated_at=now,
            key=current.key,
            name=current.name,
            entity_kind=current.entity_kind,
            expression=current.expression,
            ordering=current.ordering,
            owner_id=current.owner_id,
            visibility=current.visibility,
            status=SavedQueryStatus.ARCHIVED,
            revision=current.revision + 1,
            metadata=current.metadata,
            archived_at=now,
        )
        self.repository.save(archived)
        return archived

    def execute(
        self,
        query_id: SavedQueryId,
        page: OffsetPageRequest | None = None,
        *,
        revision: int | None = None,
    ) -> Page[EntityReference]:
        query = self.repository.get(query_id, revision)
        return self.query_executor.execute(
            query.entity_kind,
            query.expression,
            page or OffsetPageRequest(),
            at=self.clock.now(),
            ordering=query.ordering,
        )

    def preview(
        self,
        *,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        ordering = tuple(ordering)
        self.query_executor.validate(entity_kind, expression, ordering)
        return self.query_executor.execute(
            entity_kind,
            expression,
            page or OffsetPageRequest(),
            at=self.clock.now(),
            ordering=ordering,
        )

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value


__all__ = ["SavedQueryService"]
