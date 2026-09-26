"""SQLAlchemy RelationshipRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.relationships import Relationship, RelationshipId, RelationshipQuery
from pycrmkit.storage.sqlalchemy.mappers import (
    relationship_from_model,
    relationship_to_model,
)
from pycrmkit.storage.sqlalchemy.models.relationship import RelationshipModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyRelationshipRepository:
    """Session-scoped SQLAlchemy adapter for directional CRM relationships."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, relationship_id: RelationshipId) -> Relationship:
        relationship = self.find(relationship_id)
        if relationship is None:
            raise NotFoundError(
                "Relationship not found",
                code="relationship.not_found",
                context={"relationship_id": str(relationship_id)},
            )
        return relationship

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        model = self.session.get(RelationshipModel, str(relationship_id))
        return None if model is None else relationship_from_model(model)

    def save(self, relationship: Relationship) -> None:
        model = self.session.get(RelationshipModel, str(relationship.id))
        target = relationship_to_model(relationship, model)
        if model is None:
            self.session.add(target)

    def end(
        self,
        relationship_id: RelationshipId,
        ended_at: datetime,
    ) -> Relationship:
        relationship = self.get(relationship_id)
        relationship.end(ended_at)
        self.save(relationship)
        return relationship

    def search(
        self,
        query: RelationshipQuery,
        page: OffsetPageRequest,
    ) -> Page[Relationship]:
        statement = select(RelationshipModel)
        if query.active_at is not None:
            statement = statement.where(
                RelationshipModel.valid_from <= query.active_at,
                or_(
                    RelationshipModel.valid_until.is_(None),
                    query.active_at < RelationshipModel.valid_until,
                ),
            )
        elif not query.include_ended:
            statement = statement.where(RelationshipModel.valid_until.is_(None))
        if query.entity is not None:
            kind = query.entity.kind.value
            identifier = str(query.entity.id)
            statement = statement.where(
                or_(
                    and_(
                        RelationshipModel.source_kind == kind,
                        RelationshipModel.source_id == identifier,
                    ),
                    and_(
                        RelationshipModel.target_kind == kind,
                        RelationshipModel.target_id == identifier,
                    ),
                )
            )
        if query.source is not None:
            statement = statement.where(
                RelationshipModel.source_kind == query.source.kind.value,
                RelationshipModel.source_id == str(query.source.id),
            )
        if query.target is not None:
            statement = statement.where(
                RelationshipModel.target_kind == query.target.kind.value,
                RelationshipModel.target_id == str(query.target.id),
            )
        if query.relationship_type is not None:
            statement = statement.where(
                RelationshipModel.relationship_type
                == query.relationship_type.code
            )
        if query.is_primary is not None:
            statement = statement.where(
                RelationshipModel.is_primary == query.is_primary
            )
        statement = statement.order_by(
            RelationshipModel.created_at.asc(),
            RelationshipModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            relationship_from_model,
        )
