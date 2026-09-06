"""Persistence contract for tags and assignments."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.tags.entities import Tag, TagAssignment, TagId
from pycrmkit.tags.queries import TagQuery


@runtime_checkable
class TagRepository(Protocol):
    """Observable persistence semantics shared by all Tag adapters."""

    def get(self, tag_id: TagId) -> Tag:
        """Return one Tag or raise NotFoundError."""

    def find(self, tag_id: TagId) -> Tag | None:
        """Return one Tag or None when absence is expected."""

    def find_by_normalized(self, normalized_name: str) -> Tag | None:
        """Look up a Tag by its normalized name."""

    def save(self, tag: Tag) -> None:
        """Persist Tag state, enforcing normalized-name uniqueness."""

    def search(self, query: TagQuery, page: OffsetPageRequest) -> Page[Tag]:
        """Return deterministically ordered Tags."""

    def assign(self, assignment: TagAssignment) -> TagAssignment:
        """Persist an assignment or raise DuplicateError for an existing pair."""

    def remove(self, tag_id: TagId, entity: EntityReference, removed_at: datetime) -> bool:
        """Remove an assignment, returning whether one existed."""

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[Tag]:
        """List Tags assigned to one entity with deterministic ordering."""
