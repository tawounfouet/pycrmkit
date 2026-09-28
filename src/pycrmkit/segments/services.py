"""Application service for Segment lifecycle and evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.segments.entities import (
    SEGMENTABLE_ENTITY_KINDS,
    Segment,
    SegmentId,
    SegmentMember,
)
from pycrmkit.segments.enums import SegmentMode
from pycrmkit.segments.expressions import QueryExpression
from pycrmkit.segments.queries import SegmentQuery
from pycrmkit.segments.repository import (
    SegmentMembershipRepository,
    SegmentQueryExecutor,
    SegmentRepository,
)
from pycrmkit.segments.schema import default_query_schemas


@dataclass(slots=True)
class SegmentService:
    """Framework-independent Segment application service."""

    repository: SegmentRepository
    memberships: SegmentMembershipRepository
    query_executor: SegmentQueryExecutor
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        mode: SegmentMode,
        description: str | None = None,
        query: QueryExpression | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        """Create a Static or Dynamic Segment."""

        mode = SegmentMode(mode)
        if mode is SegmentMode.SNAPSHOT:
            raise InvalidStateError(
                "snapshot creation is deferred to the snapshot milestone",
                code="segment.snapshot.creation_deferred",
            )
        entity_kind = entity_kind.strip().casefold()
        if entity_kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": entity_kind},
            )
        if query is not None:
            default_query_schemas().get(entity_kind).validate(query)

        now = self.clock.now()
        segment = Segment(
            id=self.id_factory.new(SegmentId),
            created_at=now,
            updated_at=now,
            key=key,
            name=name,
            entity_kind=entity_kind,
            mode=mode,
            description=description,
            query=query,
            owner_id=owner_id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(segment)
        return segment

    def get(self, segment_id: SegmentId) -> Segment:
        return self.repository.get(segment_id)

    def list(
        self,
        query: SegmentQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Segment]:
        return self.repository.search(
            query or SegmentQuery(),
            page or OffsetPageRequest(),
        )

    def archive(self, segment_id: SegmentId) -> Segment:
        segment = self.repository.get(segment_id)
        segment.archive(self.clock.now())
        self.repository.save(segment)
        return segment

    def preview(
        self,
        *,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        kind = entity_kind.strip().casefold()
        default_query_schemas().get(kind).validate(expression)
        return self.query_executor.execute(
            kind,
            expression,
            page or OffsetPageRequest(),
        )

    def evaluate(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        segment = self.repository.get(segment_id)
        request = page or OffsetPageRequest()
        if segment.mode is SegmentMode.DYNAMIC:
            assert segment.query is not None
            return self.query_executor.execute(
                segment.entity_kind,
                segment.query,
                request,
            )
        stored = self.memberships.list(segment.id, request)
        return Page(
            items=tuple(member.entity for member in stored.items),
            limit=stored.limit,
            offset=stored.offset,
            total=stored.total,
        )

    def count(self, segment_id: SegmentId) -> int:
        segment = self.repository.get(segment_id)
        if segment.mode is SegmentMode.DYNAMIC:
            assert segment.query is not None
            return self.query_executor.count(segment.entity_kind, segment.query)
        return self.memberships.count(segment.id)

    def add_member(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
        *,
        source: str = "manual",
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> SegmentMember:
        segment = self.repository.get(segment_id)
        segment.ensure_membership_writable()
        self._validate_member(segment, entity)
        member = SegmentMember(
            segment_id=segment.id,
            entity=entity,
            added_at=self.clock.now(),
            source=source,
            actor_id=actor_id,
            metadata=dict(metadata or {}),
        )
        return self.memberships.add(member)

    def remove_member(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        segment = self.repository.get(segment_id)
        segment.ensure_membership_writable()
        self._validate_member_kind(segment, entity)
        return self.memberships.remove(segment.id, entity)

    def contains(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        segment = self.repository.get(segment_id)
        self._validate_member_kind(segment, entity)
        if segment.mode is SegmentMode.DYNAMIC:
            assert segment.query is not None
            if not self.query_executor.exists(entity):
                return False
            page = self.query_executor.execute(
                segment.entity_kind,
                segment.query,
                OffsetPageRequest(limit=OffsetPageRequest.MAX_LIMIT),
            )
            if entity in page.items:
                return True
            if not page.has_next:
                return False
            return self._dynamic_contains(segment, entity)
        return self.memberships.contains(segment.id, entity)

    def _dynamic_contains(self, segment: Segment, entity: EntityReference) -> bool:
        assert segment.query is not None
        offset = 0
        while True:
            page = self.query_executor.execute(
                segment.entity_kind,
                segment.query,
                OffsetPageRequest(
                    limit=OffsetPageRequest.MAX_LIMIT,
                    offset=offset,
                ),
            )
            if entity in page.items:
                return True
            if not page.has_next:
                return False
            offset += len(page.items)

    def _validate_member(self, segment: Segment, entity: EntityReference) -> None:
        self._validate_member_kind(segment, entity)
        if not self.query_executor.exists(entity):
            raise ValidationError(
                "segment member must reference an existing CRM entity",
                code="segment.member.not_found",
                context={
                    "entity_kind": entity.kind,
                    "entity_id": str(entity.id),
                },
            )

    @staticmethod
    def _validate_member_kind(segment: Segment, entity: EntityReference) -> None:
        if entity.kind != segment.entity_kind:
            raise ValidationError(
                "segment member kind must match segment entity kind",
                code="segment.member.kind_mismatch",
                context={
                    "segment_kind": segment.entity_kind,
                    "entity_kind": entity.kind,
                },
            )


__all__ = ["SegmentService"]
