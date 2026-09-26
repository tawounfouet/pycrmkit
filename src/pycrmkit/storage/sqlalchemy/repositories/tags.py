"""SQLAlchemy TagRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import (
    tag_assignment_from_model,
    tag_assignment_to_model,
    tag_from_model,
    tag_to_model,
)
from pycrmkit.storage.sqlalchemy.models.tag import TagAssignmentModel, TagModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.tags import Tag, TagAssignment, TagId, TagQuery


class SQLAlchemyTagRepository:
    """SQLAlchemy adapter preserving normalized-name and assignment uniqueness."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, tag_id: TagId) -> Tag:
        tag = self.find(tag_id)
        if tag is None:
            raise NotFoundError(
                "Tag not found",
                code="tag.not_found",
                context={"tag_id": str(tag_id)},
            )
        return tag

    def find(self, tag_id: TagId) -> Tag | None:
        model = self.session.get(TagModel, str(tag_id))
        return None if model is None else tag_from_model(model)

    def find_by_normalized(self, normalized_name: str) -> Tag | None:
        model = self.session.scalar(
            select(TagModel).where(
                func.lower(TagModel.name) == normalized_name
            )
        )
        return None if model is None else tag_from_model(model)

    def save(self, tag: Tag) -> None:
        with self.session.no_autoflush:
            existing = self.find_by_normalized(tag.name.normalized)
        if existing is not None and existing.id != tag.id:
            raise DuplicateError(
                "Tag normalized name already exists",
                code="tag.duplicate",
                context={"normalized_name": tag.name.normalized},
            )
        model = self.session.get(TagModel, str(tag.id))
        target = tag_to_model(tag, model)
        if model is None:
            self.session.add(target)

    def search(
        self,
        query: TagQuery,
        page: OffsetPageRequest,
    ) -> Page[Tag]:
        statement = select(TagModel)
        if query.name is not None:
            statement = statement.where(
                func.lower(TagModel.name) == query.name.normalized
            )
        statement = statement.order_by(
            TagModel.created_at.asc(),
            TagModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            tag_from_model,
        )

    def assign(self, assignment: TagAssignment) -> TagAssignment:
        with self.session.no_autoflush:
            existing = self.session.scalar(
                select(TagAssignmentModel).where(
                    TagAssignmentModel.tag_id == str(assignment.tag_id),
                    TagAssignmentModel.entity_kind == assignment.entity.kind,
                    TagAssignmentModel.entity_id == str(assignment.entity.id),
                )
            )
        if existing is not None:
            raise DuplicateError(
                "Tag is already assigned to this entity",
                code="tag.assignment.duplicate",
                context={
                    "tag_id": str(assignment.tag_id),
                    "entity_kind": assignment.entity.kind,
                    "entity_id": str(assignment.entity.id),
                },
            )
        model = tag_assignment_to_model(assignment)
        self.session.add(model)
        return tag_assignment_from_model(model)

    def remove(
        self,
        tag_id: TagId,
        entity: EntityReference,
        removed_at: datetime,
    ) -> bool:
        del removed_at
        result = self.session.execute(
            delete(TagAssignmentModel).where(
                TagAssignmentModel.tag_id == str(tag_id),
                TagAssignmentModel.entity_kind == entity.kind,
                TagAssignmentModel.entity_id == str(entity.id),
            )
        )
        return bool(result.rowcount)

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[Tag]:
        statement = (
            select(TagModel)
            .join(
                TagAssignmentModel,
                TagAssignmentModel.tag_id == TagModel.id,
            )
            .where(
                TagAssignmentModel.entity_kind == entity.kind,
                TagAssignmentModel.entity_id == str(entity.id),
            )
            .order_by(
                func.lower(TagModel.name).asc(),
                TagModel.id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            tag_from_model,
        )
