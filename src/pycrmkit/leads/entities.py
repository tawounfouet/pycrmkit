"""Lead aggregate root."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pycrmkit.contacts import ContactId
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
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

    def mark_converted(self, at: datetime) -> None:
        """Mark a qualified lead converted.

        Public lead-to-opportunity conversion is intentionally deferred to
        0.3.0b2; this aggregate transition exists so repositories can already
        preserve the complete declared Lead state model.
        """

        self._transition(
            LeadStatus.CONVERTED,
            at,
            allowed_from={LeadStatus.QUALIFIED},
        )

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
