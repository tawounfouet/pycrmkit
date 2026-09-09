"""Opportunities facade namespace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pycrmkit.contacts import ContactId
from pycrmkit.facade._runtime import CRMRuntime, present_fields
from pycrmkit.opportunities import (
    Opportunity,
    OpportunityId,
    OpportunityService,
    OpportunityStatus,
)
from pycrmkit.organizations import OrganizationId


class OpportunitiesAPI:
    """Transactional facade namespace for opportunity creation and stage movement."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(
        self,
        *,
        name: str,
        contact_id: ContactId,
        organization_id: OrganizationId | None = None,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        estimated_value: Decimal | None = None,
        currency: str | None = None,
        probability: Decimal | None = None,
        expected_close_date: date | None = None,
        owner_id: str | None = None,
    ) -> Opportunity:
        with self._runtime.uow_factory() as uow:
            opportunity = OpportunityService(
                uow.opportunities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                name=name,
                contact_id=contact_id,
                organization_id=organization_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                estimated_value=estimated_value,
                currency=currency,
                probability=probability,
                expected_close_date=expected_close_date,
                owner_id=owner_id,
            )
            self._runtime.record_change(
                uow,
                event_type="opportunity.created",
                aggregate_type="opportunity",
                aggregate_id=opportunity.id,
                changes={
                    "fields": present_fields(
                        {
                            "name": name,
                            "contact_id": contact_id,
                            "organization_id": organization_id,
                            "pipeline_id": pipeline_id,
                            "stage_id": stage_id,
                            "estimated_value": estimated_value,
                            "currency": currency,
                            "probability": probability,
                            "expected_close_date": expected_close_date,
                            "owner_id": owner_id,
                        }
                    )
                },
                payload={"status": opportunity.status.value},
            )
            uow.commit()
            return opportunity

    def move(self, opportunity_id: OpportunityId, *, to: str) -> Opportunity:
        """Move an opportunity to an allowed stage in its persisted pipeline."""
        with self._runtime.uow_factory() as uow:
            before = uow.opportunities.get(opportunity_id)
            from_stage = before.stage_id
            from_status = before.status
            opportunity = OpportunityService(
                uow.opportunities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
                pipeline_repository=uow.pipelines,
            ).move(opportunity_id, to=to)
            self._runtime.record_change(
                uow,
                event_type="opportunity.stage_changed",
                aggregate_type="opportunity",
                aggregate_id=opportunity.id,
                changes={
                    "fields": [
                        "stage_id",
                        "stage_entered_at",
                        "probability",
                        "status",
                    ]
                },
                payload={
                    "from_stage": from_stage,
                    "to_stage": opportunity.stage_id,
                    "status": opportunity.status.value,
                    "pipeline_id": opportunity.pipeline_id,
                },
            )
            if opportunity.status is not from_status:
                terminal_event = {
                    OpportunityStatus.WON: "opportunity.won",
                    OpportunityStatus.LOST: "opportunity.lost",
                    OpportunityStatus.CANCELLED: "opportunity.cancelled",
                }[opportunity.status]
                self._runtime.record_change(
                    uow,
                    event_type=terminal_event,
                    aggregate_type="opportunity",
                    aggregate_id=opportunity.id,
                    changes={"fields": ["status"]},
                    payload={
                        "stage_id": opportunity.stage_id,
                        "pipeline_id": opportunity.pipeline_id,
                    },
                )
            uow.commit()
            return opportunity
