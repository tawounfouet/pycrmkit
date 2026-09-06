"""Persistence contract for Relationship aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.relationships.entities import Relationship, RelationshipId
from pycrmkit.relationships.queries import RelationshipQuery


@runtime_checkable
class RelationshipRepository(Protocol):
    """Backend-neutral repository contract for CRM relationships."""

    def get(self, relationship_id: RelationshipId) -> Relationship:
        """Return a relationship or raise NotFoundError when it does not exist."""

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        """Return a relationship or None when it does not exist."""

    def save(self, relationship: Relationship) -> None:
        """Persist current relationship state without committing an outer transaction."""

    def end(self, relationship_id: RelationshipId, ended_at: datetime) -> Relationship:
        """End a relationship and return the resulting domain entity."""

    def search(
        self,
        query: RelationshipQuery,
        page: OffsetPageRequest,
    ) -> Page[Relationship]:
        """Search relationships with exact count and deterministic pagination."""
