from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.core import EntityId, FixedClock, OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import (
    Organization,
    OrganizationDomain,
    OrganizationId,
    OrganizationQuery,
    OrganizationRepository,
    OrganizationService,
    OrganizationStatus,
    OrganizationUpdate,
)


class DeterministicIdFactory:
    def new(self, id_type):
        return id_type(UUID("00000000-0000-4000-8000-000000000121"))


class ServiceRepository:
    def __init__(self) -> None:
        self.organizations: dict[OrganizationId, Organization] = {}

    def get(self, organization_id: OrganizationId) -> Organization:
        organization = self.find(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found", code="organization.not_found")
        return organization

    def find(self, organization_id: OrganizationId) -> Organization | None:
        organization = self.organizations.get(organization_id)
        return deepcopy(organization) if organization else None

    def save(self, organization: Organization) -> None:
        self.organizations[organization.id] = deepcopy(organization)

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
        items = [
            item
            for item in self.organizations.values()
            if query.include_archived or item.status is not OrganizationStatus.ARCHIVED
        ]
        items.sort(key=lambda item: (item.created_at, item.id))
        selected = items[page.offset : page.offset + page.limit]
        return Page(tuple(deepcopy(selected)), page.limit, page.offset, len(items))


def test_organization_service_create_update_archive_and_search() -> None:
    repository = ServiceRepository()
    assert isinstance(repository, OrganizationRepository)
    clock = FixedClock(datetime(2026, 9, 6, 12, 0, tzinfo=UTC))
    service = OrganizationService(
        repository=repository,
        id_factory=DeterministicIdFactory(),
        clock=clock,
    )

    organization = service.create(
        legal_name=" Example Holdings SAS ",
        trading_name=" Example CRM ",
        domains=(OrganizationDomain("EXAMPLE.COM", is_primary=True),),
        source=" Web ",
        metadata={"campaign": "launch"},
    )

    assert str(organization.id) == "00000000-0000-4000-8000-000000000121"
    assert organization.display_name == "Example CRM"
    assert service.get(organization.id) == organization

    clock.advance(timedelta(minutes=5))
    owner_id = EntityId(UUID("00000000-0000-4000-8000-000000000199"))
    updated = service.update(
        organization.id,
        OrganizationUpdate(
            trading_name="Example Cloud",
            owner_id=owner_id,
            source=None,
        ),
    )

    assert updated.display_name == "Example Cloud"
    assert updated.owner_id == owner_id
    assert updated.source is None
    assert updated.updated_at == clock.now()
    assert service.search().items == (updated,)

    clock.advance(timedelta(minutes=5))
    archived = service.archive(organization.id)
    assert archived.status is OrganizationStatus.ARCHIVED
    assert service.search().items == ()
    assert service.search(OrganizationQuery(include_archived=True)).items == (archived,)
