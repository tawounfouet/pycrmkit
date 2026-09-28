"""Segmentation persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.segments.repository import (
    SegmentMembershipRepository,
    SegmentQueryExecutor,
    SegmentRepository,
)


@runtime_checkable
class SegmentUnitOfWork(Protocol):
    """Optional UoW capability implemented by adapters supporting Segmentation."""

    @property
    def segments(self) -> SegmentRepository:
        """Segment definitions participating in the transaction."""

    @property
    def segment_memberships(self) -> SegmentMembershipRepository:
        """Stored memberships participating in the transaction."""

    @property
    def segment_query_executor(self) -> SegmentQueryExecutor:
        """Portable query evaluator bound to the same transaction."""


__all__ = ["SegmentUnitOfWork"]
