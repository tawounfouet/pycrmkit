"""Backend-independent Opportunity query expressions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pycrmkit.contacts import ContactId
from pycrmkit.opportunities.entities import OpportunityStatus
from pycrmkit.organizations import OrganizationId


@dataclass(frozen=True, slots=True)
class OpportunityQuery:
    """Portable filters for Opportunity repositories."""

    status: OpportunityStatus | None = None
    contact_id: ContactId | None = None
    organization_id: OrganizationId | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    owner_id: str | None = None
    currency: str | None = None
    expected_close_date: date | None = None

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", OpportunityStatus(self.status))
        for field_name in ("pipeline_id", "stage_id", "owner_id"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = " ".join(value.strip().split()).casefold()
                object.__setattr__(self, field_name, normalized or None)
        if self.currency is not None:
            currency = self.currency.strip().upper()
            object.__setattr__(self, "currency", currency or None)
