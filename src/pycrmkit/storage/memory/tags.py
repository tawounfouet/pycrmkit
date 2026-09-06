"""In-memory TagRepository implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.tags.entities import Tag, TagAssignment, TagId
from pycrmkit.tags.queries import TagQuery


class MemoryTagRepository:
    """Copy-isolated, contract-conformant Tag repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, tag_id: TagId) -> Tag:
        tag = self.find(tag_id)
        if tag is None:
            raise NotFoundError(
                "Tag not found",
                code="tag.not_found",
                context={"tag_id": str(tag_id)},
            )
        return tag

    def find(self, tag_id: TagId) -> Tag | None:
        tag = self._state.tags.get(tag_id)
        return deepcopy(tag) if tag is not None else None

    def find_by_normalized(self, normalized_name: str) -> Tag | None:
        for tag in self._state.tags.values():
            if tag.name.normalized == normalized_name:
                return deepcopy(tag)
        return None

    def save(self, tag: Tag) -> None:
        existing = self.find_by_normalized(tag.name.normalized)
        if existing is not None and existing.id != tag.id:
            raise DuplicateError(
                "Tag normalized name already exists",
                code="tag.duplicate",
                context={"normalized_name": tag.name.normalized},
            )
        self._state.tags[tag.id] = deepcopy(tag)

    def search(self, query: TagQuery, page: OffsetPageRequest) -> Page[Tag]:
        tags = list(self._state.tags.values())
        if query.name is not None:
            tags = [item for item in tags if item.name.normalized == query.name.normalized]
        tags.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(tags)
        selected = tags[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def assign(self, assignment: TagAssignment) -> TagAssignment:
        key = (assignment.tag_id, assignment.entity)
        if key in self._state.tag_assignments:
            raise DuplicateError(
                "Tag is already assigned to this entity",
                code="tag.assignment.duplicate",
                context={
                    "tag_id": str(assignment.tag_id),
                    "entity_kind": assignment.entity.kind,
                    "entity_id": str(assignment.entity.id),
                },
            )
        stored = deepcopy(assignment)
        self._state.tag_assignments[key] = stored
        return deepcopy(stored)

    def remove(self, tag_id: TagId, entity: EntityReference, removed_at: datetime) -> bool:
        del removed_at
        return self._state.tag_assignments.pop((tag_id, entity), None) is not None

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[Tag]:
        tag_ids = {
            tag_id
            for tag_id, assigned_entity in self._state.tag_assignments
            if assigned_entity == entity
        }
        tags = [tag for tag in self._state.tags.values() if tag.id in tag_ids]
        tags.sort(key=lambda item: (item.name.normalized, str(item.id)))
        total = len(tags)
        selected = tags[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
