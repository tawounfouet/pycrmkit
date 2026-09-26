"""SQLAlchemy OpportunityRepository implementation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityQuery
from pycrmkit.storage.sqlalchemy.mappers import (
    opportunity_from_model,
    opportunity_to_model,
)
from pycrmkit.storage.sqlalchemy.models.opportunity import OpportunityModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyOpportunityRepository:
    """SQLAlchemy adapter for commercial opportunities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, opportunity_id: OpportunityId) -> Opportunity:
        opportunity = self.find(opportunity_id)
        if opportunity is None:
            raise NotFoundError(
                "opportunity not found",
                code="opportunity.not_found",
                context={"opportunity_id": str(opportunity_id)},
            )
        return opportunity

    def find(self, opportunity_id: OpportunityId) -> Opportunity | None:
        model = self.session.get(
            OpportunityModel,
            str(opportunity_id),
        )
        return None if model is None else opportunity_from_model(model)

    def save(self, opportunity: Opportunity) -> None:
        model = self.session.get(
            OpportunityModel,
            str(opportunity.id),
        )
        target = opportunity_to_model(opportunity, model)
        if model is None:
            self.session.add(target)

    def list(
        self,
        query: OpportunityQuery,
        page: OffsetPageRequest,
    ) -> Page[Opportunity]:
        statement = select(OpportunityModel)
        if query.status is not None:
            statement = statement.where(
                OpportunityModel.status == query.status.value
            )
        if query.contact_id is not None:
            statement = statement.where(
                OpportunityModel.contact_id == str(query.contact_id)
            )
        if query.organization_id is not None:
            statement = statement.where(
                OpportunityModel.organization_id
                == str(query.organization_id)
            )
        if query.pipeline_id is not None:
            statement = statement.where(
                func.lower(OpportunityModel.pipeline_id)
                == query.pipeline_id
            )
        if query.stage_id is not None:
            statement = statement.where(
                func.lower(OpportunityModel.stage_id) == query.stage_id
            )
        if query.owner_id is not None:
            statement = statement.where(
                func.lower(OpportunityModel.owner_id) == query.owner_id
            )
        if query.currency is not None:
            statement = statement.where(
                OpportunityModel.currency == query.currency
            )
        if query.expected_close_date is not None:
            statement = statement.where(
                OpportunityModel.expected_close_date
                == query.expected_close_date
            )
        statement = statement.order_by(
            OpportunityModel.created_at.desc(),
            OpportunityModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            opportunity_from_model,
        )
