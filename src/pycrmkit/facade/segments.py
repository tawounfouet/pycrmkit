"""Segments facade namespace."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import IntegrationError
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.saved_queries import SavedQueryId, SavedQueryUnitOfWork
from pycrmkit.segments import (
    QueryExpression,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentMode,
    SegmentQuery,
    SegmentService,
    SegmentUnitOfWork,
)


class SegmentsAPI:
    """Transactional facade for Static and Dynamic Segments."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

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
        with self._runtime.uow_factory() as uow:
            service = self._service(self._capabilities(uow))
            segment = service.create(
                key=key,
                name=name,
                entity_kind=entity_kind,
                mode=mode,
                description=description,
                query=query,
                owner_id=owner_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="segment.created",
                aggregate_type="segment",
                aggregate_id=segment.id,
                changes={"fields": ["key", "name", "entity_kind", "mode"]},
                payload={
                    "key": segment.key,
                    "entity_kind": segment.entity_kind,
                    "mode": segment.mode.value,
                },
            )
            uow.commit()
            return segment

    def create_static(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        description: str | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        return self.create(
            key=key,
            name=name,
            entity_kind=entity_kind,
            mode=SegmentMode.STATIC,
            description=description,
            owner_id=owner_id,
            metadata=metadata,
        )

    def create_dynamic(
        self,
        *,
        key: str,
        name: str,
        entity_kind: str,
        query: QueryExpression,
        description: str | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        return self.create(
            key=key,
            name=name,
            entity_kind=entity_kind,
            mode=SegmentMode.DYNAMIC,
            description=description,
            query=query,
            owner_id=owner_id,
            metadata=metadata,
        )

    def create_dynamic_from_saved_query(
        self,
        *,
        key: str,
        name: str,
        saved_query_id: SavedQueryId,
        revision: int | None = None,
        description: str | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Segment:
        with self._runtime.uow_factory() as uow:
            capabilities = self._capabilities(uow)
            if not isinstance(uow, SavedQueryUnitOfWork):
                raise IntegrationError(
                    "Saved Queries are not available for this persistence adapter yet",
                    code="saved_query.persistence.unsupported",
                )
            saved_query = uow.saved_queries.get(saved_query_id, revision)
            segment = self._service(capabilities).create(
                key=key,
                name=name,
                entity_kind=saved_query.entity_kind,
                mode=SegmentMode.DYNAMIC,
                description=description,
                query=saved_query.expression,
                saved_query_id=saved_query.id,
                saved_query_revision=saved_query.revision,
                owner_id=owner_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="segment.created",
                aggregate_type="segment",
                aggregate_id=segment.id,
                changes={
                    "fields": [
                        "key",
                        "name",
                        "entity_kind",
                        "mode",
                        "saved_query_id",
                        "saved_query_revision",
                    ]
                },
                payload={
                    "key": segment.key,
                    "entity_kind": segment.entity_kind,
                    "mode": segment.mode.value,
                    "saved_query_id": str(saved_query.id),
                    "saved_query_revision": saved_query.revision,
                },
            )
            uow.commit()
            return segment

    def get(self, segment_id: SegmentId) -> Segment:
        with self._runtime.uow_factory() as uow:
            return self._capabilities(uow).segments.get(segment_id)

    def list(
        self,
        query: SegmentQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Segment]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).list(query, page)

    def archive(self, segment_id: SegmentId) -> Segment:
        with self._runtime.uow_factory() as uow:
            segment = self._service(self._capabilities(uow)).archive(segment_id)
            self._runtime.record_change(
                uow,
                event_type="segment.archived",
                aggregate_type="segment",
                aggregate_id=segment.id,
                changes={"fields": ["status", "archived_at", "revision"]},
            )
            uow.commit()
            return segment

    def preview(
        self,
        *,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).preview(
                entity_kind=entity_kind,
                expression=expression,
                page=page,
            )

    def evaluate(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).evaluate(segment_id, page)

    def count(self, segment_id: SegmentId) -> int:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).count(segment_id)

    def add_member(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
        *,
        source: str = "manual",
        metadata: Mapping[str, object] | None = None,
    ) -> SegmentMember:
        with self._runtime.uow_factory() as uow:
            member = self._service(self._capabilities(uow)).add_member(
                segment_id,
                entity,
                source=source,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="segment.member_added",
                aggregate_type="segment",
                aggregate_id=segment_id,
                changes={"fields": ["members"]},
                payload={
                    "entity_kind": entity.kind,
                    "entity_id": str(entity.id),
                    "source": member.source,
                },
            )
            uow.commit()
            return member

    def remove_member(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = self._service(self._capabilities(uow)).remove_member(
                segment_id,
                entity,
            )
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="segment.member_removed",
                    aggregate_type="segment",
                    aggregate_id=segment_id,
                    changes={"fields": ["members"]},
                    payload={
                        "entity_kind": entity.kind,
                        "entity_id": str(entity.id),
                    },
                )
            uow.commit()
            return removed

    def contains(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).contains(segment_id, entity)

    def _service(self, capabilities: SegmentUnitOfWork) -> SegmentService:
        return SegmentService(
            capabilities.segments,
            capabilities.segment_memberships,
            capabilities.segment_query_executor,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
        )

    @staticmethod
    def _capabilities(uow: object) -> SegmentUnitOfWork:
        if not isinstance(uow, SegmentUnitOfWork):
            raise IntegrationError(
                "Segmentation is not available for this persistence adapter yet",
                code="segment.persistence.unsupported",
            )
        return uow


__all__ = ["SegmentsAPI"]
