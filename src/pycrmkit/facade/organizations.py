"""Organizations facade namespace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.facade._runtime import CRMRuntime, revision_fields
from pycrmkit.organizations import (
    Organization,
    OrganizationAddress,
    OrganizationDomain,
    OrganizationId,
    OrganizationQuery,
    OrganizationService,
    OrganizationStatus,
    OrganizationUpdate,
)


class OrganizationsAPI:
    """Transactional facade namespace for Organizations."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(
        self,
        *,
        legal_name: str,
        trading_name: str | None = None,
        display_name: str | None = None,
        registration_number: str | None = None,
        tax_id: str | None = None,
        status: OrganizationStatus = OrganizationStatus.ACTIVE,
        owner_id: EntityId | None = None,
        source: str | None = None,
        domains: Sequence[OrganizationDomain] = (),
        addresses: Sequence[OrganizationAddress] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Organization:
        with self._runtime.uow_factory() as uow:
            organization = OrganizationService(
                uow.organizations,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                legal_name=legal_name,
                trading_name=trading_name,
                display_name=display_name,
                registration_number=registration_number,
                tax_id=tax_id,
                status=status,
                owner_id=owner_id,
                source=source,
                domains=domains,
                addresses=addresses,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="organization.created",
                aggregate_type="organization",
                aggregate_id=organization.id,
                changes={"fields": ["legal_name"]},
            )
            uow.commit()
            return organization

    def get(self, organization_id: OrganizationId) -> Organization:
        with self._runtime.uow_factory() as uow:
            return uow.organizations.get(organization_id)

    def update(
        self,
        organization_id: OrganizationId,
        changes: OrganizationUpdate,
    ) -> Organization:
        with self._runtime.uow_factory() as uow:
            organization = OrganizationService(
                uow.organizations,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).update(organization_id, changes)
            self._runtime.record_change(
                uow,
                event_type="organization.updated",
                aggregate_type="organization",
                aggregate_id=organization.id,
                changes={"fields": revision_fields(changes)},
            )
            uow.commit()
            return organization

    def archive(self, organization_id: OrganizationId) -> Organization:
        with self._runtime.uow_factory() as uow:
            organization = OrganizationService(
                uow.organizations,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).archive(organization_id)
            self._runtime.record_change(
                uow,
                event_type="organization.archived",
                aggregate_type="organization",
                aggregate_id=organization.id,
                changes={"fields": ["status"]},
            )
            uow.commit()
            return organization

    def search(
        self,
        query: OrganizationQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Organization]:
        with self._runtime.uow_factory() as uow:
            return OrganizationService(uow.organizations).search(query, page)
