"""SavedQuery persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.saved_queries.repository import SavedQueryRepository
from pycrmkit.segments.repository import SegmentQueryExecutor


@runtime_checkable
class SavedQueryUnitOfWork(Protocol):
    """Optional UoW capability for SavedQuery-aware adapters."""

    @property
    def saved_queries(self) -> SavedQueryRepository:
        """Versioned SavedQuery definitions in the transaction."""

    @property
    def segment_query_executor(self) -> SegmentQueryExecutor:
        """Shared portable query evaluator/compiler."""


__all__ = ["SavedQueryUnitOfWork"]
