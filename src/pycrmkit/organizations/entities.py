"""Organization aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.organizations.policies import (
    normalize_optional_text,
    normalize_required_text,
    resolve_display_name,
    validate_organization_addresses,
    validate_organization_domains,
)
from pycrmkit.organizations.value_objects import OrganizationAddress, OrganizationDomain


class OrganizationId(UUIDId):
    """Strongly typed identifier for an Organization."""


class OrganizationStatus(StrEnum):
    """Lifecycle status for an organization record."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass(eq=False, slots=True)
class Organization(TimestampedEntity[OrganizationId]):
    """Headless CRM organization aggregate."""

    legal_name: str = ""
    trading_name: str | None = None
    display_name: str | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    owner_id: EntityId | None = None
    source: str | None = None
    domains: tuple[OrganizationDomain, ...] = ()
    addresses: tuple[OrganizationAddress, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.legal_name = normalize_required_text(self.legal_name, field_name="legal_name")
        self.trading_name = normalize_optional_text(self.trading_name)
        self.display_name = resolve_display_name(
            legal_name=self.legal_name,
            trading_name=self.trading_name,
            explicit=self.display_name,
        )
        self.registration_number = normalize_optional_text(self.registration_number)
        self.tax_id = normalize_optional_text(self.tax_id)
        self.source = normalize_optional_text(self.source)
        self.domains = tuple(self.domains)
        self.addresses = tuple(self.addresses)
        self.metadata = dict(self.metadata)
        if self.archived_at is not None:
            self.archived_at = as_utc(self.archived_at)
            if self.archived_at < self.created_at:
                raise ValidationError(
                    "archived_at cannot be earlier than created_at",
                    code="organization.archive.invalid_timestamp",
                )
        if self.status is OrganizationStatus.ARCHIVED and self.archived_at is None:
            raise ValidationError(
                "archived organizations require archived_at",
                code="organization.archive.timestamp_required",
            )
        if self.status is not OrganizationStatus.ARCHIVED and self.archived_at is not None:
            raise ValidationError(
                "non-archived organizations cannot carry archived_at",
                code="organization.archive.status_mismatch",
            )
        validate_organization_domains(self.domains)
        validate_organization_addresses(self.addresses)

    def archive(self, at: datetime) -> None:
        """Archive the organization idempotently at an explicit domain timestamp."""
        timestamp = as_utc(at)
        if timestamp < self.created_at:
            raise ValidationError(
                "archive timestamp cannot be earlier than organization creation",
                code="organization.archive.invalid_timestamp",
            )
        if self.status is OrganizationStatus.ARCHIVED:
            return
        self.status = OrganizationStatus.ARCHIVED
        self.archived_at = timestamp
        self.updated_at = timestamp

    def ensure_mutable(self) -> None:
        """Reject profile mutation after archival."""
        if self.status is OrganizationStatus.ARCHIVED:
            raise InvalidStateError(
                "archived organizations cannot be updated",
                code="organization.archived",
                context={"organization_id": str(self.id)},
            )
