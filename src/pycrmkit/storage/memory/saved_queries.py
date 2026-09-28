"""In-memory repository for versioned SavedQuery definitions."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryStatus,
    normalize_saved_query_key,
)
from pycrmkit.storage.memory._state import _MemoryState


class MemorySavedQueryRepository:
    """Copy-isolated versioned SavedQuery repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        query = self.find(query_id, revision)
        if query is None:
            raise NotFoundError(
                "Saved query not found",
                code=(
                    "saved_query.not_found"
                    if revision is None
                    else "saved_query.revision.not_found"
                ),
                context={
                    "saved_query_id": str(query_id),
                    "revision": revision,
                },
            )
        return query

    def find(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery | None:
        versions = self._state.saved_queries.get(query_id, [])
        if not versions:
            return None
        if revision is None:
            return deepcopy(versions[-1])
        for query in versions:
            if query.revision == revision:
                return deepcopy(query)
        return None

    def find_by_key(self, key: str) -> SavedQuery | None:
        normalized = normalize_saved_query_key(key)
        for versions in self._state.saved_queries.values():
            if versions[-1].key == normalized:
                return deepcopy(versions[-1])
        return None

    def save(self, query: SavedQuery) -> None:
        existing_by_key = self.find_by_key(query.key)
        if existing_by_key is not None and existing_by_key.id != query.id:
            raise DuplicateError(
                "Saved-query key already exists",
                code="saved_query.key.duplicate",
                context={"key": query.key},
            )
        versions = self._state.saved_queries.setdefault(query.id, [])
        expected = 1 if not versions else versions[-1].revision + 1
        if query.revision != expected:
            raise ConflictError(
                "Saved-query revisions must be appended sequentially",
                code="saved_query.revision.conflict",
                context={"expected": expected, "actual": query.revision},
            )
        if versions and query.key != versions[-1].key:
            raise ConflictError(
                "Saved-query key is immutable",
                code="saved_query.key.immutable",
            )
        if versions and query.entity_kind != versions[-1].entity_kind:
            raise ConflictError(
                "Saved-query entity kind is immutable",
                code="saved_query.entity_kind.immutable",
            )
        versions.append(deepcopy(query))

    def list_revisions(self, query_id: SavedQueryId) -> tuple[SavedQuery, ...]:
        return tuple(deepcopy(self._state.saved_queries.get(query_id, [])))

    def search(
        self,
        query: SavedQueryQuery,
        page: OffsetPageRequest,
    ) -> Page[SavedQuery]:
        values = [versions[-1] for versions in self._state.saved_queries.values()]
        if not query.include_archived:
            values = [
                item for item in values if item.status is not SavedQueryStatus.ARCHIVED
            ]
        if query.status is not None:
            values = [item for item in values if item.status is query.status]
        if query.visibility is not None:
            values = [item for item in values if item.visibility is query.visibility]
        if query.entity_kind is not None:
            values = [item for item in values if item.entity_kind == query.entity_kind]
        if query.owner_id is not None:
            values = [item for item in values if item.owner_id == query.owner_id]
        values.sort(key=lambda item: (item.name.casefold(), str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


__all__ = ["MemorySavedQueryRepository"]
