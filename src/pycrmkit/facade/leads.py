"""Leads facade namespace."""

from __future__ import annotations

from pycrmkit.contacts import ContactId
from pycrmkit.facade._runtime import CRMRuntime, present_fields
from pycrmkit.leads import Lead, LeadId, LeadService
from pycrmkit.organizations import OrganizationId


class LeadsAPI:
    """Transactional facade namespace for commercial lead qualification."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(
        self,
        *,
        contact_id: ContactId,
        organization_id: OrganizationId | None = None,
        source: str | None = None,
    ) -> Lead:
        with self._runtime.uow_factory() as uow:
            lead = LeadService(
                uow.leads,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                contact_id=contact_id,
                organization_id=organization_id,
                source=source,
            )
            self._runtime.record_change(
                uow,
                event_type="lead.created",
                aggregate_type="lead",
                aggregate_id=lead.id,
                changes={
                    "fields": present_fields(
                        {
                            "contact_id": contact_id,
                            "organization_id": organization_id,
                            "source": source,
                        }
                    )
                },
                payload={"status": lead.status.value},
            )
            uow.commit()
            return lead

    def qualify(self, lead_id: LeadId) -> Lead:
        with self._runtime.uow_factory() as uow:
            lead = LeadService(
                uow.leads,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).qualify(lead_id)
            self._runtime.record_change(
                uow,
                event_type="lead.qualified",
                aggregate_type="lead",
                aggregate_id=lead.id,
                changes={"fields": ["status"]},
                payload={"status": lead.status.value},
            )
            uow.commit()
            return lead

    def disqualify(self, lead_id: LeadId) -> Lead:
        with self._runtime.uow_factory() as uow:
            lead = LeadService(
                uow.leads,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).disqualify(lead_id)
            self._runtime.record_change(
                uow,
                event_type="lead.disqualified",
                aggregate_type="lead",
                aggregate_id=lead.id,
                changes={"fields": ["status"]},
                payload={"status": lead.status.value},
            )
            uow.commit()
            return lead
