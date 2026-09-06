"""Persistence contract for Organization aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.organizations.entities import Organization, OrganizationId
from pycrmkit.organizations.queries import OrganizationQuery


@runtime_checkable
class OrganizationRepository(Protocol):
    """Backend-neutral repository contract for organizations."""

    def get(self, organization_id: OrganizationId) -> Organization:
        """Return an organization or raise NotFoundError when missing."""

    def find(self, organization_id: OrganizationId) -> Organization | None:
        """Return an organization or None when missing."""

    def save(self, organization: Organization) -> None:
        """Persist current organization state without committing an outer transaction."""

    def archive(self, organization_id: OrganizationId, archived_at: datetime) -> Organization:
        """Archive the organization and return the resulting domain entity."""

    def search(
        self,
        query: OrganizationQuery,
        page: OffsetPageRequest,
    ) -> Page[Organization]:
        """Search organizations with exact count and deterministic pagination."""
