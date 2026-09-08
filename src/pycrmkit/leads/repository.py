"""Persistence contract for Lead aggregates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.leads.entities import Lead, LeadId
from pycrmkit.leads.queries import LeadQuery


@runtime_checkable
class LeadRepository(Protocol):
    """Backend-neutral Lead repository contract.

    ``get`` raises ``NotFoundError`` for missing records; ``find`` is nullable.
    Listing uses ``created_at DESC, id ASC`` ordering with exact pagination.
    """

    def get(self, lead_id: LeadId) -> Lead:
        """Return a lead or raise NotFoundError."""

    def find(self, lead_id: LeadId) -> Lead | None:
        """Return a lead or None."""

    def save(self, lead: Lead) -> None:
        """Persist current lead state without committing an outer transaction."""

    def list(self, query: LeadQuery, page: OffsetPageRequest) -> Page[Lead]:
        """List leads using deterministic reverse-creation ordering."""
