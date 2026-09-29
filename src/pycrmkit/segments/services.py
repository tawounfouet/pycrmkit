"""Application service for Segment lifecycle and evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory, UUIDId
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
from pycrmkit.segments.expressions import QueryExpression, expression_to_dict
from pycrmkit.segments.queries import SegmentQuery
from pycrmkit.segments.repository import (
    SegmentMembershipRepository,
    SegmentQueryExecutor,
    SegmentRepository,
)


@dataclass(slots=True)
class SegmentService:
    """Framework-independent Segment application service."""

    repository: SegmentRepository
    memberships: SegmentMembershipRepository
    query_executor: SegmentQueryExecutor
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    MAX_BULK_MEMBERS = 1000

    def create(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        mode: SegmentMode,
        description: str | None = None,
        query: QueryExpression | None = None,
        saved_query_id: UUIDId | None = None,
        saved_query_revision: int | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        """Create a Static or Dynamic Segment."""

        mode = SegmentMode(mode)
        if mode is SegmentMode.SNAPSHOT:
            raise InvalidStateError(
                "snapshot segments must be materialized atomically",
                code="segment.snapshot.dedicated_creation_required",
            )
        entity_kind = entity_kind.strip().casefold()
        if entity_kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": entity_kind},
            )
        if query is not None:
            self.query_executor.validate(entity_kind, query)

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
            saved_query_id=saved_query_id,
            saved_query_revision=saved_query_revision,
            owner_id=owner_id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(segment)
        return segment

    def create_snapshot(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        expression: QueryExpression,
        description: str | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        """Freeze one query result into an immutable Snapshot Segment."""

        kind = entity_kind.strip().casefold()
        if kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": kind},
            )
        self.query_executor.validate(kind, expression)
        snapshot_metadata = dict(metadata or {})
        snapshot_metadata.setdefault(
            "snapshot_source",
            {
                "kind": "expression",
                "expression": expression_to_dict(expression),
            },
        )
        snapshot = self._new_snapshot(
            key=key,
            name=name,
            entity_kind=kind,
            description=description,
            owner_id=owner_id,
            metadata=snapshot_metadata,
        )
        self._materialize_expression(snapshot, expression)
        return snapshot

    def snapshot(
        self,
        source_segment_id: SegmentId,
        *,
        key: str,
        name: str,
        description: str | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        """Freeze the current membership of an existing Segment."""

        source = self.repository.get(source_segment_id)
        snapshot_metadata = dict(metadata or {})
        snapshot_metadata.setdefault(
            "snapshot_source",
            {
                "kind": "segment",
                "segment_id": str(source.id),
                "segment_revision": source.revision,
            },
        )
        snapshot = self._new_snapshot(
            key=key,
            name=name,
            entity_kind=source.entity_kind,
            description=description,
            owner_id=owner_id,
            metadata=snapshot_metadata,
        )
        if source.mode is SegmentMode.DYNAMIC:
            assert source.query is not None
            self._materialize_expression(snapshot, source.query)
        else:
            self._copy_stored_members(source, snapshot)
        return snapshot

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
        self.query_executor.validate(kind, expression)
        return self.query_executor.execute(
            kind,
            expression,
            page or OffsetPageRequest(),
            at=self.clock.now(),
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
                at=self.clock.now(),
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
            return self.query_executor.count(
                segment.entity_kind,
                segment.query,
                at=self.clock.now(),
            )
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

    def add_members(
        self,
        segment_id: SegmentId,
        entities: Iterable[EntityReference],
        *,
        source: str = "manual",
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[SegmentMember, ...]:
        """Add one bounded membership batch atomically."""

        segment = self.repository.get(segment_id)
        segment.ensure_membership_writable()
        references = tuple(entities)
        self._validate_bulk(references)
        for entity in references:
            self._validate_member(segment, entity)
        now = self.clock.now()
        values = tuple(
            SegmentMember(
                segment_id=segment.id,
                entity=entity,
                added_at=now,
                source=source,
                actor_id=actor_id,
                metadata=dict(metadata or {}),
            )
            for entity in references
        )
        return self.memberships.add_many(values)

    def remove_member(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        segment = self.repository.get(segment_id)
        segment.ensure_membership_writable()
        self._validate_member_kind(segment, entity)
        return self.memberships.remove(segment.id, entity)

    def remove_members(
        self,
        segment_id: SegmentId,
        entities: Iterable[EntityReference],
    ) -> int:
        """Remove one bounded membership batch idempotently."""

        segment = self.repository.get(segment_id)
        segment.ensure_membership_writable()
        references = tuple(dict.fromkeys(entities))
        self._validate_bulk(references)
        for entity in references:
            self._validate_member_kind(segment, entity)
        return self.memberships.remove_many(segment.id, references)

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
                at=self.clock.now(),
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
                at=self.clock.now(),
            )
            if entity in page.items:
                return True
            if not page.has_next:
                return False
            offset += len(page.items)

    def _new_snapshot(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        description: str | None,
        owner_id: EntityId | None,
        metadata: Mapping[str, object],
    ) -> Segment:
        now = self.clock.now()
        snapshot = Segment(
            id=self.id_factory.new(SegmentId),
            created_at=now,
            updated_at=now,
            key=key,
            name=name,
            entity_kind=entity_kind,
            mode=SegmentMode.SNAPSHOT,
            description=description,
            owner_id=owner_id,
            metadata=dict(metadata),
        )
        self.repository.save(snapshot)
        return snapshot

    def _materialize_expression(
        self,
        snapshot: Segment,
        expression: QueryExpression,
    ) -> None:
        offset = 0
        captured_at = self.clock.now()
        while True:
            page = self.query_executor.execute(
                snapshot.entity_kind,
                expression,
                OffsetPageRequest(
                    limit=OffsetPageRequest.MAX_LIMIT,
                    offset=offset,
                ),
                at=captured_at,
            )
            if page.items:
                members = tuple(
                    SegmentMember(
                        segment_id=snapshot.id,
                        entity=entity,
                        added_at=captured_at,
                        source="snapshot",
                        metadata={},
                    )
                    for entity in page.items
                )
                self.memberships.add_many(members)
            if not page.has_next:
                return
            offset += len(page.items)

    def _copy_stored_members(
        self,
        source: Segment,
        snapshot: Segment,
    ) -> None:
        offset = 0
        captured_at = self.clock.now()
        while True:
            page = self.memberships.list(
                source.id,
                OffsetPageRequest(
                    limit=OffsetPageRequest.MAX_LIMIT,
                    offset=offset,
                ),
            )
            if page.items:
                self.memberships.add_many(
                    tuple(
                        SegmentMember(
                            segment_id=snapshot.id,
                            entity=member.entity,
                            added_at=captured_at,
                            source="snapshot",
                            metadata={},
                        )
                        for member in page.items
                    )
                )
            if not page.has_next:
                return
            offset += len(page.items)

    def _validate_bulk(
        self,
        entities: tuple[EntityReference, ...],
    ) -> None:
        if len(entities) > self.MAX_BULK_MEMBERS:
            raise ValidationError(
                "segment membership batch exceeds the configured limit",
                code="segment.member.bulk_limit",
                context={"max_members": self.MAX_BULK_MEMBERS},
            )
        if len(entities) != len(set(entities)):
            raise ValidationError(
                "segment membership batch contains duplicate references",
                code="segment.member.batch_duplicate",
            )

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
