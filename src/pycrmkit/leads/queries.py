"""Backend-independent Lead query expressions."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.contacts import ContactId
from pycrmkit.leads.entities import LeadStatus
from pycrmkit.organizations import OrganizationId


@dataclass(frozen=True, slots=True)
class LeadQuery:
    """Portable filters for Lead repositories."""

    status: LeadStatus | None = None
    contact_id: ContactId | None = None
    organization_id: OrganizationId | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", LeadStatus(self.status))
        if self.source is not None:
            source = " ".join(self.source.strip().split()).casefold()
            object.__setattr__(self, "source", source or None)
