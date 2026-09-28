"""Persistence and evaluation contracts for Segmentation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.segments.entities import Segment, SegmentId, SegmentMember
from pycrmkit.segments.expressions import QueryExpression
from pycrmkit.segments.queries import SegmentQuery


@runtime_checkable
class SegmentRepository(Protocol):
    """Backend-neutral Segment repository."""

    def get(self, segment_id: SegmentId) -> Segment:
        """Return one Segment or raise NotFoundError."""

    def find(self, segment_id: SegmentId) -> Segment | None:
        """Return one Segment or None."""

    def find_by_key(self, key: str) -> Segment | None:
        """Return one Segment by normalized key or None."""

    def save(self, segment: Segment) -> None:
        """Persist current Segment state."""

    def search(self, query: SegmentQuery, page: OffsetPageRequest) -> Page[Segment]:
        """Search Segments with deterministic pagination."""


@runtime_checkable
class SegmentMembershipRepository(Protocol):
    """Stored membership for Static and Snapshot Segments."""

    def add(self, member: SegmentMember) -> SegmentMember:
        """Persist one unique membership."""

    def remove(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        """Remove one membership idempotently."""

    def contains(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        """Return whether the exact membership exists."""

    def list(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest,
    ) -> Page[SegmentMember]:
        """List stored memberships."""

    def count(self, segment_id: SegmentId) -> int:
        """Return exact stored membership count."""


@runtime_checkable
class SegmentQueryExecutor(Protocol):
    """Evaluate portable expressions against canonical CRM entities."""

    def execute(
        self,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest,
    ) -> Page[EntityReference]:
        """Return matching entity references."""

    def count(self, entity_kind: str, expression: QueryExpression) -> int:
        """Return exact matching entity count."""

    def exists(self, entity: EntityReference) -> bool:
        """Return whether the referenced canonical entity exists."""


__all__ = [
    "SegmentMembershipRepository",
    "SegmentQueryExecutor",
    "SegmentRepository",
]
