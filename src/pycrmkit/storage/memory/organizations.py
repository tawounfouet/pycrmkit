"""In-memory OrganizationRepository implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations.entities import Organization, OrganizationId, OrganizationStatus
from pycrmkit.organizations.queries import OrganizationQuery
from pycrmkit.storage.memory._state import _MemoryState


class MemoryOrganizationRepository:
    """Copy-isolated, contract-conformant Organization repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, organization_id: OrganizationId) -> Organization:
        organization = self.find(organization_id)
        if organization is None:
            raise NotFoundError(
                "Organization not found",
                code="organization.not_found",
                context={"organization_id": str(organization_id)},
            )
        return organization

    def find(self, organization_id: OrganizationId) -> Organization | None:
        organization = self._state.organizations.get(organization_id)
        return deepcopy(organization) if organization is not None else None

    def save(self, organization: Organization) -> None:
        self._state.organizations[organization.id] = deepcopy(organization)

    def archive(self, organization_id: OrganizationId, archived_at: datetime) -> Organization:
        organization = self.get(organization_id)
        organization.archive(archived_at)
        self.save(organization)
        return organization

    def search(
        self,
        query: OrganizationQuery,
        page: OffsetPageRequest,
    ) -> Page[Organization]:
        organizations = list(self._state.organizations.values())
        if not query.include_archived:
            organizations = [
                item for item in organizations if item.status is not OrganizationStatus.ARCHIVED
            ]
        if query.status is not None:
            organizations = [item for item in organizations if item.status is query.status]
        if query.domain is not None:
            organizations = [
                item
                for item in organizations
                if any(domain.normalized == query.domain for domain in item.domains)
            ]
        if query.name is not None:
            needle = query.name.casefold()
            organizations = [
                item
                for item in organizations
                if needle
                in " ".join(
                    part
                    for part in (item.legal_name, item.trading_name, item.display_name)
                    if part
                ).casefold()
            ]
        if query.registration_number is not None:
            registration = query.registration_number.casefold()
            organizations = [
                item
                for item in organizations
                if item.registration_number is not None
                and item.registration_number.casefold() == registration
            ]
        if query.owner_id is not None:
            organizations = [item for item in organizations if item.owner_id == query.owner_id]
        if query.source is not None:
            source = query.source.casefold()
            organizations = [
                item
                for item in organizations
                if item.source is not None and item.source.casefold() == source
            ]
        organizations.sort(key=lambda item: (item.created_at, item.id))
        total = len(organizations)
        selected = organizations[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
