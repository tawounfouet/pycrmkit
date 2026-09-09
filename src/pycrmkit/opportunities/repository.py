"""Persistence contract for Opportunity aggregates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.opportunities.entities import Opportunity, OpportunityId
from pycrmkit.opportunities.queries import OpportunityQuery


@runtime_checkable
class OpportunityRepository(Protocol):
    """Backend-neutral Opportunity repository contract.

    ``get`` raises ``NotFoundError`` for missing records; ``find`` is nullable.
    Listing uses ``created_at DESC, id ASC`` ordering with exact pagination.
    """

    def get(self, opportunity_id: OpportunityId) -> Opportunity:
        """Return an opportunity or raise NotFoundError."""

    def find(self, opportunity_id: OpportunityId) -> Opportunity | None:
        """Return an opportunity or None."""

    def save(self, opportunity: Opportunity) -> None:
        """Persist current state without committing an outer transaction."""

    def list(
        self,
        query: OpportunityQuery,
        page: OffsetPageRequest,
    ) -> Page[Opportunity]:
        """List opportunities using deterministic reverse-creation ordering."""
