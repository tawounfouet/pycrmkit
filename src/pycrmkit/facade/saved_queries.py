"""Saved Queries facade namespace."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import IntegrationError
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryRevision,
    SavedQueryService,
    SavedQueryUnitOfWork,
    SavedQueryVisibility,
    UnsetType,
)
from pycrmkit.segments import QueryExpression, SortExpression


class SavedQueriesAPI:
    """Transactional facade for reusable CRM selection semantics."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

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
        with self._runtime.uow_factory() as uow:
            service = self._service(self._capabilities(uow))
            query = service.create(
                key=key,
                name=name,
                entity_kind=entity_kind,
                expression=expression,
                ordering=ordering,
                owner_id=owner_id,
                visibility=visibility,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="saved_query.created",
                aggregate_type="saved_query",
                aggregate_id=query.id,
                changes={
                    "fields": [
                        "key",
                        "name",
                        "entity_kind",
                        "expression",
                        "ordering",
                    ]
                },
                payload={"revision": query.revision},
            )
            uow.commit()
            return query

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        with self._runtime.uow_factory() as uow:
            return self._capabilities(uow).saved_queries.get(query_id, revision)

    def list(
        self,
        query: SavedQueryQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[SavedQuery]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).list(query, page)

    def revisions(self, query_id: SavedQueryId) -> tuple[SavedQuery, ...]:
        with self._runtime.uow_factory() as uow:
            return self._capabilities(uow).saved_queries.list_revisions(query_id)

    def update(
        self,
        query_id: SavedQueryId,
        changes: SavedQueryRevision,
        *,
        expected_revision: int | None = None,
    ) -> SavedQuery:
        with self._runtime.uow_factory() as uow:
            query = self._service(self._capabilities(uow)).update(
                query_id,
                changes,
                expected_revision=expected_revision,
            )
            self._runtime.record_change(
                uow,
                event_type="saved_query.updated",
                aggregate_type="saved_query",
                aggregate_id=query.id,
                changes={"fields": self._changed_fields(changes)},
                payload={"revision": query.revision},
            )
            uow.commit()
            return query

    def archive(
        self,
        query_id: SavedQueryId,
        *,
        expected_revision: int | None = None,
    ) -> SavedQuery:
        with self._runtime.uow_factory() as uow:
            before = self._capabilities(uow).saved_queries.get(query_id)
            query = self._service(self._capabilities(uow)).archive(
                query_id,
                expected_revision=expected_revision,
            )
            if query.revision != before.revision:
                self._runtime.record_change(
                    uow,
                    event_type="saved_query.archived",
                    aggregate_type="saved_query",
                    aggregate_id=query.id,
                    changes={"fields": ["status", "archived_at", "revision"]},
                    payload={"revision": query.revision},
                )
            uow.commit()
            return query

    def execute(
        self,
        query_id: SavedQueryId,
        page: OffsetPageRequest | None = None,
        *,
        revision: int | None = None,
    ) -> Page[EntityReference]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).execute(
                query_id,
                page,
                revision=revision,
            )

    def preview(
        self,
        *,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).preview(
                entity_kind=entity_kind,
                expression=expression,
                ordering=ordering,
                page=page,
            )

    def _service(self, capabilities: SavedQueryUnitOfWork) -> SavedQueryService:
        return SavedQueryService(
            capabilities.saved_queries,
            capabilities.segment_query_executor,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
        )

    @staticmethod
    def _capabilities(uow: object) -> SavedQueryUnitOfWork:
        if not isinstance(uow, SavedQueryUnitOfWork):
            raise IntegrationError(
                "Saved Queries are not available for this persistence adapter yet",
                code="saved_query.persistence.unsupported",
            )
        return uow

    @staticmethod
    def _changed_fields(changes: SavedQueryRevision) -> list[str]:
        return [
            name
            for name in (
                "name",
                "expression",
                "ordering",
                "owner_id",
                "visibility",
                "metadata",
            )
            if not isinstance(getattr(changes, name), UnsetType)
        ]


__all__ = ["SavedQueriesAPI"]
