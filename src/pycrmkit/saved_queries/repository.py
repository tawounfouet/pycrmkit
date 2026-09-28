"""Persistence contract for versioned SavedQuery definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.saved_queries.entities import SavedQuery, SavedQueryId
from pycrmkit.saved_queries.queries import SavedQueryQuery


@runtime_checkable
class SavedQueryRepository(Protocol):
    """Observable persistence semantics shared by adapters."""

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        """Return latest or requested revision, else NotFoundError."""

    def find(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery | None:
        """Return latest/requested revision or None."""

    def find_by_key(self, key: str) -> SavedQuery | None:
        """Return latest SavedQuery by normalized key."""

    def save(self, query: SavedQuery) -> None:
        """Append one revision with optimistic sequential semantics."""

    def list_revisions(self, query_id: SavedQueryId) -> tuple[SavedQuery, ...]:
        """Return all revisions ordered ascending."""

    def search(
        self,
        query: SavedQueryQuery,
        page: OffsetPageRequest,
    ) -> Page[SavedQuery]:
        """Search latest revisions with deterministic pagination."""


__all__ = ["SavedQueryRepository"]
