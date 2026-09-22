"""Leads facade namespace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pycrmkit.contacts import ContactId
from pycrmkit.facade._runtime import CRMRuntime, present_fields
from pycrmkit.leads import Lead, LeadConversionService, LeadId, LeadService
from pycrmkit.opportunities import Opportunity
from pycrmkit.organizations import OrganizationId


class LeadsAPI:
    """Transactional facade namespace for commercial lead qualification and conversion."""

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

    def convert(
        self,
        lead_id: LeadId,
        *,
        name: str | None = None,
        estimated_value: Decimal | None = None,
        currency: str | None = None,
        pipeline_id: str | None = None,
        expected_close_date: date | None = None,
        owner_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Opportunity:
        """Atomically convert one qualified Lead into exactly one Opportunity."""

        with self._runtime.uow_factory() as uow:
            result = LeadConversionService(
                leads=uow.leads,
                opportunities=uow.opportunities,
                pipelines=uow.pipelines,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).convert(
                lead_id,
                name=name,
                estimated_value=estimated_value,
                currency=currency,
                pipeline_id=pipeline_id,
                expected_close_date=expected_close_date,
                owner_id=owner_id,
                idempotency_key=idempotency_key,
            )
            if not result.created:
                return result.opportunity

            opportunity = result.opportunity
            lead = result.lead
            self._runtime.record_change(
                uow,
                event_type="opportunity.created",
                aggregate_type="opportunity",
                aggregate_id=opportunity.id,
                changes={
                    "fields": present_fields(
                        {
                            "name": opportunity.name,
                            "contact_id": opportunity.contact_id,
                            "organization_id": opportunity.organization_id,
                            "pipeline_id": opportunity.pipeline_id,
                            "stage_id": opportunity.stage_id,
                            "estimated_value": opportunity.estimated_value,
                            "currency": opportunity.currency,
                            "probability": opportunity.probability,
                            "expected_close_date": opportunity.expected_close_date,
                            "owner_id": opportunity.owner_id,
                        }
                    )
                },
                payload={
                    "status": opportunity.status.value,
                    "lead_id": str(lead.id),
                },
            )
            self._runtime.record_change(
                uow,
                event_type="lead.converted",
                aggregate_type="lead",
                aggregate_id=lead.id,
                changes={"fields": ["status", "converted_opportunity_id"]},
                payload={
                    "status": lead.status.value,
                    "opportunity_id": str(opportunity.id),
                },
            )
            uow.commit()
            return opportunity
