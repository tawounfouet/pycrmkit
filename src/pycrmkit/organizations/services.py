"""Application service for Organization lifecycle operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.organizations.dto import OrganizationUpdate, UnsetType
from pycrmkit.organizations.entities import Organization, OrganizationId, OrganizationStatus
from pycrmkit.organizations.policies import resolve_display_name
from pycrmkit.organizations.queries import OrganizationQuery
from pycrmkit.organizations.repository import OrganizationRepository
from pycrmkit.organizations.value_objects import OrganizationAddress, OrganizationDomain

T = TypeVar("T")


@dataclass(slots=True)
class OrganizationService:
    """Framework-agnostic Organization application service."""

    repository: OrganizationRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

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
        """Create and persist an Organization after domain validation."""
        if status is OrganizationStatus.ARCHIVED:
            raise InvalidStateError(
                "organizations cannot be created directly as archived",
                code="organization.create.archived",
            )
        now = self.clock.now()
        organization = Organization(
            id=self.id_factory.new(OrganizationId),
            created_at=now,
            updated_at=now,
            legal_name=legal_name,
            trading_name=trading_name,
            display_name=display_name,
            registration_number=registration_number,
            tax_id=tax_id,
            status=status,
            owner_id=owner_id,
            source=source,
            domains=tuple(domains),
            addresses=tuple(addresses),
            metadata=dict(metadata or {}),
        )
        self.repository.save(organization)
        return organization

    def get(self, organization_id: OrganizationId) -> Organization:
        """Return an Organization using the repository's not-found contract."""
        return self.repository.get(organization_id)

    def update(
        self,
        organization_id: OrganizationId,
        changes: OrganizationUpdate,
    ) -> Organization:
        """Validate a typed partial update and persist the resulting Organization."""
        current = self.repository.get(organization_id)
        current.ensure_mutable()
        now = self.clock.now()
        status = self._value(changes.status, current.status)
        if status is OrganizationStatus.ARCHIVED:
            raise InvalidStateError(
                "use OrganizationService.archive() to archive an organization",
                code="organization.update.archive_requires_archive_operation",
            )
        legal_name = self._value(changes.legal_name, current.legal_name)
        trading_name = self._value(changes.trading_name, current.trading_name)
        display_name = self._display_name_for_update(
            current,
            changes,
            legal_name,
            trading_name,
        )
        candidate = Organization(
            id=current.id,
            created_at=current.created_at,
            updated_at=now,
            legal_name=legal_name,
            trading_name=trading_name,
            display_name=display_name,
            registration_number=self._value(
                changes.registration_number,
                current.registration_number,
            ),
            tax_id=self._value(changes.tax_id, current.tax_id),
            status=status,
            owner_id=self._value(changes.owner_id, current.owner_id),
            source=self._value(changes.source, current.source),
            domains=self._value(changes.domains, current.domains),
            addresses=self._value(changes.addresses, current.addresses),
            metadata=self._value(changes.metadata, current.metadata),
        )
        self.repository.save(candidate)
        return candidate

    def archive(self, organization_id: OrganizationId) -> Organization:
        """Archive an organization through the repository's shared contract."""
        return self.repository.archive(organization_id, self.clock.now())

    def search(
        self,
        query: OrganizationQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Organization]:
        """Search organizations using backend-independent filters and pagination."""
        return self.repository.search(
            query or OrganizationQuery(),
            page or OffsetPageRequest(),
        )

    @staticmethod
    def _display_name_for_update(
        current: Organization,
        changes: OrganizationUpdate,
        legal_name: str,
        trading_name: str | None,
    ) -> str | None:
        if not isinstance(changes.display_name, UnsetType):
            return changes.display_name
        current_derived = resolve_display_name(
            legal_name=current.legal_name,
            trading_name=current.trading_name,
            explicit=None,
        )
        names_changed = not isinstance(changes.legal_name, UnsetType) or not isinstance(
            changes.trading_name,
            UnsetType,
        )
        if names_changed and current.display_name == current_derived:
            return resolve_display_name(
                legal_name=legal_name,
                trading_name=trading_name,
                explicit=None,
            )
        return current.display_name

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
