"""SQLAlchemy LeadRepository implementation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.leads import Lead, LeadId, LeadQuery
from pycrmkit.storage.sqlalchemy.mappers import lead_from_model, lead_to_model
from pycrmkit.storage.sqlalchemy.models.lead import LeadModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyLeadRepository:
    """SQLAlchemy adapter for Lead aggregates."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, lead_id: LeadId) -> Lead:
        lead = self.find(lead_id)
        if lead is None:
            raise NotFoundError(
                "lead not found",
                code="lead.not_found",
                context={"lead_id": str(lead_id)},
            )
        return lead

    def find(self, lead_id: LeadId) -> Lead | None:
        model = self.session.get(LeadModel, str(lead_id))
        return None if model is None else lead_from_model(model)

    def save(self, lead: Lead) -> None:
        model = self.session.get(LeadModel, str(lead.id))
        target = lead_to_model(lead, model)
        if model is None:
            self.session.add(target)

    def list(self, query: LeadQuery, page: OffsetPageRequest) -> Page[Lead]:
        statement = select(LeadModel)
        if query.status is not None:
            statement = statement.where(LeadModel.status == query.status.value)
        if query.contact_id is not None:
            statement = statement.where(LeadModel.contact_id == str(query.contact_id))
        if query.organization_id is not None:
            statement = statement.where(
                LeadModel.organization_id == str(query.organization_id)
            )
        if query.source is not None:
            statement = statement.where(func.lower(LeadModel.source) == query.source)
        statement = statement.order_by(
            LeadModel.created_at.desc(),
            LeadModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            lead_from_model,
        )
