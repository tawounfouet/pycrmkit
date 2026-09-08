"""Application service for Lead lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.leads.entities import Lead, LeadId
from pycrmkit.leads.queries import LeadQuery
from pycrmkit.leads.repository import LeadRepository
from pycrmkit.organizations import OrganizationId


@dataclass(slots=True)
class LeadService:
    """Framework-agnostic service for commercial lead qualification."""

    repository: LeadRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        contact_id: ContactId,
        organization_id: OrganizationId | None = None,
        source: str | None = None,
    ) -> Lead:
        now = self.clock.now()
        lead = Lead(
            id=self.id_factory.new(LeadId),
            created_at=now,
            updated_at=now,
            contact_id=contact_id,
            organization_id=organization_id,
            source=source,
        )
        self.repository.save(lead)
        return lead

    def get(self, lead_id: LeadId) -> Lead:
        return self.repository.get(lead_id)

    def open(self, lead_id: LeadId) -> Lead:
        lead = self.repository.get(lead_id)
        lead.open(self.clock.now())
        self.repository.save(lead)
        return lead

    def mark_contacted(self, lead_id: LeadId) -> Lead:
        lead = self.repository.get(lead_id)
        lead.mark_contacted(self.clock.now())
        self.repository.save(lead)
        return lead

    def qualify(self, lead_id: LeadId) -> Lead:
        lead = self.repository.get(lead_id)
        lead.qualify(self.clock.now())
        self.repository.save(lead)
        return lead

    def disqualify(self, lead_id: LeadId) -> Lead:
        lead = self.repository.get(lead_id)
        lead.disqualify(self.clock.now())
        self.repository.save(lead)
        return lead

    def list(
        self,
        query: LeadQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Lead]:
        return self.repository.list(
            query or LeadQuery(),
            page or OffsetPageRequest(),
        )
