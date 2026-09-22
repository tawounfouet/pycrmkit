"""Lead aggregate root."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.contacts import ContactId
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.opportunities.entities import OpportunityId
from pycrmkit.organizations import OrganizationId


class LeadId(UUIDId):
    """Strongly typed identifier for a Lead."""


class LeadStatus(StrEnum):
    """Commercial qualification lifecycle defined by the 0.3 sales foundation."""

    NEW = "new"
    OPEN = "open"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONVERTED = "converted"


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > 120:
        raise ValidationError(
            f"{field_name} must be at most 120 characters",
            code=f"lead.{field_name}.too_long",
        )
    return normalized


@dataclass(eq=False, slots=True)
class Lead(TimestampedEntity[LeadId]):
    """Unqualified or partially qualified commercial interest."""

    contact_id: ContactId
    organization_id: OrganizationId | None = None
    source: str | None = None
    status: LeadStatus = LeadStatus.NEW
    converted_opportunity_id: OpportunityId | None = None
    conversion_idempotency_key: str | None = field(default=None, repr=False)
    conversion_request_fingerprint: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        if not isinstance(self.contact_id, ContactId):
            raise ValidationError(
                "lead contact_id must be a ContactId",
                code="lead.contact_id.invalid",
            )
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise ValidationError(
                "lead organization_id must be an OrganizationId",
                code="lead.organization_id.invalid",
            )
        self.source = _normalize_optional_text(self.source, field_name="source")
        self.status = LeadStatus(self.status)
        self._validate_conversion_provenance()

    def open(self, at: datetime) -> None:
        """Move a newly captured lead into active handling."""

        self._transition(
            LeadStatus.OPEN,
            at,
            allowed_from={LeadStatus.NEW},
        )

    def mark_contacted(self, at: datetime) -> None:
        """Record that commercial contact has occurred."""

        self._transition(
            LeadStatus.CONTACTED,
            at,
            allowed_from={LeadStatus.NEW, LeadStatus.OPEN},
        )

    def qualify(self, at: datetime) -> None:
        """Mark the lead as commercially qualified."""

        self._transition(
            LeadStatus.QUALIFIED,
            at,
            allowed_from={LeadStatus.NEW, LeadStatus.OPEN, LeadStatus.CONTACTED},
        )

    def disqualify(self, at: datetime) -> None:
        """Move the lead to a terminal disqualified state."""

        self._transition(
            LeadStatus.DISQUALIFIED,
            at,
            allowed_from={
                LeadStatus.NEW,
                LeadStatus.OPEN,
                LeadStatus.CONTACTED,
                LeadStatus.QUALIFIED,
            },
        )

    def mark_converted(
        self,
        at: datetime,
        *,
        opportunity_id: OpportunityId | None = None,
        idempotency_key: str | None = None,
        request_fingerprint: str | None = None,
    ) -> None:
        """Mark a qualified lead converted and optionally record conversion provenance.

        The optional arguments preserve the pre-0.3.0b2 aggregate-level transition
        while the public conversion workflow records the complete provenance tuple.
        """

        provided = (
            opportunity_id is not None,
            idempotency_key is not None,
            request_fingerprint is not None,
        )
        if any(provided) and not all(provided):
            raise ValidationError(
                "conversion provenance must include opportunity, idempotency key, and fingerprint",
                code="lead.conversion.provenance.incomplete",
            )
        if opportunity_id is not None and not isinstance(opportunity_id, OpportunityId):
            raise ValidationError(
                "converted opportunity id must be an OpportunityId",
                code="lead.conversion.opportunity_id.invalid",
            )
        self._transition(
            LeadStatus.CONVERTED,
            at,
            allowed_from={LeadStatus.QUALIFIED},
        )
        self.converted_opportunity_id = opportunity_id
        self.conversion_idempotency_key = idempotency_key
        self.conversion_request_fingerprint = request_fingerprint

    def _transition(
        self,
        target: LeadStatus,
        at: datetime,
        *,
        allowed_from: set[LeadStatus],
    ) -> None:
        timestamp = as_utc(at)
        if timestamp < self.created_at:
            raise ValidationError(
                "lead transition timestamp cannot be earlier than creation",
                code="lead.transition.invalid_timestamp",
            )
        if self.status not in allowed_from:
            raise InvalidStateError(
                f"lead cannot transition from {self.status.value} to {target.value}",
                code="lead.transition.invalid",
                context={
                    "lead_id": str(self.id),
                    "from_status": self.status.value,
                    "to_status": target.value,
                },
            )
        self.status = target
        self.updated_at = timestamp

    def _validate_conversion_provenance(self) -> None:
        values = (
            self.converted_opportunity_id,
            self.conversion_idempotency_key,
            self.conversion_request_fingerprint,
        )
        if self.status is not LeadStatus.CONVERTED and any(value is not None for value in values):
            raise ValidationError(
                "conversion provenance is only valid for converted leads",
                code="lead.conversion.provenance.status_mismatch",
            )
        populated = tuple(value is not None for value in values)
        if self.status is LeadStatus.CONVERTED and any(populated) and not all(populated):
            raise ValidationError(
                "converted lead provenance must be complete when present",
                code="lead.conversion.provenance.incomplete",
            )
        if (
            self.converted_opportunity_id is not None
            and not isinstance(self.converted_opportunity_id, OpportunityId)
        ):
            raise ValidationError(
                "converted opportunity id must be an OpportunityId",
                code="lead.conversion.opportunity_id.invalid",
            )
