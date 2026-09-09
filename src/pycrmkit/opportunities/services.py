"""Application service for Opportunity lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.opportunities.entities import Opportunity, OpportunityId
from pycrmkit.opportunities.queries import OpportunityQuery
from pycrmkit.opportunities.repository import OpportunityRepository
from pycrmkit.organizations import OrganizationId
from pycrmkit.pipelines import PipelineRepository, PipelineTransitionPolicy


@dataclass(slots=True)
class OpportunityService:
    """Framework-agnostic service for commercial opportunities."""
    repository: OpportunityRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)
    pipeline_repository: PipelineRepository | None = None

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
        now = self.clock.now()
        opportunity = Opportunity(
            id=self.id_factory.new(OpportunityId),
            created_at=now,
            updated_at=now,
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
        self.repository.save(opportunity)
        return opportunity

    def get(self, opportunity_id: OpportunityId) -> Opportunity:
        return self.repository.get(opportunity_id)

    def move(self, opportunity_id: OpportunityId, *, to: str) -> Opportunity:
        """Move an opportunity using its persisted pipeline transition policy."""
        opportunity = self.repository.get(opportunity_id)
        if opportunity.pipeline_id is None:
            raise InvalidStateError(
                "opportunity has no pipeline",
                code="opportunity.pipeline.required",
                context={"opportunity_id": str(opportunity.id)},
            )
        if self.pipeline_repository is None:
            raise InvalidStateError(
                "pipeline repository is required for stage movement",
                code="opportunity.pipeline.repository_required",
            )
        pipeline = self.pipeline_repository.get(opportunity.pipeline_id)
        target = PipelineTransitionPolicy.resolve(
            pipeline,
            from_stage=opportunity.stage_id,
            to_stage=to,
        )
        opportunity.move_to_stage(
            target.id,
            probability=target.default_probability,
            at=self.clock.now(),
            outcome=target.outcome if target.terminal else None,
        )
        self.repository.save(opportunity)
        return opportunity

    def mark_won(self, opportunity_id: OpportunityId) -> Opportunity:
        opportunity = self.repository.get(opportunity_id)
        opportunity.mark_won(self.clock.now())
        self.repository.save(opportunity)
        return opportunity

    def mark_lost(self, opportunity_id: OpportunityId) -> Opportunity:
        opportunity = self.repository.get(opportunity_id)
        opportunity.mark_lost(self.clock.now())
        self.repository.save(opportunity)
        return opportunity

    def cancel(self, opportunity_id: OpportunityId) -> Opportunity:
        opportunity = self.repository.get(opportunity_id)
        opportunity.cancel(self.clock.now())
        self.repository.save(opportunity)
        return opportunity

    def list(
        self,
        query: OpportunityQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Opportunity]:
        return self.repository.list(
            query or OpportunityQuery(),
            page or OffsetPageRequest(),
        )
