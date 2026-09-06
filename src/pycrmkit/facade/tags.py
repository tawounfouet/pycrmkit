"""Tags facade namespace."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.tags import Tag, TagAssignment, TagId, TagQuery, TagService


class TagsAPI:
    """Transactional facade namespace for Tags and assignments."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(self, name: str, *, metadata: Mapping[str, object] | None = None) -> Tag:
        with self._runtime.uow_factory() as uow:
            tag = TagService(
                uow.tags,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(name, metadata=metadata)
            self._runtime.record_change(
                uow,
                event_type="tag.created",
                aggregate_type="tag",
                aggregate_id=tag.id,
                changes={"fields": ["name"]},
            )
            uow.commit()
            return tag

    def get(self, tag_id: TagId) -> Tag:
        with self._runtime.uow_factory() as uow:
            return uow.tags.get(tag_id)

    def search(
        self,
        query: TagQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Tag]:
        with self._runtime.uow_factory() as uow:
            return TagService(uow.tags).search(query, page)

    def assign(self, tag_id: TagId, entity: EntityReference) -> TagAssignment:
        with self._runtime.uow_factory() as uow:
            assignment = TagService(
                uow.tags,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).assign(tag_id, entity)
            self._runtime.record_change(
                uow,
                event_type="tag.assigned",
                aggregate_type=entity.kind,
                aggregate_id=entity.id,
                changes={"fields": ["tags"]},
                payload={"tag_id": str(tag_id)},
            )
            uow.commit()
            return assignment

    def remove(self, tag_id: TagId, entity: EntityReference) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = TagService(
                uow.tags,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).remove(tag_id, entity)
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="tag.removed",
                    aggregate_type=entity.kind,
                    aggregate_id=entity.id,
                    changes={"fields": ["tags"]},
                    payload={"tag_id": str(tag_id)},
                )
            uow.commit()
            return removed

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest | None = None,
    ) -> Page[Tag]:
        with self._runtime.uow_factory() as uow:
            return TagService(uow.tags).list_for_entity(entity, page)
